# 三个目标站侦察报告

> 状态：**实测数据，非推测**。用于决定第一个爬虫从哪个站开始。
> 侦察方式：真实浏览器加载 + 同源 `fetch` 取原始 HTML / JSON（绕开渲染，等价于 Python 请求看到的内容）。
> 结论会直接决定 `crawler_kit` 需要哪些能力，以及第一阶段能省掉多少工作量。

---

## 一、总览

| | **2048ai.vip** | **ncat21.com** | **rou.video** |
| --- | --- | --- | --- |
| 站点类型 | 短剧平台 | 影视聚合（maccms 系） | 视频站（Cloudflare） |
| 数据形态 | **纯 JSON API** | SSR HTML | SSR HTML + 自定义 API |
| 列表 | `GET /api/v1/short-dramas?productId=1&sortBy=heat&page=1&size=12` | `.v-item` 卡片 | `.v-item` 类卡片，链接 `/v/{cuid}` |
| 详情 | `GET /api/v1/short-dramas/{id}?productId=1` | `GET /detail/{id}.html` | `GET /v/{cuid}` |
| 播放地址 | **详情响应里直接给** | **播放页 HTML 里直接给** | 需调 API，**响应加密** |
| 加密 | API 无；HLS 流 **AES-128** | 无（但 JS 混淆） | **有**（base64 + 位移） |
| 反爬 | 无（仅 deviceId 埋点） | **cdndefend 闸门 + 反调试** | Cloudflare |
| 解析难度 | ★☆☆☆☆ | ★★☆☆☆ | ★★★★☆ |
| **建议顺序** | **第 1 个** | 第 2 个 | 第 3 个 |

**一句话结论：先从 `2048ai.vip` 开始。** 它是唯一一个"不用解析 HTML、不用解密、不用过闸门"的源，能最快打通"协议 → 后端 → 前端"整条链路，把风险集中留到后面处理。

---

## 二、2048ai.vip（首选）

### 2.1 站点形态

- 原始 HTML 只有 **2.4KB**，纯 SPA（Vite 打包，`/assets/index-*.js`）→ **所有数据走 API**
- 备用域名：`madouai.xyz`
- 前端路由：`/media/videos?categoryId=N`、`/media/short-dramas/{id}/episodes/{n}`、`/media/search?mode=latest`、`/media/short-dramas/rankings`

### 2.2 已探到的 API 清单

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/categories?type=video` | 分类树 |
| GET | `/api/v1/menus?productId=1` | 导航菜单 |
| GET | `/api/v1/short-dramas/home?productId=1` | 首页聚合 |
| GET | `/api/v1/short-dramas?productId=1&sortBy=heat&page=1&size=12` | **列表（分页）** |
| GET | `/api/v1/short-dramas/{id}?productId=1` | **详情 + 剧集 + 播放路径** |
| GET | `/api/v1/short-dramas/{id}/related?productId=1&limit=6` | 相关推荐 |
| GET | `/api/v1/short-dramas/rankings` | 榜单 |
| GET | `/api/v1/short-dramas/directors?productId=1&homeOnly=true&size=5` | 导演/演员 |
| GET | `/api/v1/comments?videoId=20562&page=1&size=20` | 评论（可选） |
| GET | `/api/v1/site-settings?productId=1` | 站点配置 |
| GET | `/api/v1/ads?productId=1&position=home_bottom_popup` | 广告位（**要过滤**） |
| POST | `/api/v1/track/page-view` | 埋点（**不要调**） |

### 2.3 详情响应真实样例（去掉无关字段）

```json
{ "code": 200, "message": "ok",
  "data": {
    "id": 249,
    "title": "2048原创短剧 - 我是爸爸的新妻子",
    "description": "我是爸爸的新妻子",
    "coverUrl": "/uploads/images/7baf35bba6cd4e688cbf733faf3d9406.jpg",
    "rating": 9.4,
    "episodeSegmentSize": 20,
    "episodeCount": 7,
    "heatCount": 1354523,
    "publishedAt": "2026-09-28T17:22:42",
    "episodes": [
      { "videoId": 20562, "episodeNo": 1,
        "title": "我是爸爸的新妻子第一集", "titleOverride": null,
        "videoUrl": "jpd/20260928/1o/b6/bj/bf/430846dc47884812bbebfb601e8e15e8.m3u8",
        "orientation": null, "sourcePlatform": "gossip", "durationSec": 262 }
    ]
  } }
