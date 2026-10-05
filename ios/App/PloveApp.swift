import Foundation

enum AppConfiguration {
    private static let apiBaseKey = "Plove4APIBaseURL"

    static var apiBaseURL: URL {
        if let saved = UserDefaults.standard.string(forKey: apiBaseKey),
           let url = normalized(saved) {
            return url
        }
        let configured = Bundle.main.object(forInfoDictionaryKey: "PloveAPIBaseURL") as? String
        return normalized(configured ?? "") ?? URL(string: "http://192.168.10.71:4001")!
    }

    @discardableResult
    static func setAPIBaseURL(_ raw: String) -> Bool {
        guard let url = normalized(raw) else { return false }
        UserDefaults.standard.set(url.absoluteString, forKey: apiBaseKey)
        return true
    }

    private static func normalized(_ raw: String) -> URL? {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard var components = URLComponents(string: text),
              let scheme = components.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              components.host != nil,
              components.user == nil,
              components.password == nil,
              components.query == nil,
              components.fragment == nil else {
            return nil
        }
        components.path = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard var url = components.url else { return nil }
        if url.path != "/" && !url.path.isEmpty {
            url.deleteLastPathComponent()
        }
        return url
    }
}
import Foundation
import Network

final class LocalWebAppServer {
    static let shared = LocalWebAppServer()

    enum ServerError: LocalizedError {
        case webAppMissing
        case listenerFailed(String)
        case invalidURL

        var errorDescription: String? {
            switch self {
            case .webAppMissing: return "IPA 内置前端资源缺失"
            case .listenerFailed(let message): return "本地前端服务启动失败：\(message)"
            case .invalidURL: return "本地前端地址无效"
            }
        }
    }

    private let queue = DispatchQueue(label: "com.plove4.local-web", qos: .userInitiated)
    private let session: URLSession
    private var listener: NWListener?
    private var port: NWEndpoint.Port?
    private var pending: [(Result<URL, Error>) -> Void] = []

    private init() {
        let config = URLSessionConfiguration.ephemeral
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 90
        config.httpShouldSetCookies = false
        session = URLSession(configuration: config)
    }

    func start(completion: @escaping (Result<URL, Error>) -> Void) {
        queue.async { [weak self] in
            guard let self else { return }
            if let port = self.port, let url = self.homeURL(port: port) {
                DispatchQueue.main.async { completion(.success(url)) }
                return
            }
            self.pending.append(completion)
            self.startListenerIfNeeded()
        }
    }

    private var webRoot: URL? {
        Bundle.main.resourceURL?.appendingPathComponent("WebApp", isDirectory: true)
    }

    private func homeURL(port: NWEndpoint.Port) -> URL? {
        URL(string: "http://127.0.0.1:\(port.rawValue)/?native=ios&appBuild=2")
    }

    private func startListenerIfNeeded() {
        guard listener == nil else { return }
        guard webRoot != nil else {
            finishPending(.failure(ServerError.webAppMissing))
            return
        }

        do {
            let listener = try NWListener(using: .tcp, on: .any)
            self.listener = listener
            listener.newConnectionHandler = { [weak self] connection in self?.accept(connection) }
            listener.stateUpdateHandler = { [weak self] state in
                guard let self else { return }
                switch state {
                case .ready:
                    guard let port = listener.port, let url = self.homeURL(port: port) else {
                        self.finishPending(.failure(ServerError.invalidURL))
                        return
                    }
                    self.port = port
                    self.finishPending(.success(url))
                case .failed(let error):
                    self.listener = nil
                    self.port = nil
                    self.finishPending(.failure(ServerError.listenerFailed(error.localizedDescription)))
                    listener.cancel()
                default:
                    break
                }
            }
            listener.start(queue: queue)
        } catch {
            listener = nil
            port = nil
            finishPending(.failure(error))
        }
    }

    private func finishPending(_ result: Result<URL, Error>) {
        let callbacks = pending
        pending.removeAll()
        for callback in callbacks {
            DispatchQueue.main.async { callback(result) }
        }
    }

