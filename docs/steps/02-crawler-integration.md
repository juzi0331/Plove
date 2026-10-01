# 步骤 2 · 接上爬虫

> 完成：2026-09-30 ｜ 代码：[backend/app/crawler/](../../backend/app/crawler/) ·
> [backend/app/services/](../../backend/app/services/) · [backend/app/api/v1/](../../backend/app/api/v1/)
> 验证：`70 passed` · `契约一致（13 个）` · 真实源四条链路全通

---

## 一、这一步干了什么

把后端从"只有健康检查的空壳"变成**真的能返回数据**：
从 HTTP 请求进来到爬虫子进程跑完、错误被翻译、结果过契约校验，这条链路打通了。

| 交付物 | 位置 | 作用 |
| --- | --- | --- |
| 子进程执行器 | [runner.py](../../backend/app/crawler/runner.py) | 跑爬虫、卡硬超时、解析单行 JSON 信封 |
| 站点注册表 | [registry.py](../../backend/app/crawler/registry.py) | 有哪些源、源的 meta 与能力、**能力路由** |
| 契约校验 | [validate.py](../../backend/app/crawler/validate.py) | 把爬虫输出塞进模型，**不合格就拒收** |
| 业务编排 | [catalog_service.py](../../backend/app/services/catalog_service.py) | 首页 / 列表 / 详情 / 播放 / 搜索 |
| 路由 | [api/v1/](../../backend/app/api/v1/) | 8 个接口，薄到只有转发 |
| 假爬虫 | [tests/fixtures/fake_crawler/](../../backend/tests/fixtures/fake_crawler/) | 不联网也能把整条链路测完 |

---

## 二、现在有哪些接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/sites` | 站点列表（含每个源的能力清单） |
| GET | `/api/v1/sites/{key}` | 单个站点信息 |
| GET | `/api/v1/sites/{key}/home` | 首页：分类 + 推荐 + 板块 |
| GET | `/api/v1/sites/{key}/category?tid=&page=` | 分类列表 |
| GET | `/api/v1/sites/{key}/search?kw=&page=` | 搜索（目前两个源都返回 `UNSUPPORTED`） |
| GET | `/api/v1/sites/{key}/detail?vod_id=` | 详情 + 剧集 + 线路 |
| GET | `/api/v1/sites/{key}/playback?vod_id=&ep=&line=` | 播放地址 |

`{key}` 就是爬虫文件名：`ai2048`、`ncat21`。

**id 全部走查询参数，不走路径段。** 因为 `vod_id` 的约定是"可复现的定位符"，
多线路源会用**完整路径**当 id，路径段里塞斜杠要额外转义、还容易被反向代理改写。

---

## 三、数据是怎么流动的

以一次播放为例：

```
浏览器
  │  GET /api/v1/sites/ncat21/playback?vod_id=369061&ep=1&line=1
  ▼
路由 catalog.py           ← 只声明参数，转发
  ▼
服务 catalog_service.py   ← 检查 mode、按契约校验、翻译错误
  ▼
注册表 registry.py        ← 先查能力清单：ncat21 会 play 吗？会 → 放行
  ▼
执行器 runner.py          ← fork 子进程，卡硬超时
  ▼
python crawler/sites/ncat21.py play --id 369061 --ep 1 --line 1
  │  （过 cdndefend 闸门 → 抓详情页 → 抓播放页 → 抠 m3u8）
  │  stdout 一行 JSON：{"ok":true,"data":{...},"error":null}
  ▼
runner 解析 → 注册表返回 → 服务过 Playback 契约 → 套信封
  ▼
{"ok":true,"data":{"url":"…","format":"m3u8","headers":{"Referer":"…"}},"error":null,"request_id":"…"}
```

**这就是上一份文档里那三堵墙的落地方式**：浏览器只跟我们的 API 说话，
爬虫、闸门、解密全在服务端的子进程里，F12 看不到任何抓取逻辑。

---

## 四、三个关键设计

### 1. 子进程 + 硬超时 —— 稳定性隔离

爬虫**永远不跑在 API 进程里**。威胁模型不是"防恶意代码"，而是
**"别让某个爬虫卡死拖垮全站"**。

要命的一点：**超时是调用方的责任，不是爬虫的责任**。爬虫不知道我们多有耐心，
所以 `runner.py` 到点直接 kill，翻译成 `UPSTREAM_TIMEOUT`(504)。
测试 `test_hung_crawler_hits_the_hard_timeout` 就是让假爬虫睡 60 秒，
验证我们能在上限内把它掐死。