```

### 2.4 关键判断

- **`vod_id` 用 `id`（数字）即可**，站内唯一、可复现，不需要"用完整路径当 id"的兜底方案。
- **播放走站点自己的代理，不需要 CDN 基址**（已实测解开）：

  ```
  GET https://2048ai.vip/api/v1/m3u8/proxy?path=<urlencode(videoUrl)>
  → 200, application/vnd.apple.mpegurl
  ```

  代理返回的清单里，分片是带 `auth_key` 的**限时签名地址**，域名是会轮换的
  CDN（实测 `acfan.ymkizv84.work`，形如
  `.../x.ts?auth_key=1790678497-<md5>-0-<md5>`）。所以：
  - **不要硬编码 CDN 域名**，也不要去逆 auth_key —— 一律通过站点代理拿；
  - **播放地址不可缓存**，每次播放现取（`auth_key` 里的时间戳就是当前时间）。

  这意味着这个站的 `mode` 是 **`direct`**：**第一版不用做后端流代理**，
  直接把这个 URL 交给前端即可（架构文档第十节里那条最大取舍，这里有了答案）。
- **`sourcePlatform`（如 `gossip`）** 是播放源标识，归一化时可以丢掉或映射成"线路"。
- **`rating` 有真实值（9.4）**，可以保留；注意参考项目后期"彻底废除打分机制"，这里要和你确认要不要。
- 列表分页是标准 `page`/`size`，`has_more` 可以直接用 `page*size < total` 推。

---

## 三、ncat21.com（第 2 个）

### 3.1 站点形态

- 网飞猫，maccms 衍生模板（静态资源在 `vf.esadj.com/vod_pc_static_ncat/`）
- **服务端渲染**：首页原始 HTML 260KB，直接含 81 个 `.v-item` 卡片
- 引了 `crypto-js`、`Auth.min.js`、`disable-devtool`、`domainTransformer.js` → JS 整体混淆（`_0x1956` 这类）

### 3.2 已确认的页面结构

| 用途 | 路径 / 选择器 |
| --- | --- |
| 详情 | `/detail/{vod_id}.html` |
| 播放 | `/play/{vod_id}-{线路}-{剧集id}.html` |
| 频道 | `/channel/{n}.html` |
| 榜单 | `/ranking/index.html` |
| 标签 | `/label/new.html` |
| 搜索 | `/search?k={关键词}&t={token}` ← **需要 token** |
| 卡片 | `.v-item` / `.module-item` |
| 剧集列表 | `.episode-list-box-main > .episode-list`（**每个线路一个 div，默认 `display:none`**） |
| 单集 | `a.episode-item[data-index]`，内部 `<span>` 是画质（`1080P`/`HD国语`/`TC`） |

### 3.3 播放地址真实样例（**直接写在播放页 HTML 里，无需解密**）

```
.../26090913/1_318185_2946232/1920/index.m3u8?appId=ncat&sign=0768be52947634e0bff486940db23e13&timestamp=1790678284&ref=0
```

`timestamp=1790678284` 对应的正是当前时间 —— **签名服务端现签、短时效**。这直接印证架构文档那条"播放地址绝不入库"：每次播放都必须重新抓播放页。

### 3.4 两个真门槛

1. **`cdndefend` 反爬闸门**：不带 cookie 请求详情页，服务器返回 **HTTP 状态码 850** + 一个 6.5KB 的挑战页。挑战页内嵌一份 **SHA-1 实现**，前端算出 `cdndefend_js_cookie`（实测值 44 位十六进制，形如 `A337D1EB9CCD6D599AE51019BD471B92F7245FE149882`）。
   → Python 侧必须复刻这个 SHA-1 计算逻辑，或者"人工过一次闸门、把 cookie 存下来复用"。
2. **反调试**：加载详情页后主线程被 `disable-devtool` 锁死，自动化渲染直接卡死。
   → **反面教材**：说明"用 Playwright 渲染"这条路对这个站是下策；**纯 HTTP + 复刻 cookie** 才是正解，反而更快。

> 好消息：闸门只卡在 cookie 上。过了之后列表、详情、播放页全是纯 SSR，一行 JS 都不用执行。

### 3.5 另外三个实测发现（都已固化进工具箱）

1. **广告水印用 Unicode 变体字伪装。** 详情页标题实际是
   `𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 最糟糕的初恋 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞` —— `kkys01.com` 的数学粗体写法。
   关键词过滤完全抓不到，只能按字符区间整块删（`clean.strip_decorated`）。
   列表页另有 `display:none` 的隐藏水印节点（`parse.visible`）。
2. **列表页封面有两张 `<img>`**：第一张是 `logo_placeholder_vertical.png` 占位图，
   第二张的 `data-original` 才是真封面。不排占位图的话所有封面都是同一个 logo。
3. **播放地址可能是主清单（master）而不是媒体清单。** 实测
   `vip.ffzy-plays.com/.../index.m3u8` 只有 97 字节：

   ```
   #EXTM3U
   #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=800000,RESOLUTION=1920x1080
   3000k/hls/mixed.m3u8
   ```

   这是合法的 HLS 主清单，hls.js 原生支持，变体 URI 是相对路径。
   **验收断言不能只认 `#EXTINF`**，否则会把正常的主清单误判成失败。
