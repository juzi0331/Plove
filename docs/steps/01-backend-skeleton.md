# 步骤 1 · 后端骨架 + 契约 + 统一信封

> 完成：2026-09-30 ｜ 代码：[backend/](../../backend/)
> 验证：`44 passed` · `契约一致（12 个）` · `GET /api/v1/health -> 200`

---

## 〇、先回答那个疑问：这个 API 到底是什么，凭什么要有它

你在这一步之后问了一句很关键的话：**"为啥要一个这样的 API，直接做可视化面板不是更简洁吗？"**
这一节专门回答，因为搞不清它，后面每一步都会觉得别扭。

### 1. API 不是界面，它是"数据从哪来"

把整个系统想成一家餐厅：

| 角色 | 对应什么 |
| --- | --- |
| 餐厅大堂、菜单、服务员 | 你要的**可视化面板**（用户网页 / 后台管理） |
| **收银台下单的那个窗口** | **API** |
| 后厨 | 后端业务逻辑（编排、缓存、鉴权） |
| 供货商 | 源站（2048ai、ncat21） |
| 采购员 | 爬虫 |

**客人不会自己冲进后厨炒菜。** 面板也不会自己去源站抓数据——它只跟 API 说话。
"面板"和"API"不是二选一，是**点菜的人**和**下单窗口**，两层。

### 2. 那能不能干脆不要这个窗口，让面板直接抓源站？

不能。会撞三堵墙，这三堵墙全都有实测证据，不是推测：

**墙一：CORS —— 浏览器不许。**
浏览器里的网页不能随便请求别的域名。我们在 [site-recon.md](../site-recon.md) 实测过：
2048ai 的清单/分片/密钥三个环节 CORS 全开（所以它**可以**直连），
但 **ncat21 没有**。也就是说"面板直接抓"这条路，在目标站里已经有一个走不通。

**墙二：反爬闸门 —— 浏览器里跑不动。**
ncat21 前面有一道 `cdndefend` 闸门：不带 cookie 请求返回 **HTTP 850** 和挑战页，
得先暴力找出一个让 SHA-1 摘要特定两字节命中的计数器，才算得出 cookie。
这个计算在服务端跑 **33 毫秒**；再加上站点还挂了 `disable-devtool`，
你在浏览器里一开开发者工具，主线程直接被锁死。后面的 `rou.video` 播放响应还是加密的，
同样得在服务端解。

**墙三：泄露 —— 这堵最要命。**
爬虫逻辑要是写在前端页面里，**任何人按 F12 就能看到全部抓取代码**，
包括怎么过闸门、怎么解密。而这个项目的核心诉求就是**防泄露**——
激活码是为它，单会话也是为它。把爬虫放进前端，等于把秘诀贴在门口。

这也是为什么后端从一开始就定为**方案 B：服务端爬虫，前端只调统一 API**。

### 3. 而且"面板"根本不止一个

| 谁 | 什么时候做 |
| --- | --- |
| 用户端网页（Vue3） | 阶段 2 |
| 后台管理面板（Vue3 + Element Plus） | 阶段 4 |
| 本地爬虫生成器（小网页） | 最后阶段 |
| ipa 里的 WebView | 最后一步 |

要是每个都自己去抓源站、自己归一化字段、自己处理超时和熔断，同样的逻辑得复制四份。
API 把这四份收成一份。

### 4. Swagger（`/docs`）不等于"面板"

怕被误解，单独说清：Swagger 是 FastAPI **白送的调试窗口**，不是产品界面。

| | Swagger（`/docs`） | 真正的面板（Vue3） |
| --- | --- | --- |
| 给谁用 | **只有你自己开发时** | 用户 / 运营 |
| 权限 | 没有 | 激活码 / admin token |
| 长相 | 自动生成的表单 | 你要设计的界面 |
| 现在有吗 | ✅ 白送的 | ❌ 还没做 |

它唯一的用处是"零成本验证后端"——一分钟内就能看到信封长什么样，靠的就是它。

### 5. 什么情况下"不要这层"才是对的

