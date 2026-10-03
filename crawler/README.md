# crawler —— 采集层

一个站点一个文件，全部走统一的命令行协议与 JSON 信封。
与 [crawler-plan.md](../docs/crawler-plan.md)（细则）、[architecture.md](../docs/architecture.md)（总纲）、
[site-recon.md](../docs/site-recon.md)（站点侦察）配套。

## 目录

```
crawler/
  crawler_kit/          工具箱：本地与线上同源同版本
    __init__.py
    errors.py           统一错误码 + CrawlerError
    log.py              只写 stderr 的日志
    http.py             超时/重试/Cookie/非标准状态码/限速/代理
    gate.py             反爬闸门（自定义状态码 + 前端算 cookie）的通用解法
    parse.py            HTML 树 + CSS 子集 + 隐藏节点过滤 + 正则抠 m3u8
    clean.py            URL/文本/数字/变体字清洗 + 广告域名过滤
    cli.py              参数解析 + 统一信封 + 异常兜底 + UTF-8 强制
  sites/
    ai2048.py           2048ai.vip（纯 JSON API，无反爬）
    ncat21.py           网飞猫（SSR + cdndefend 闸门 + 多线路）
  tests/
    fixtures/<key>/     页面/接口快照（离线测试用）
    test_kit.py         工具箱单测
    test_ai2048.py      站点单测
    test_ncat21.py      站点单测（含闸门全流程）
    smoke_live.py       联网冒烟测试（不在离线套件里）
```

**硬约束：站点文件只允许 `import crawler_kit` + Python 标准库。** 用不了
parsel/lxml，所以 CSS 选择器是自己实现的一个子集（见
[crawler_kit/parse.py](crawler_kit/parse.py) 顶部说明）。

## 命令

```
python sites/<key>.py meta                                    # 站点元信息 + 能力清单
python sites/<key>.py home                                    # 首页分类 + 推荐
python sites/<key>.py category --tid <分类id> --page 1
python sites/<key>.py search   --kw <关键词> --page 1
python sites/<key>.py detail   --id <影片id>
python sites/<key>.py play     --id <影片id> --ep <集号> [--line <线路号>]
python sites/<key>.py selftest                                # 结构指纹（自检）
```

* **`ep` 与 `ep_index` 都是 1 起算的集号**（不是数组下标）。
* **`line` 是多线路源用的**：同一部剧有多条播放线路时，各线路的集号会重复，
  必须靠 `--line` 指定走哪条。

## 信封

```json
{ "ok": true,  "data": { }, "error": null }
{ "ok": false, "data": null, "error": { "code": "PARSE_ERROR", "message": "剧集列表为空" } }
```

* **stdout 只输出一行 JSON**，日志与栈一律走 stderr（`CRAWLER_LOG=debug` 调级别）。
* **退出码永远是 0**，失败用 `ok:false` 表达；超时由调用方 kill。
* 错误码：`TIMEOUT` / `HTTP_ERROR` / `PARSE_ERROR` / `NOT_FOUND` / `BLOCKED` /
  `UNSUPPORTED` / `UNKNOWN`。
  **"该源不支持搜索"必须和"搜到 0 条"区分开**，不允许返回空列表蒙混。
* stdout 写死 **UTF-8**。Windows 上 `sys.stdout.encoding` 默认是 GBK，
  不强制转换的话后端按 UTF-8 解析中文必然炸。

## 运行

```bash
cd crawler

# 离线单元测试（不联网）
python -m unittest discover -s tests -t .

# 联网冒烟测试：真的去抓，并验证 play 的地址能拉回合法 m3u8
python tests/smoke_live.py ai2048
python tests/smoke_live.py ncat21
```

## 已接入站点

| key | 站点 | 形态 | mode | 反爬 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `ai2048` | 2048ai.vip | 纯 JSON API | `direct` | 无 | 播放走站点自带 `/api/v1/m3u8/proxy`；清单/分片/密钥 CORS 全开 |
| `ncat21` | ncat21.com | SSR HTML | `direct` | **cdndefend 闸门** | 多线路；播放页 HTML 里直接有带签名的 m3u8 |

站点文件名即 key，须匹配 `[a-z0-9_]{2,64}` 且不能以数字开头
（所以 `2048ai.vip` 用 `ai2048`）。

## 这三条经验是踩出来的，不要重复踩

### 1. 闸门是"暴力"，不是"解密"

`cdndefend` 的挑战页内嵌一段 SHA-1，逻辑瘦下来就四行：

```js
let c = '<40 位十六进制 secret>';   // 硬编码在挑战页里，每页都可能轮换
let n1 = parseInt('0x' + c[0]);     // 取首字符当十六进制数
for (let i = 0; ; i++) {
  let s = sha1(c + i).array();
  if (s[n1] === 0xb0 && s[n1 + 1] === 0x0b) { document.cookie = 'cdndefend_js_cookie=' + c + i; break; }
}
```

就是暴力找一个让摘要特定两字节命中的计数器，期望约 6.5 万次。
Python 实测 **33 毫秒**出结果，与浏览器算出的 cookie 逐字符一致。

**结论：这类闸门不要上 Playwright。** 站点还挂了 `disable-devtool`，
自动化渲染会被锁死主线程；而纯 HTTP + 复刻算法又快又稳。
求解器必须**从挑战页现解析 secret**，不能写死。

### 2. 广告水印会用 Unicode 变体字

ncat21 的详情页标题是：

```
𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 最糟糕的初恋 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞
```

`𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞` 是真域名 `kkys01.com` 的**数学粗体**写法，关键词匹配完全抓不到。
`clean.strip_decorated()` 按字符区间整块删掉"含有变体字符的那个词"，
不会误伤正常标题。列表页另有 `display:none` 的隐藏水印节点，
由 `parse.visible()` / `Node.is_hidden` 处理。

### 3. 失败会伪装成超时

抓取中途出现过 "TLS handshake operation timed out"。当时先怀疑是被源站按 IP 限流，
**后来发现是环境的 DNS 出口被整体关掉了**（两个目标站同时被解析到 `127.145.0.x`）。
所以那次的归因是错的。

但结论依然成立且值得保留：**限流与网络故障在客户端看是同一个现象**，
光看异常信息分不出"被限流"和"网线掉了"。`Client` 因此提供 `min_interval`
（默认 0，不偷偷限速；由站点按需设一个保守值，`ncat21` 是 1 秒/次），
日志里也应当把状态码、耗时、次数都记下来，别只记一句超时。

## 待办

* [ ] `rou.video`：列表是 SSR，但播放响应加密（base64 + 位移），排在最后。
* [ ] `search`：两个源都还没做（ncat21 要 `t=` token，ai2048 未找到接口），
      已在能力清单里标掉，不阻塞。
* [ ] 断点式的限流自适应：被限流后退避并记住冷却时间，而不是固定间隔。