4. **失败会伪装成超时。** 取数途中出现过 `handshake operation timed out`，
   当时归因为"被源站按 IP 限流"，**后来证实是环境的 DNS 出口被整体关掉了**
   （两个目标站同时被解析到 `127.145.0.x`，而 2048ai 十分钟前还正常）——
   那次归因是错的。但教训成立：限流与网络故障在客户端是同一个现象，
   日志必须记全（状态码 / 耗时 / 次数），别只记一句超时。
   `Client` 为此提供 `min_interval`，默认不限速（0），由站点按需设保守值。

### 3.6 对设计的直接影响

- **多线路撞车**：同一部剧有多个线路，每个线路的 `data-index` 都从 1 开始。架构文档里"用完整路径当 id"的建议在这里**必须落实**，否则线路 1 的第 1 集和线路 2 的第 1 集会互相覆盖。
- **搜索需要 token**：`t=` 参数。第一版可以先把 `search` 标记为**不支持**（能力清单里去掉），别在这里死磕。

---

## 四、rou.video（第 3 个）

### 4.1 站点形态

- 广告：肉視頻；Cloudflare 在后面
- 原始 HTML **380KB**（SSR，直接含数据），但外壳是 Vite SPA（`/assets/index-gjPQr8vf.js`）
- 详情链接 `/v/{id}`，**id 是 25 位 cuid**（如 `cmu2ctdht002kmufw11pjzpyp`），不是数字
- 自定义 API：`/api/pulse`、`/api/tile`

### 4.2 难点

- **播放地址需要额外调 API，且响应加密**。参考项目里那个 `decryptRouVideo(d, k)`（base64 解码后逐字符减去 k，再 `JSON.parse`）就是为它写的 —— 说明这个加密确实存在，而且方案比较土（位移密码），可逆。
- 详情页 HTML 里有 `s=!h.JS_SHA1_NO_NODE_JS` 这类 SHA-1 代码痕迹，可能也有请求签名。
- Cloudflare 在前面，需要处理 CF 的挑战/UA 校验。

### 4.3 判断

**这是三个站里最难的**，放最后。适合的阶段是"`crawler_kit` 已经成熟、需要验证它对加密源的支持能力"时再上。

---

## 五、对 `crawler_kit` 的影响（侦察的直接产出）

跑完三个站，公共能力清单变得很具体：

| 模块 | 必须提供 | 因为哪个站 |
| --- | --- | --- |
| `http` | 自定义 cookie 注入 | ncat21 |
| `http` | 自定义 UA + Referer | rou.video / ncat21 |
| `http` | **非 2xx / 非标准状态码也要能读到响应体** | ncat21（850） |
| `http` | JSON 与 HTML 统一入口 | 三站都有 |
| `parse` | CSS 选择器（scrapling/parsel） | ncat21 / rou.video |
| `parse` | **正则从整页里抠 m3u8** | ncat21（无 DOM 结构可依） |
| `clean` | 相对 URL → 绝对 URL（含 CDN 基址拼接） | 2048ai.vip / ncat21 |
| `clean` | **广告/引流域名过滤** | 三站都有（2048ai 的 `.cc` / `.top` 一堆） |
| `clean` | 画质标签归一化（`1080P`/`HD国语`/`TC`） | ncat21 |
| `log` | 统一 stderr | 全部 |