如果目标只是**自己看一个源**，那确实一个爬取脚本 + 一个页面就够了，中间那层是多余的。

但这个项目的目标是：**多个源 + 激活码 + 单会话 + 10Mbps 的 VPS + ipa 只打包一次**。
这些复杂度不会消失，只会从"有隔离的后端"挪进浏览器，然后撞上上面三堵墙。

一句话：**后端不是多出来的一层，它是抓取、归一化、鉴权这三件事唯一能待的地方。**

---

## 一、这一步干了什么

搭出后端的**地基**，并且把"三端说同一套话"这件事用机制锁死：

| 交付物 | 位置 | 作用 |
| --- | --- | --- |
| 统一信封 | [backend/app/schemas/envelope.py](../../backend/app/schemas/envelope.py) | 所有响应一个外形，前端只写一套解析 |
| 统一错误码 | [backend/app/core/errors.py](../../backend/app/core/errors.py) | 爬虫的错翻译成 `UPSTREAM_*`，前端不认爬虫那套 |
| 契约唯一来源 | [backend/app/schemas/](../../backend/app/schemas/) | Pydantic 模型，导出成 JSON 给另外两端 |
| 契约生成物 | [contracts/schemas/](../../contracts/schemas/) | 12 个 JSON Schema，前端与爬虫读它 |
| 应用骨架 | [backend/app/main.py](../../backend/app/main.py) | 只组装，不写业务 |
| 测试 | [backend/tests/](../../backend/tests/) | 44 个用例 |

---

## 二、现在这个后端实际能干什么

说实话：**只有一个接口。** 因为它目前只是地基，还没有接上爬虫。

### 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查。返回服务状态、环境、版本 |
| GET | `/docs` | Swagger 面板（开发时点着用） |
| GET | `/openapi.json` | 机器可读的接口描述，可导入 Postman / Apifox |
| GET | `/api/v1/*`（未注册的路径） | 统一返回 `404` + 失败信封 |

### 统一信封

所有响应都是这四个键，一个不多一个不少：

```json
{ "ok": true,  "data": { "status": "ok", "env": "dev", "version": "0.1.0" },
  "error": null, "request_id": "dc6682a5f73144f3b7f6826c305d461a" }
```

```json
{ "ok": false, "data": null,
  "error": { "code": "NOT_FOUND", "message": "接口或资源不存在", "detail": null },
  "request_id": "386515fd52a9403f9246d93ca010bbe4" }
```

**为什么是这个形状？** 因为它和爬虫的命令行信封**同构**（爬虫那侧也有 `ok`/`data`/`error`），
只多一个 `request_id`。好处是整条链路只有一种信封，前端写一套拆包 + 一套错误处理。

### `request_id` 是干什么的

每个请求分配一个 id，同时出现在**响应体**和**响应头 `X-Request-Id`** 里。

它的用途是**追问题**：出问题时，从网关日志里搜这个 id，能看到这一路发生了什么。
等接上爬虫以后，这个 id 还会跟着传到爬虫的 stderr——所以一个 id 能串起整条链路。
（客户端自己带了 `X-Request-Id` 就沿用，方便 App 与前端之间也串起来。）

### 错误码表

前端判断错误分支就靠这张表。分三类：

**上游（爬虫）的错，一律翻译成 `UPSTREAM_*`：**

| 爬虫给的 | 网关对外 | HTTP |
| --- | --- | --- |
| `TIMEOUT` | `UPSTREAM_TIMEOUT` | 504 |
| `HTTP_ERROR` | `UPSTREAM_HTTP_ERROR` | 502 |
| `PARSE_ERROR` | `UPSTREAM_PARSE_ERROR` | 502 |
| `BLOCKED` | `UPSTREAM_BLOCKED` | 503 |
| `UNKNOWN` | `UPSTREAM_UNKNOWN` | 502 |
| `NOT_FOUND` | `NOT_FOUND` | 404 |
| `UNSUPPORTED` | `UNSUPPORTED` | 501 |