    private func accept(_ connection: NWConnection) {
        connection.start(queue: queue)
        var buffer = Data()
        let separator = Data("\r\n\r\n".utf8)

        func receiveMore() {
            connection.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { [weak self] data, _, complete, error in
                guard let self else { connection.cancel(); return }
                if let data { buffer.append(data) }

                if let marker = buffer.range(of: separator) {
                    let header = buffer.subdata(in: 0..<marker.lowerBound)
                    let expected = self.contentLength(from: header)
                    let bodyStart = marker.upperBound
                    let bodyEnd = bodyStart + expected
                    if buffer.count >= bodyEnd {
                        let body = expected > 0 ? buffer.subdata(in: bodyStart..<bodyEnd) : Data()
                        self.route(header: header, body: body, connection: connection)
                        return
                    }
                }

                if error != nil || complete || buffer.count > 6 * 1024 * 1024 {
                    connection.cancel()
                    return
                }
                receiveMore()
            }
        }

        receiveMore()
    }

    private func contentLength(from header: Data) -> Int {
        guard let text = String(data: header, encoding: .utf8) else { return 0 }
        for line in text.components(separatedBy: "\r\n").dropFirst() {
            let pair = line.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
            guard pair.count == 2 else { continue }
            if pair[0].trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "content-length" {
                return max(0, Int(pair[1].trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0)
            }
        }
        return 0
    }

    private func headerFields(from text: String) -> [String: String] {
        var headers: [String: String] = [:]
        for line in text.components(separatedBy: "\r\n").dropFirst() {
            let pair = line.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
            guard pair.count == 2 else { continue }
            let key = pair[0].trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let value = pair[1].trimmingCharacters(in: .whitespacesAndNewlines)
            if !key.isEmpty { headers[key] = value }
        }
        return headers
    }

    private func route(header: Data, body: Data, connection: NWConnection) {
        guard let text = String(data: header, encoding: .utf8),
              let first = text.components(separatedBy: "\r\n").first else {
            send(connection, status: 400, type: "text/plain; charset=utf-8", body: Data("bad request".utf8))
            return
        }

        let parts = first.split(separator: " ")
        guard parts.count >= 2 else {
            send(connection, status: 400, type: "text/plain; charset=utf-8", body: Data("bad request".utf8))
            return
        }

        let method = String(parts[0]).uppercased()
        let rawTarget = String(parts[1])
        let headers = headerFields(from: text)

        if method == "OPTIONS" {
            send(connection, status: 204, type: "text/plain; charset=utf-8", body: Data())
            return
        }

        let rawPath = rawTarget.split(separator: "?", maxSplits: 1).first.map(String.init) ?? "/"
        let decodedPath = rawPath.removingPercentEncoding ?? rawPath

        if decodedPath == "/__plove/health" {
            let payload = Data("{\"ok\":true,\"service\":\"plove4-ios\",\"build\":2}".utf8)
            send(connection, status: 200, type: "application/json; charset=utf-8", body: payload)
            return
        }

        if decodedPath == "/api" || decodedPath.hasPrefix("/api/") {
            proxyAPI(rawTarget: rawTarget, method: method, requestHeaders: headers, body: body, connection: connection)
            return
        }

        guard method == "GET" || method == "HEAD" else {
            send(connection, status: 405, type: "text/plain; charset=utf-8", body: Data("method not allowed".utf8))
            return
        }

        let clean = decodedPath.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !clean.contains(".."), let root = webRoot else {
            send(connection, status: 403, type: "text/plain; charset=utf-8", body: Data("forbidden".utf8))
            return
        }

        let candidate = clean.isEmpty ? root.appendingPathComponent("index.html") : root.appendingPathComponent(clean)
        let fileURL: URL
        if FileManager.default.fileExists(atPath: candidate.path), !candidate.hasDirectoryPath {
            fileURL = candidate
        } else if !clean.contains(".") {
            fileURL = root.appendingPathComponent("index.html")
        } else {
            send(connection, status: 404, type: "text/plain; charset=utf-8", body: Data("not found".utf8))
            return
        }

        do {
            let bytes = try Data(contentsOf: fileURL, options: [.mappedIfSafe])
            let cache = fileURL.lastPathComponent == "index.html" ? "no-cache" : "public, max-age=31536000, immutable"
            send(connection, status: 200, type: mimeType(for: fileURL.pathExtension), body: bytes, headOnly: method == "HEAD", cacheControl: cache)
        } catch {
            send(connection, status: 500, type: "text/plain; charset=utf-8", body: Data(error.localizedDescription.utf8))
        }
    }

    private func proxyAPI(rawTarget: String, method: String, requestHeaders: [String: String], body: Data, connection: NWConnection) {
        let base = AppConfiguration.apiBaseURL
        guard let target = URL(string: rawTarget, relativeTo: base)?.absoluteURL,
              target.host?.lowercased() == base.host?.lowercased(),
              target.port == base.port else {
            send(connection, status: 400, type: "application/json; charset=utf-8", body: Data("{\"ok\":false,\"error\":\"invalid proxy target\"}".utf8))
            return
        }

        var request = URLRequest(url: target, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30)
        request.httpMethod = method

        let forwarded = [
            "accept", "content-type", "x-device-token", "x-admin-token",
            "range", "if-none-match", "if-modified-since", "user-agent"
        ]
        for name in forwarded {
            if let value = requestHeaders[name], !value.isEmpty {
                request.setValue(value, forHTTPHeaderField: name)
            }
        }
        request.setValue(base.absoluteString, forHTTPHeaderField: "Referer")
        request.setValue("ios", forHTTPHeaderField: "X-Plove-Native-Client")
        if !body.isEmpty && method != "GET" && method != "HEAD" { request.httpBody = body }

        session.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { connection.cancel(); return }
            self.queue.async {
                if let error {
                    let msg = error.localizedDescription
                        .replacingOccurrences(of: "\\", with: "\\\\")
                        .replacingOccurrences(of: "\"", with: "\\\"")
                    let payload = Data("{\"ok\":false,\"error\":{\"code\":\"UPSTREAM_UNREACHABLE\",\"message\":\"\(msg)\"}}".utf8)
                    self.send(connection, status: 502, type: "application/json; charset=utf-8", body: payload)
                    return
                }
                guard let http = response as? HTTPURLResponse else {
                    self.send(connection, status: 502, type: "application/json; charset=utf-8", body: Data("{\"ok\":false}".utf8))
                    return
                }

                var extra: [String: String] = [:]
                for name in ["ETag", "Last-Modified", "Accept-Ranges", "Content-Range", "Location"] {
                    if let value = http.value(forHTTPHeaderField: name) { extra[name] = value }
                }
                self.send(
                    connection,
                    status: http.statusCode,
                    type: http.value(forHTTPHeaderField: "Content-Type") ?? "application/octet-stream",
                    body: data ?? Data(),
                    headOnly: method == "HEAD",
                    cacheControl: http.value(forHTTPHeaderField: "Cache-Control") ?? "no-store",
                    extraHeaders: extra
                )
            }
        }.resume()
    }

