import UIKit
import WebKit

enum AppConfiguration {
    static let serverURL = URL(string: "http://189.24.77.252:4002/")!
    static let healthURL = URL(string: "http://189.24.77.252:4002/api/v1/health")!
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
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
    private var requestGeneration = 0

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

        overlay.addArrangedSubview(activity)
        overlay.addArrangedSubview(message)
        overlay.addArrangedSubview(retry)
        view.addSubview(overlay)

        NSLayoutConstraint.activate([
            overlay.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            overlay.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            overlay.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor, constant: -48)
        ])
    }

    @objc private func connect() {
        requestGeneration += 1
        let generation = requestGeneration
        overlay.isHidden = false
        webView.isHidden = true
        activity.startAnimating()
        message.text = "Plove 4.0\n正在连接服务器…"

        var request = URLRequest(url: AppConfiguration.healthURL)
        request.timeoutInterval = 12
        request.cachePolicy = .reloadIgnoringLocalCacheData

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self, self.requestGeneration == generation else { return }
                let http = response as? HTTPURLResponse
                let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
                let ok = (json?["ok"] as? Bool) == true

                guard error == nil, http?.statusCode == 200, ok else {
                    self.showError("Plove 4.0 服务器暂时无法连接。")
                    return
                }

                self.webView.load(
                    URLRequest(
                        url: AppConfiguration.serverURL,
                        cachePolicy: .reloadIgnoringLocalCacheData,
                        timeoutInterval: 30
                    )
                )
            }
        }.resume()
    }

    private func showError(_ text: String) {
        activity.stopAnimating()
        overlay.isHidden = false
        webView.isHidden = true
        message.text = text + "\n\n" + AppConfiguration.serverURL.absoluteString
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        activity.stopAnimating()
        overlay.isHidden = true
        webView.isHidden = false
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
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

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }

        let isHttp = ["http", "https"].contains(url.scheme?.lowercased() ?? "")
        let sameHost = url.host == AppConfiguration.serverURL.host
        let samePort = url.port == AppConfiguration.serverURL.port

        if navigationAction.targetFrame?.isMainFrame == true,
           isHttp,
           !(sameHost && samePort),
           navigationAction.navigationType == .linkActivated {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        decisionHandler(.allow)
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        guard let url = navigationAction.request.url else { return nil }
        let sameServer = url.host == AppConfiguration.serverURL.host
            && url.port == AppConfiguration.serverURL.port

        if sameServer {
            webView.load(navigationAction.request)
        } else if ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
            UIApplication.shared.open(url)
        }
        return nil
    }
}
