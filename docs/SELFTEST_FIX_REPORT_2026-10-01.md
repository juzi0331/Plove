# Plove 4.0 自测与修复报告（2026-10-01）

## 1. 本轮范围

本轮针对 Windows 本地 `plove4.0` 进行完整回归，覆盖：

- 后端 FastAPI / SQLAlchemy 全量测试
- 前端 TypeScript 类型检查与生产构建
- 爬虫工坊测试
- 站点注册与 `/api/v1/sites`
- 首页、分类、详情、播放链路
- 后台站点配置与本地 SQLite
- 重部署后 `.env` 默认配置行为

## 2. 已修复问题

### 2.1 空目录配置导致前台“0 个站点”

**现象**

`.env.example` 中：

```ini
PLOVE_CRAWLER_DIR=
PLOVE_CONTRACTS_DIR=
```

Pydantic 会把空字符串解析为 `Path('.')`，导致后端实际扫描 `backend/sites`，而不是仓库根目录下的 `crawler/sites`。

**后果**

- `ai2048.py`、`ncat21.py`、`xiaoyakankan.py` 明明存在，前台却显示 0 个可用站点。
- 后台上传采集器时还可能被写入错误目录。

**修复**

在 `backend/app/core/config.py` 增加字段校验：
- 空字符串 / 纯空白 `PLOVE_CRAWLER_DIR` 自动回退到 `PROJECT_DIR / "crawler"`
- 空字符串 / 纯空白 `PLOVE_CONTRACTS_DIR` 自动回退到 `BACKEND_DIR / "contracts"`

并新增 `backend/tests/test_config.py` 回归测试。
### 2.2 分类权限检查存在无条件 403

**现象**

`backend/app/services/site_control_service.py` 的 `check_category_allowed()` 中存在错误缩进：

在遍历第一条分类规则后，会无条件执行：

```python
raise AppError(ErrorCode.FORBIDDEN, ...)
```

因此只要后台保存过分类规则，即使分类 `hidden=false`，用户访问分类仍可能被拒绝。

**修复**

删除无条件 `raise`，仅在目标一级分类或二级分类明确标记 `hidden=true` 时返回 403。

并新增 `backend/tests/test_category_rules.py`，覆盖：
- 可见分类不会被误拒绝
- 隐藏分类仍会正确返回 FORBIDDEN

## 3. 回归结果

### 3.1 后端

- 全量 `pytest -q`：通过
- 2 个真实 MySQL 条件测试按预期跳过
- 新增配置与分类规则回归测试均通过
- 仅有 Starlette TestClient / httpx 的弃用警告，不影响运行

### 3.2 爬虫工坊

- `crawler/service/tests`：8 passed
- 无失败项

### 3.3 前端

- `npm run typecheck`：通过
- `npm run build`：通过
- Vite 仅提示 `hls.js` chunk 约 594 KB，属于包体积优化告警，不是功能错误

## 4. 真实运行链路验证

### ai2048

- 站点注册：正常
- 首页：正常
- 分类：正常
- 详情：正常
- 播放地址解析：正常
- 实测首页：23 个分类、22 个推荐

### xiaoyakankan

- 站点注册：正常
- 首页：正常
- 分类：修复后正常
- 详情：正常
- 播放地址解析：正常
- 实测首页：57 个分类、60 个推荐
### ncat21（网飞猫）

**当前状态：上游 TLS 兼容性风险，未伪装为“已修复”。**

现象：
- 同一台 Windows 上，`curl/Schannel` 可在约 1 秒内连到 `www.ncat21.com` 并收到 HTTP 850 防护页；
- Python `urllib` / `httpx` 使用 OpenSSL 时，TLS 握手会间歇性或持续超时；
- 在 Mac 上用 Python 也能复现同类 TLS 握手超时；
- 多个网飞猫备用域名测试同样存在 Python/OpenSSL 握手问题。

结论：
- 不是 `ncat21.py` 的 HTML 解析规则失效；
- 不是 Windows 单机网络故障；
- 当前更像源站 TLS 重协商与 Python/OpenSSL 的兼容性问题。

处理：
- 未通过简单增加全局超时冒充修复；
- 已验证将单站超时放宽到 35 秒仍会失败，只会增加用户等待时间，因此恢复默认超时；
- 保留现有熔断、超时和换源机制。

## 5. 部署状态

当前 Windows 本地：

- 前端：`http://192.168.0.232:4000/`
- 后端 / Portal：`http://192.168.0.232:4001/`
- 爬虫工坊：`http://127.0.0.1:8088/`
- SQLite 数据库继续保留
- `.env` 可继续保持 `PLOVE_CRAWLER_DIR=` 和 `PLOVE_CONTRACTS_DIR=` 空值，源码会自动回退到正确目录

## 6. 本轮源码变更

- `backend/app/core/config.py`
- `backend/app/services/site_control_service.py`
- `backend/tests/test_config.py`
- `backend/tests/test_category_rules.py`
- `docs/SELFTEST_FIX_REPORT_2026-10-01.md`

## 7. 后续建议

1. 为 `ncat21` 单独研究兼容 TLS 重协商的 HTTP 传输层，不建议用无限延长超时替代。
2. 后续可把 `hls.js` 改成播放器路由按需加载，降低首包体积。
3. CI 中固定保留“空 `.env` 路径回退”与“分类显隐权限”两组回归测试，防止再次出现前台 0 站点或分类全部 403。