    private func mimeType(for ext: String) -> String {
        switch ext.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "js", "mjs": return "application/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "webp": return "image/webp"
        case "svg": return "image/svg+xml"
        case "ico": return "image/x-icon"
        case "woff": return "font/woff"
        case "woff2": return "font/woff2"
        default: return "application/octet-stream"
        }
    }

    private func send(_ connection: NWConnection, status: Int, type: String, body: Data, headOnly: Bool = false, cacheControl: String = "no-store", extraHeaders: [String: String] = [:]) {
        let reason = HTTPURLResponse.localizedString(forStatusCode: status)
            .split(separator: " ").map { $0.prefix(1).uppercased() + $0.dropFirst() }.joined(separator: " ")
        var headers = "HTTP/1.1 \(status) \(reason)\r\n"
        headers += "Content-Type: \(type)\r\n"
        headers += "Content-Length: \(body.count)\r\n"
        headers += "Cache-Control: \(cacheControl)\r\n"
        headers += "Access-Control-Allow-Origin: *\r\n"
        headers += "Access-Control-Allow-Methods: GET, HEAD, POST, PUT, DELETE, PATCH, OPTIONS\r\n"
        headers += "Access-Control-Allow-Headers: Content-Type, X-Device-Token, X-Admin-Token, Range, If-None-Match, If-Modified-Since\r\n"
        for (name, value) in extraHeaders {
            let safeName = name.replacingOccurrences(of: "\r", with: "").replacingOccurrences(of: "\n", with: "")
            let safeValue = value.replacingOccurrences(of: "\r", with: "").replacingOccurrences(of: "\n", with: "")
            headers += "\(safeName): \(safeValue)\r\n"
        }
        headers += "Connection: close\r\n\r\n"
        var response = Data(headers.utf8)
        if !headOnly { response.append(body) }
        connection.send(content: response, completion: .contentProcessed { _ in connection.cancel() })
    }
}
import UIKit
import WebKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = Plove4ViewController()
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
}

