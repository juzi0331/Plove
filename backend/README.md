# 后端 —— 网关

FastAPI。只做三件事：**定义契约**、**编排爬虫**、**发统一信封**。

## 分层与依赖方向

```
api  →  services  →  crawler / cache / db  →  models
                          ↘  schemas  ↗
        core（最内层，谁都能用）
```

| 目录 | 职责 | 硬规矩 |
| --- | --- | --- |
| `app/api/` | 薄路由 | 只声明参数与转发，**不写业务** |
| `app/services/` | 业务编排 | **不 import fastapi**，所以能脱离 HTTP 单测 |
| `app/crawler/` | 子进程调度 + 每站守护 | **唯一**接触爬虫的地方，别处不知道爬虫是进程 |
| `app/cache/` | 缓存原语 + 内容缓存策略 | 只有通用原语，**不含业务知识**（不认识爬虫） |
| `app/models/` | ORM（数据库形状） | 不要泄漏到 API |
| `app/schemas/` | Pydantic（接口形状） | 契约的唯一来源，导出成 `contracts/schemas/*.json` |
| `app/core/` | config · logging · errors · 中间件 · 异常处理 | 不反向依赖上面任何一层 |

一文件一职责：`vod.py` 只放 vod 相关，不搞 `utils.py` 大杂烩。

## 目录

```
app/
  main.py            只组装：建 app、挂中间件、注册异常处理、挂路由
  contracts.py       把 Pydantic 模型导出成 contracts/schemas/*.json
  core/
    config.py        PLOVE_* 环境变量
    clock.py         时间：存库 naive UTC，出接口 aware UTC
    logging.py       统一日志（只写 stderr）
    errors.py        统一错误码 + AppError + HTTP 状态映射
    middleware.py    每个请求一个 request_id
    handlers.py      异常 → 统一失败信封
    scheduler.py     极简周期任务（一个线程，用于定时预热）
  db/                base · session · schema
  models/            ORM（数据库形状）：activation · device
  schemas/           Pydantic（接口形状）= 契约唯一来源
  cache/             ttl（TTL+LRU）· singleflight（防击穿）· content（内容缓存策略）
  crawler/           runner · registry · guard · validate
  services/          catalog · site · activation · warmup（主动预热）
  api/v1/            薄路由：health · activation · sites · catalog · admin
  api/deps.py        get_db · require_device · require_admin · get_registry · get_content_cache
tools/
  _common.py              公共引导（路径 + UTF-8）
  export_contracts.py     契约导出 CLI
  init_db.py              建表 / 查连通性
  issue_code.py           签发激活码
tests/               一模块一测试
```

## 数据库

线上是 MySQL，本地/测试是 SQLite，靠 SQLAlchemy 切换。连接串写在 `.env`：

```ini
PLOVE_DATABASE_URL=mysql+pymysql://plove:密码@192.168.1.10:3306/plove?charset=utf8mb4
```

**表结构只用可移植类型**（不用 JSON 列、排序规则、前缀索引这类 MySQL 专有特性），
否则必然出现"本地绿、线上炸"。规矩写在 [app/db/__init__.py](app/db/__init__.py)。

真库验证（可选）：设 `PLOVE_TEST_DATABASE_URL` 后跑 `pytest -m mysql`。

## 缓存与稳定性

| 机制 | 默认 | 一句话 |
| --- | --- | --- |
| 首页缓存 | 600s | 分类树/推荐几乎不变，却要 fork 一次子进程 |
| 分类 / 详情缓存 | 300s | 会随新片变化，但不需要秒级 |
| 播放地址 | **永不缓存** | m3u8 带时效签名，缓存等于把失效地址发给用户 |
| 防击穿 | 同 key 只放一个 | 缓存挡不住"刚好过期那一瞬间"的并发 |
| 每站并发上限 | 2 | 抢不到槽位就排队，排太久回 `UPSTREAM_BUSY` |
| 熔断 | 连败 5 次 / 冷却 60s | 冷却完放**一个**探针试探 |

**还有一个"主动预热"**（`PLOVE_WARMUP_ENABLED`，默认关）：定时把每个源的
首页 + 前几个分类重新抓一遍填进缓存。因为 TTL 是**被动过期** —— 到点后由
**下一个来访者**触发重抓、由**他**承担几秒等待，而且没人来的话数据会一直旧着。
推荐组合：**周期 24 小时 + TTL 25 小时**。

参数全在 `.env`（见 [.env.example](.env.example)）。**TTL 设成 0 就是关掉那一类缓存。**

两个容易搞错的地方：

* **`NOT_FOUND` / `UNSUPPORTED` 不算源站故障**，不计入熔断 —— 它们是"正确的回答"。
  否则用户点几个失效链接就能把整个源熔断掉。
* **`meta` 只走并发限流，不参与熔断判定**。它每请求必经、又被缓存、
  还可能拿旧值顶替，让它参与计数会把内容失败的计数一次次清零，
  结果就是"meta 能通、抓内容就超时"的源永远熔断不掉。

## 跑起来

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # macOS / Linux

.venv/Scripts/python tools/init_db.py            # 建表（用 .env 里的库，默认本地 SQLite）
.venv/Scripts/python tools/issue_code.py --days 30   # 发一个激活码

.venv/Scripts/python -m uvicorn app.main:app --reload
.venv/Scripts/python -m pytest
.venv/Scripts/python tools/export_contracts.py
```

跑起来之后，**所有内容接口都要带 ``X-Device-Token``**：
先去 `/docs` 调 `POST /api/v1/activation/redeem` 拿令牌，再用它访问 `/api/v1/sites`。

打开 <http://127.0.0.1:8000/docs> 可以直接点接口。

## 后台接口

```
GET  /api/v1/admin/status            缓存 + 每个源的健康 + 上次预热的结果
POST /api/v1/admin/cache/refresh     手动跑一轮；?wait=true 会等它跑完
```

用 `X-Admin-Token`（`.env` 里的 `PLOVE_ADMIN_TOKEN`），与激活码是**两套凭证**：
激活码管"谁能看内容"，它管"谁能管这台机器"。

**没配令牌就一律拒绝**（403）—— 空令牌必须永远不能通过，否则一个忘了配变量的
部署就等于把后台裸奔在公网上。比较用 `secrets.compare_digest`（防时序侧信道）。

这两个接口已经能用；**界面**属于后面的阶段（见 [../PROGRESS.md](../PROGRESS.md)）。

## 已经立住的两条约定

**统一信封**：所有响应都是 `{ok, data, error, request_id}`，
与爬虫命令行信封同构，只多一个 `request_id`。
前端只写一套错误处理，排查时用 `request_id` 从网关日志串到爬虫 stderr。

**错误码单一来源**：`core/errors.py` 里的 `ErrorCode`。
爬虫的 `TIMEOUT`/`HTTP_ERROR`/`PARSE_ERROR`/`BLOCKED` 一律翻译成 `UPSTREAM_*`，
前端不需要知道爬虫长什么样。测试会直接读爬虫那侧的码表比对，防止两端漂移。
