# Plove 4.0 自测与修复报告（2026-10-01）

## 本轮范围

针对 Windows 本地 `plove4.0` 完成前后端、爬虫、站点注册和真实内容链路回归，并将可安全合并到稳定分支 `pl` 的修复同步到本分支。

覆盖：

- 后端 FastAPI / SQLAlchemy 全量测试
- 前端 TypeScript 类型检查与生产构建
- crawler/service 测试
- 站点注册与 `/api/v1/sites`
- 首页、分类、详情、播放链路
- 后台站点配置与 SQLite
- 重部署后空 `.env` 路径行为

## 已修复：空路径导致前台 0 个站点

`.env.example` 允许：

```ini
PLOVE_CRAWLER_DIR=
PLOVE_CONTRACTS_DIR=
```

空字符串如果直接交给 `Path`，可能被解析为当前目录，导致后端扫描错误的 sites 目录。

本次在 `backend/app/core/config.py` 增加 Pydantic `field_validator`：

- 空或纯空白 `PLOVE_CRAWLER_DIR` → `PROJECT_DIR / "crawler"`
- 空或纯空白 `PLOVE_CONTRACTS_DIR` → `BACKEND_DIR / "contracts"`

并新增 `backend/tests/test_config.py`，防止重新部署后再次出现“0 个站点”。

## 分类权限回归保护

Windows 上基于 `main` 的自测曾发现分类权限逻辑会误拒绝正常分类。当前 `pl` 分支的 `check_category_allowed()` 已采用按目标 tid 精确判断的实现，没有该无条件拒绝问题，因此本次没有用 `main` 的整份 `site_control_service.py` 覆盖 `pl`。

为防止后续回归，新增 `backend/tests/test_category_rules.py`，固定验证：

- 已保存规则后，可见分类仍允许访问
- `hidden=true` 的分类继续返回 FORBIDDEN

这样既保留 `pl` 当前稳定实现，也把这次发现的问题纳入持续回归。

## 回归结果

Windows 本地本轮验证结果：

- 后端全量 `pytest -q`：通过；2 个真实 MySQL 条件测试按预期跳过
- `crawler/service/tests`：8 passed
- 前端 `npm run typecheck`：通过
- 前端 `npm run build`：通过
- Vite 仅提示 hls.js chunk 约 594 KB，属于包体积优化告警，不是功能错误

## 真实源验证

### ai2048

- 注册：正常
- 首页：正常
- 分类：正常
- 详情：正常
- 播放地址解析：正常
- 自测时首页约 23 个分类、22 个推荐

### xiaoyakankan

- 注册：正常
- 首页：正常
- 分类：正常
- 详情：正常
- 播放地址解析：正常
- 自测时首页约 57 个分类、60 个推荐

### ncat21

当前仍存在上游 TLS 兼容性风险：

- Windows curl/Schannel 可以连接并收到源站 HTTP 850 防护页
- Python urllib/httpx 使用 OpenSSL 时会在 TLS 握手阶段超时
- Mac Python 环境也复现同类握手超时
- 多个备用网址也出现类似 Python/OpenSSL 握手问题

因此没有通过单纯增加超时时间来伪装修复。将单站超时放宽到 35 秒后仍失败，只会增加等待时间，故继续使用默认超时和现有熔断/换源机制。

## 稳定分支同步内容

本次 `pl` 分支同步：

- `backend/app/core/config.py`
- `backend/tests/test_config.py`
- `backend/tests/test_category_rules.py`
- `docs/SELFTEST_FIX_REPORT_2026-10-01.md`

没有上传：

- `.env`
- SQLite 数据库
- 日志
- `.venv`
- `node_modules`
- 其他运行态文件

## 后续建议

1. 为 ncat21 单独研究兼容 TLS 重协商的传输实现，不用无限延长超时替代。
2. 后续可将 hls.js 做播放器路由按需加载，降低首包体积。
3. CI 固定保留“空路径回退”和“分类显隐权限”回归测试。