### 2. 能力路由 —— "不支持"不能伪装成"没有"

`meta` 命令声明了这个源会什么。源没声明 `search`，网关就必须**明确报错**：

```json
{"ok":false,"data":null,"error":{"code":"UNSUPPORTED","message":"网飞猫 不支持 search"},…}
```

而不是返回一个空列表。因为"**该源不支持搜索**"和"**搜到 0 条**"对用户是
完全不同的两件事，混成空列表的话用户在体验上根本分不清。

对爬虫的硬约束也在这里受益：不认识的能力直接拒掉，不给它机会乱来。

### 3. 契约拒收 —— 绝不"凑合入库"

爬虫的输出必须过 Pydantic 校验，不合格就是 `UPSTREAM_PARSE_ERROR`(502)，
并且 `detail` 里明确指出**错在哪个字段**：

```json
{"code":"UPSTREAM_PARSE_ERROR","message":"fake 的 home 输出不符合契约（2 处）",
 "detail":[{"loc":"recommend.0.vod_id","msg":"Field required","type":"missing"}]}
```

这样"源站改版了"会在**日志里变成一条明确的报错**，而不是让用户对着空白页猜。

---

## 五、真实实测结果

不是推测，是真跑出来的（2026-09-30）：

| 源 | home | detail | playback | 播放耗时 |
| --- | --- | --- | --- | --- |
| `ai2048` | 23 个分类 / 22 条推荐 | 7 集 / 0 条线路 | ✅ m3u8 | **1.0s** |
| `ncat21` | 5 个分类 / 77 条推荐 | 18 集 / **18 条线路** | ✅ m3u8（带 Referer） | **4.1s** |

---

## 六、这一步踩到的两个坑（都修了）

### 1. `__init__.py` 被当成了一个站点

`SITE_KEY_PATTERN` 是 `^[a-z_][a-z0-9_]{1,63}$`，而 `__init__` **首字符是下划线，
恰好能通过**。不特判的话扫目录会把它当成一个源，然后去执行它。

修法：`keys()` 里显式跳过下划线开头的文件。

### 2. 播放超时 5 秒太紧 —— 而且只有实测才看得出来

最初按"元数据 3s / 播放 5s"设的。实测发现 `ncat21` 的播放要 **4.1 秒**，
5 秒贴着边，网络一抖就 504（第一轮真跑就翻车了）。

**为什么这么慢**：`ncat21` 的 `play` 内部会**先调一次自己的 `detail()`** 去定位
`play_id`，再加上它自带 1 秒的主动限速，一个播放请求要跑 2~3 次网络往返。
而 `ai2048` 的播放只要 1 秒（详情响应里直接带地址）。

修法：按实测把超时定成 `10s`（元数据）/ `12s`（播放），并在配置里写清依据，
防止以后有人"凭感觉调小"。

> **这里留了个真正的优化空间**：前端其实已经调过 `detail`、手里就有 `play_id` 了，
> 完全可以让后端把 `play_id` 直接传给 `play`，省掉那次重复抓取。
> 但那要改爬虫的命令行协议（`--id/--ep/--line` → `--play-id`），
> 属于下一步的事，记在这里。

---

## 七、怎么验证

```powershell
cd E:\Pychon-code\NY\Plove1.0\backend
.\.venv\Scripts\python.exe -m pytest -v          # 70 个用例，含 12 个接口端到端
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

然后开 <http://127.0.0.1:8000/docs>，现在里面有 8 个接口可以点。

**注意**：Swagger 里点的是**真实源站**，会真的联网抓取，`ncat21` 的接口要等 4 秒左右。

---

## 八、这一步**没有**做什么

| 没做 | 为什么 |
| --- | --- |
| 缓存 | 列表/详情每次都真抓。缓存是下一步的事，先把链路打通 |
| 并发上限 / 熔断 | 现在只有一个用户（你）在点，还不需要 |
| 结构指纹自检 | 爬虫侧的 `selftest` 命令已经有了，但还没接进网关 |
| 流代理 | 两个源都实测 `direct` 可直连，第一版不做 |
| 真实源的 `search` | 两个源都没实现，接口存在但明确返回 `UNSUPPORTED` |
| 激活码 / 单会话 | 后面的阶段 |

---

## 九、下一步

**步骤 3：缓存与稳定性** —— 列表/详情加两级缓存（防击穿）、并发上限、
连续失败熔断、把爬虫的 `selftest` 接进来做结构指纹告警。
（或者按你的节奏先做激活码与单会话。）
