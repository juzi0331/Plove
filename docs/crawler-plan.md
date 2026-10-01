# 爬虫开发计划（阶段 1）

> 状态：**讨论中，未定稿**。定稿后再动手写代码。
> 范围：只解决一件事——**本地能跑、命令行能测、输出统一结构的 Python 爬虫**。
> 不做：可视化生成器、数据库、调度、并发、m3u8 代理、前端。

---

## 一、阶段 1 的三个交付物

| 交付物 | 内容 | 谁用它 |
| --- | --- | --- |
| **运行协议** | 命令行参数约定 + stdout 只输出 JSON + stderr 放日志 | 后端调度、你自己调试 |
| **工具箱 `crawler_kit`** | 网络请求、HTML 解析、数据清洗、日志，打包成一个可安装的小包 | 所有爬虫 |
| **样例爬虫** | 一个真实站点的完整实现 + 测试 | 后面所有爬虫的模板 |

**关键约束：工具箱必须"本地和后端同源同版本"**——本地 `pip install -e`，服务器 `pip install` 同一个包同一版本号。否则必然出现"本地绿、上传炸"。

---

## 二、运行协议

### 2.1 命令

```
python <站点>.py meta
python <站点>.py home
python <站点>.py category --tid <分类id> --page 1
python <站点>.py search   --kw <关键词>  --page 1
python <站点>.py detail   --id <影片id>
python <站点>.py play     --id <影片id> --ep <集索引>
# 可选加速通道：详情里每集都带 play_id，原样回传可让 play 跳过"先抓一遍详情页"
python <站点>.py play     --play-id <详情里给的play_id>
```

### 2.2 统一信封（所有命令的输出都是这个外形）

```json
{ "ok": true,  "data": { }, "error": null }
{ "ok": false, "data": null, "error": { "code": "PARSE_ERROR", "message": "剧集列表为空" } }
```

- **stdout 只允许一行 JSON**，任何 `print` 调试、异常栈一律走 stderr。这条是硬规矩：否则一句调试输出就会污染 JSON，后端解析直接失败。
- 爬虫**正常退出码永远是 0**，失败也用 `ok:false` 表达。超时/被杀由后端负责（超时 → 子进程被 kill）。
- 错误码统一：`TIMEOUT` / `HTTP_ERROR` / `PARSE_ERROR` / `NOT_FOUND` / `BLOCKED` / `UNKNOWN`。

### 2.3 各命令的 data 结构

**meta** — 站点元信息

```
{ key, name, version, base_url, mode: "direct" | "proxy" }
```

`mode` 表示播放时是直连源站还是必须走后端代理（防盗链/被墙的站标 proxy）。

**home** — 首页分类 + 推荐

```
{ categories: [ { tid, name } ], recommend: [ VodItem ] }
```

**category / search** — 列表（结构完全一致，前端可复用）

```
{ videos: [ VodItem ], page, has_more }
```

**detail** — 详情 + 剧集列表

```
{ video: VodItem, desc,
  episodes: [ { ep_index, ep_name, play_id, line?, duration_sec? } ],
  lines:    [ { line, name, count } ] }        // 多线路源才有
```

``ep_index`` 是 **1 起算的集号**，不是数组下标；多线路源的集号会**重复**，
必须靠 ``line`` 区分 —— 所以 ``play_id`` 建议用完整路径（见 2.4 那个坑）。

**play** — 播放地址

```
{ url, format: "m3u8" | "mp4", headers: { } }
```

`headers` 用来带防盗链所需的 `Referer` / `User-Agent`，前端直连或后端代理时都要用上。

#### `--play-id`：一个可选的加速通道

`detail` 里每集都带着 `play_id`，调用方（后端/前端）可以把它**原样回传**给
`play`，源就**不必为了找到某一集而重新抓一遍详情页**。

这是一个**可选**参数：不传就退回老路径（自己调 `detail` 去找），行为不变、只是慢一点。
实测 ncat21 靠它把播放从 **7.249 秒降到 3.981 秒**。

两条实现要求：

1. **必须校验它。** 这个值是上层回传的，而 `play` 会拿它直接去 `fetch` ——
   一个绝对 URL 就能让爬虫变成任意地址的抓取代理（SSRF）。
   用 `clean.safe_relative_path()` 收敛：必须是站内相对路径，
   并且拒掉 `//evil.example/x`（**协议相对**，只检查"以 / 开头"正好会放它过去）
   与含反斜杠的值。不合法就**退回慢路径**，不要报错。
2. **不要把它当整数。** 它是长这样的：`/play/369061-41-4969745.html`。
   （`cli.INT_OPTIONS` 里刻意没有它。）

### 2.4 VodItem（全站强制统一，前端只写一套卡片 UI）