**本端的错：** `BAD_REQUEST`(400) · `VALIDATION_ERROR`(422) · `UNAUTHORIZED`(401) ·
`FORBIDDEN`(403) · `RATE_LIMITED`(429) · `NOT_FOUND`(404)

**业务（激活码 / 单会话）：** `ACTIVATION_INVALID`(403) · `ACTIVATION_EXPIRED`(403) ·
`SESSION_KICKED`(409)

**兜底：** `NOT_IMPLEMENTED`(501) · `INTERNAL`(500)

### 契约是什么

[contracts/schemas/](../../contracts/schemas/) 里有 12 个 JSON Schema 文件，
描述"每种数据长什么样"：`vod-item`（影片卡片）、`episode`（单集）、
`playback`（播放地址）、`site-meta`（站点元信息）等等。

**它不是手写的，是从 Pydantic 模型导出出来的生成物。** 规矩是：

```
backend/app/schemas/*.py  （唯一来源，改这里）
        ↓  python tools/export_contracts.py
contracts/schemas/*.json  （生成物，提交进仓库）
        ↓
前端生成 TS 类型 ｜ 爬虫用标准库做最小校验
```

为什么事实源必须是"能落成文件"的东西？因为**爬虫被硬约束为只准用标准库**
（不装第三方包），它 import 不了 Pydantic，只能读 JSON 文件。

---

## 三、怎么验证

### 1. 自动化测试

```powershell
cd E:\Pychon-code\NY\Plove1.0\backend
.\.venv\Scripts\python.exe -m pytest -v
```

必须用 `.venv` 里的 python（系统那个是 3.14，没装依赖）。

### 2. 手动点

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

浏览器开 <http://127.0.0.1:8000/docs> → 点 `GET /api/v1/health` →
**Try it out** → **Execute**，看 Response body 与 Response headers。

再手敲一个不存在的地址 <http://127.0.0.1:8000/api/v1/nope>，
确认**框架自己的 404 也走信封**（这很关键，否则前端会遇到"有的错是 JSON、有的错是 HTML"）。

### 3. 契约有没有过期

```powershell
.\.venv\Scripts\python.exe tools\export_contracts.py --check
```

改了模型忘了导出就会报出来——测试里也有一条 `test_contracts_on_disk_are_not_stale` 盯着。

---

## 四、分层规矩（后面每一步都要守）

```
api  →  services  →  crawler / db  →  models
                       ↘  schemas  ↗
        core（最内层，谁都能用）
```

| 目录 | 职责 | 硬规矩 |
| --- | --- | --- |
| `app/api/` | 薄路由 | 只声明参数与转发，**不写业务** |
| `app/services/` | 业务编排 | **不 import fastapi**，能脱离 HTTP 单测 |
| `app/crawler/` | 子进程调度 | **唯一**接触爬虫的地方 |
| `app/models/` | ORM（数据库形状） | 不泄漏到 API |
| `app/schemas/` | Pydantic（接口形状） | 契约唯一来源 |
| `app/core/` | config · logging · errors · 中间件 · 异常处理 | 不反向依赖 |

三条纪律：**一文件一职责**；**依赖单向**；**每个 service 配一个 pytest**。

---

## 五、这一步**没有**做什么（边界）

| 没做 | 因为 |
| --- | --- |
| 数据库（MySQL） | 骨架阶段不需要；按你的选择"先不接数据库" |
| `app/services/`、`app/models/` 目录 | 等各自有第一份真实内容再落地，先不堆空壳 |
| 任何真实业务接口 | 还没有爬虫 runner，接了才有数据 |
| 激活码 / 单会话 | 属于后面的阶段 |
| 流代理 | 已实测两个目标源都 `direct` 可直连，第一版不做 |

---

## 六、下一步

**步骤 2：接上爬虫** —— 写子进程 runner（硬超时 + 解析单行 JSON）和站点注册表，
让 `home` / `category` / `detail` / `play` 真的能返回数据。
见 [02-crawler-integration.md](02-crawler-integration.md)。