final class Plove4ViewController: UIViewController, WKNavigationDelegate, WKUIDelegate {
    private var webView: WKWebView!
    private let overlay = UIStackView()
    private let message = UILabel()
    private let activity = UIActivityIndicatorView(style: .large)
    private var homeURL: URL?

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }
    override var prefersHomeIndicatorAutoHidden: Bool { false }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureWebView()
        configureOverlay()
        connect()
    }

    private func configureWebView() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        config.allowsAirPlayForMediaPlayback = true
        config.allowsPictureInPictureMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.defaultWebpagePreferences.allowsContentJavaScript = true

        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.backgroundColor = .black
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.allowsBackForwardNavigationGestures = true
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
    }

    private func configureOverlay() {
        overlay.axis = .vertical
        overlay.spacing = 16
        overlay.alignment = .center
        overlay.translatesAutoresizingMaskIntoConstraints = false

        activity.color = .white
        message.numberOfLines = 0
        message.textAlignment = .center
        message.textColor = .white
        message.font = .systemFont(ofSize: 15, weight: .medium)

        let retry = UIButton(type: .system)
        retry.setTitle("重新连接", for: .normal)
        retry.addTarget(self, action: #selector(connect), for: .touchUpInside)

        let settings = UIButton(type: .system)
        settings.setTitle("后端服务器", for: .normal)
        settings.addTarget(self, action: #selector(editServer), for: .touchUpInside)

        overlay.addArrangedSubview(activity)
        overlay.addArrangedSubview(message)
        overlay.addArrangedSubview(retry)
        overlay.addArrangedSubview(settings)
        view.addSubview(overlay)

        NSLayoutConstraint.activate([
            overlay.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            overlay.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            overlay.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor, constant: -48)
        ])
    }

    @objc private func connect() {
        overlay.isHidden = false
        webView.isHidden = true
        activity.startAnimating()
        message.text = "Plove 4.0\n正在启动…"

        LocalWebAppServer.shared.start { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let url):
                self.homeURL = url
                self.webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30))
            case .failure(let error):
                self.showError(error.localizedDescription)
            }
        }
    }

    private func showError(_ text: String) {
        activity.stopAnimating()
        overlay.isHidden = false
        webView.isHidden = true
        message.text = text + "\n\n后端：" + AppConfiguration.apiBaseURL.absoluteString
    }

    @objc private func editServer() {
        let alert = UIAlertController(
            title: "Plove 4 后端地址",
            message: "填写 API 根地址，例如 http://192.168.10.71:4001",
            preferredStyle: .alert
        )
        alert.addTextField { field in
            field.text = AppConfiguration.apiBaseURL.absoluteString
            field.keyboardType = .URL
            field.autocapitalizationType = .none
            field.autocorrectionType = .no
        }
        alert.addAction(UIAlertAction(title: "取消", style: .cancel))
        alert.addAction(UIAlertAction(title: "保存并重载", style: .default) { [weak self, weak alert] _ in
            guard let self else { return }
            let value = alert?.textFields?.first?.text ?? ""
            guard AppConfiguration.setAPIBaseURL(value) else {
                self.showError("服务器地址格式无效")
                return
            }
            self.webView.configuration.websiteDataStore.removeData(
                ofTypes: [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache],
                modifiedSince: .distantPast
            ) {
                self.connect()
            }
        })
        present(alert, animated: true)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        activity.stopAnimating()
        overlay.isHidden = true
        webView.isHidden = false
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        showError("页面加载失败：" + error.localizedDescription)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        showError("页面连接中断：" + error.localizedDescription)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        connect()
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        let localHost = homeURL?.host
        if navigationAction.targetFrame?.isMainFrame == true,
           url.host != nil,
           url.host != localHost,
           ["http", "https"].contains(url.scheme?.lowercased() ?? ""),
           navigationAction.navigationType == .linkActivated {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        guard let url = navigationAction.request.url else { return nil }
        if url.host == homeURL?.host {
            webView.load(navigationAction.request)
        } else if ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
            UIApplication.shared.open(url)
        }
        return nil
    }
}