> 下文的字段在**后端契约**里更完整（还有 `vod_category` / `vod_year` 等）。
> 权威版本永远是 `contracts/schemas/*.json`，它们由 `backend/app/schemas/` 导出。

必填：`vod_id`、`vod_name`、`vod_pic`、`vod_remarks`
可选：`vod_year`、`vod_area`、`vod_type`、`vod_actor`、`vod_score`

> ⚠️ 最容易踩的坑：`vod_id` 必须**站内唯一且在 detail/play 时可复现**。很多站的 id 藏在 URL 里，建议直接用"完整路径"当 id，而不是从 URL 里正则抠一个数字——后者很容易在分页/多线路时撞车。

---

## 三、工具箱 `crawler_kit`

| 模块 | 提供的能力 |
| --- | --- |
| `http` | `get()/post()`，带超时、自动重试、自动补 Referer、可选走代理 |
| `parse` | CSS / XPath 选择器（基于 parsel） |
| `clean` | 去广告/引流关键词、提取 m3u8、相对 URL 转绝对 URL、去空白 |
| `log` | 统一写 stderr 的日志函数 |

**硬约束：爬虫只能 import `crawler_kit` + Python 标准库**，不允许 import 任意第三方库、不允许读写文件、不允许直接开 socket。

理由有三条：① 服务器上不需要为每个爬虫准备依赖；② 后端做白名单校验时有明确边界；③ 保证本地和线上能力完全一致。

---

## 四、开发步骤（每步都能单独验证）

| 步 | 做什么 | 怎么验证 |
| --- | --- | --- |
| 1.1 | 建目录骨架 + 工具箱第一步（http + parse + log） | 用**保存下来的 HTML 快照**做 pytest，不联网也能测 |
| 1.2 | 定义 VodItem 等结构 + 一个校验函数 | 塞假数据：合规通过，缺字段报错 |
| 1.3 | 写 CLI 入口（参数解析 + 统一信封 + 异常兜底） | 用一个**假爬虫**（返回写死的 JSON）跑全部 6 个命令，都输出合规信封 |
| 1.4 | 人工分析目标站的列表页 / 详情页 / 播放页 | 在浏览器开发者工具里定位到"剧集列表"和"m3u8 地址" |
| 1.5 | 实现 `home` + `category` | 命令行能拿到分类树和影片列表 |
| 1.6 | 实现 `search` + `detail` | 能搜到片、能拿到完整剧集列表 |
| 1.7 | 实现 `play` | 命令行吐出的 m3u8 地址用播放器/VLC 能播 |
| 1.8 | 异常与稳定性 | 站点 404 / 超时 / 结构变化时输出 `ok:false` 而不是崩栈 |
| 1.9 | 手写第 2、3 个爬虫 | 记录"哪些代码在重复"，形成生成器的需求清单 |

**1.1 ~ 1.3 完全不碰真实网站**，先把骨架和协议打通。这样后面遇到的每一个问题都只可能是"站点相关"的，不会和骨架问题混在一起。

---

## 五、文件约定

```
crawler_kit/                     # 工具箱：本地和后端同源同版本
  __init__.py  http.py  parse.py  clean.py  log.py
crawlers/
  <站点key>.py                   # 一个站点一个文件，文件本身尽量短
tests/
  fixtures/<站点key>/*.html      # 页面快照（离线测试用）
  test_<站点key>.py              # 每个爬虫配一个测试
```

---

## 六、风险与对策

| 风险 | 对策 |
| --- | --- |
| 站点改版导致爬虫失效 | 用 HTML 快照做测试 + 校验函数，结构变了会**明确报错**，而不是静默返回空列表 |
| m3u8 藏在 JS 里拿不到 | 第一版允许用正则从页面/脚本里抠；实在抠不到就换站，不要在这里死磕 |
| 防盗链 | `play` 返回 `headers`，前端直连时带上；带不动就标 `mode: "proxy"` 交给后端 |
| 影片 id 不稳定 | 用完整路径当 id |
| 测试依赖目标站在线 | 全部用本地 HTML 快照测试，只有"冒烟测试"才真联网 |

---

## 七、阶段 1 验收标准

对同一个目标站**连续跑 3 次**，每次都满足：

1. `meta` 返回正确的站点信息
2. `home` / `category` 能拿到分类和影片列表，字段齐全
3. `search` 能搜到指定片名
4. `detail` 能拿到完整剧集列表
5. `play` 至少拿到一集**能真正播放**的 m3u8 地址
6. 故意构造一个错误场景，能输出 `ok:false` 而不是崩栈

达不到这个标准，不往下走（不进后端）。

---

## 八、待确认项

- [ ] 目标站先用哪个？先拿一个简单公开站练手，还是直接上最终要用的站？
- [ ] `play` 的粒度：一次给一集，还是一次给整部剧？
- [ ] 是否接受上面的"统一信封"结构？