**清晰的反面示范**：参考项目把这些启发式直接复制进每个适配器（连 `cleanHtmlNoise`、`isCoverPlaceholder` 都是从 sniffer 里 import 进适配器的），结果每个站都得重来一遍。新架构里它们必须在 `crawler_kit` 里只有一份。

---

## 六、待确认 / 未解

- [x] ~~2048ai.vip 的 CDN 基址~~ —— **已解开**：走 `/api/v1/m3u8/proxy`，无需拼 CDN。
- [x] ~~跨域播放~~ —— **已实测，整条链都开放**，前端可直连，**不需要后端流代理**（详下）。
- [ ] **`search` 接口**：仍未找到，已在能力清单里标掉，不阻塞。

### 2.5 播放链实测结论（前端能否直连）

决定"要不要做后端流代理"的完整证据链：

| 环节 | 实测结果 |
| --- | --- |
| m3u8 代理 | `HTTP 200`、`Content-Type: application/vnd.apple.mpegurl`、`access-control-allow-origin: *`、`allow-headers: Range, Content-Type`、预检 `OPTIONS` 返回 200 且 `max-age=3600` |
| 清单形态 | **媒体清单**（非主清单），138 行 / 66 个分片，**分片 URI 全是绝对地址**（无需重写） |
| 分片 | `HTTP 206`（支持 Range）、`access-control-allow-origin: *`、`allow-expose-headers: *`、单分片约 3.3MB、`server: go-cdn-server` |
| 加密 | **`#EXT-X-KEY:METHOD=AES-128`**，密钥在第三个域名上；密钥接口返回 **16 字节**（长度正确）且 CORS 放行 |

所以：

1. **`hls.js` 直接 `loadSource(play.url)` 就能播**，不需要代理、不需要重写清单、
   不需要注入 Header。分片是绝对地址，AES-128 由 hls.js 自动取密钥解密。
2. **「第一版不做后端流代理」成立**（针对这个源）。架构文档里那个最大的
   工作量取舍，这里可以划掉一半。
3. **IV 全零** → hls.js 会按标准用媒体序号当 IV，正常行为，不用特殊处理。
4. 唯一小瑕疵：分片的 `Content-Type` 是 `text/vnd.trolltech.linguist`（源站配错了）。
   hls.js 按清单类型判定 demuxer，不看这个头，所以不影响；但如果以后换别的播放器，
   这就是第一个要查的地方。

> **这条经验要固化：每接入一个源，必须验证「清单 + 分片 + 密钥」三者的 CORS，
> 否则前一句"支持直连"很可能是错的。** 只测清单是最容易骗过自己的测法。
- [x] ~~ncat21 的 `cdndefend`~~ —— **已完整逆向并实测通过**。算法是暴力找一个让
      `SHA-1(secret + i)` 摘要第 10、11 字节等于 `0xB0 0x0B` 的计数器（实测 i=49882，
      **Python 33 毫秒**出结果），算出的 cookie 与浏览器值逐字符一致，带上它详情页返回 200。
      **不需要浏览器、不需要 Playwright**。实现见
      [\u722c\u866b/sites/ncat21.py](../\u722c\u866b/sites/ncat21.py) \u7684 `solve_cdndefend`\uff0c
      \u901a\u7528\u6d41\u7a0b\u5728 [\u722c\u866b/crawler_kit/gate.py](../\u722c\u866b/crawler_kit/gate.py)\u3002
- [ ] **`rating` 要不要保留**：2048ai 有真实评分（9.4），参考项目后期把评分机制废掉了。
- [ ] **多线路怎么建模**：ncat21 有多个线路，`episodes` 是平铺，还是按线路分组？（建议加一个可选的 `line` 字段）
- [ ] **第一版要不要做 `search`**：ncat21 需要 token，2048ai 的 `/media/search` 还要再探一次。
- [ ] 三个站的**内容合法性/授权**由你自己把关，本报告只解决技术可行性。
