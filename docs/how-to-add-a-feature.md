# 加功能怎么做

> 这份文件是**给下一个对话窗口看的**：想加东西时，先读它，再动手。
>
> 这个项目有一条"固定动作"链，漏哪一步，测试就会红、或者前后端悄悄对不上。
> 链本身不长，但要**按顺序**走。

---

## 零、先选路线

| 我想做的事 | 从哪开始 | 要不要动契约 |
| --- | --- | --- |
| 加一个**内容**接口（用户端能调的） | [一、后端加一个新接口](#一后端加一个新接口固定的-8-步) | ✅ 要 |
| 加一个**后台**接口（运维能点的） | 上面的 8 步 + [二、后台的额外规矩](#二后台接口的额外规矩) | ✅ 要 |
| 接一个**新源站** | `crawler/sites/<key>.py` + `crawler/README.md` | ❌ 不用（源对上层透明） |
| 调界面 / 加页面 | [三、前端](#三前端如果这次要动) | 只在接口形状变了时 |
| 改部署 / 上线 | `deploy/CHECKLIST.md` · `deploy/BT-PANEL.md` | ❌ |

**判断"要不要动契约"最快的办法：** 只要**响应或请求的形状**变了（加字段、改类型、加接口），
契约就得动。只改内部实现、SQL、算法 —— 不用。

---

## 一、后端加一个新接口：固定的 8 步

### 1. 先定形状：写 Pydantic 模型

文件：`backend/app/schemas/<域>.py`

**顺序很重要：先写模型，再写实现。** 契约是唯一事实源，
先定形状能强迫自己想清楚"前端到底要拿到什么"，而不是让实现反推形状。

字段上要带 `description`（会进契约和前端注释），有约束就用 `Field(ge=..., le=...)`。
带默认值的字段到了前端会变成**可选**属性（`xxx?`），这是刻意的。

### 2. 登记契约：改 `EXPORTS`

文件：`backend/app/schemas/__init__.py`

两处都要加：`__all__` 列表 和 `EXPORTS` 字典。

**规矩：内层类型也单独导出。** 不要只导出最外层 payload ——
嵌套类型不导出的话，前端只能给内层自己手写一份 interface，
那两份就会各自漂移，而漂移起来**不会有任何报错**。

### 3. 导出生成物（**这一步不能忘**）

```bash
cd backend
./.venv/Scripts/python.exe tools/export_contracts.py
```

`contracts/schemas/*.json` 是**生成物**，跟着一起提交。
忘了跑，`tests/test_contracts.py::test_contracts_on_disk_are_not_stale` 会红 ——
那是故意的：它防的就是"模型改了、三端还照着旧 JSON 干活"。

### 4. 写 service

文件：`backend/app/services/<域>_service.py`

两条硬规矩：

* **不 `import fastapi`** —— service 要被脚本（`tools/`）和测试直接调，
  不能因为"想抛 `HTTPException`"就把 Web 框架拖进来。要报错就抛 `AppError`（带 `ErrorCode`）。
* **不 `commit`** —— 事务边界归 `get_db`（见第 5 步的例外）。

### 5. 写路由

文件：`backend/app/api/v1/<域>.py`

```python
router = APIRouter(tags=["xx"], dependencies=[Depends(require_device)])  # 守卫挂 router 上
```

* **守卫挂在 router 上，不要塞进每个路由函数。** 加新接口时才不会忘记加鉴权 ——
  忘记加鉴权是这类系统最常见的事故。
* **写操作必须在返回前 `commit_now(db)`。** 因为 `get_db` 的 `commit()` 跑在
  **响应送出之后**，客户端拿到 200 立刻发的下一个请求可能读到旧值。
  真实事故：点完"停用"列表还是旧值；点"在此设备继续"后第一个请求仍然 409。
* 响应一律包 `ok(data, request_id)`。

### 6. 写测试

文件：`backend/tests/test_<域>.py`

夹具都在 `tests/conftest.py`：`db_engine` / `db_factory` / `db_session` /
`fake_settings` / `fake_app` / `anon_client` / `authed_client` / `activation` / `crawler_counter`。

三条规矩：

1. **不联网、不碰真数据库。** 爬虫走 `tests/fixtures/fake_crawler`，库走临时 SQLite 文件。
2. **不依赖开发机上的 `.env`。** 要什么配置就在夹具里**显式钉死**
   （`fake_settings` 里 `admin_token=""` 就是这么来的）。
3. 断言重点放在**副作用是否精确**，而不是"接口返回 200"。

### 7. 跑测试

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest        # 期望 201 passed, 2 skipped
cd ../crawler && ../backend/.venv/Scripts/python.exe -m pytest   # 期望 97 passed
```

### 8. 写文档 + 同步数字

* **改契约 / 改行为** → 在 `docs/steps/` 里新开一份编号文档（格式照抄上一份：
  做了什么 / 为什么 / 现在能干什么 / 怎么验证 / **没做什么** / 下一步）。
  改的只是小东西就写进**现有**那一份。顺手在 `docs/steps/README.md` 的清单加行。
* **改数字** → 同步 `PROGRESS.md` 顶部那段"验证数字"、接口清单、进度表、踩坑表。

> 文档不是仪式。这个项目里**"为什么"比"是什么"值钱** ——
> 代码能告诉你怎么实现，告诉不了你为什么这么选、边界在哪、什么情况下会崩。

---

## 二、后台接口的额外规矩

后台和用户端是**两套凭证**，别混：

| | 用户端 | 后台 |
| --- | --- | --- |
| 头 | `X-Device-Token` | `X-Admin-Token` |
| 守卫 | `require_device` | `require_admin` |
| 令牌来源 | `POST /activation/redeem` 换来的 | `PLOVE_ADMIN_TOKEN` 环境变量（**留空 = 全部 403**） |

四条额外规矩：

1. **每个写操作留一行审计**：`logger.info("后台操作 action=%s %s request_id=%s", ...)`
   （见 `app/api/v1/admin.py` 的 `_audit`）。理由：这些操作在用户那边**不会产生任何提示**，
   用户只会发现"突然看不了了"，事后能对上"几点几分谁干了什么"才不会去怀疑代码。
2. **敏感值一律掩码**：设备令牌只给前 6 位（`admin_service.mask_code` 同理）。
   后台页面会被投影、会截图，令牌一旦进响应就等于每次都泄露一遍。
3. **写操作显式 `commit_now(db)`**（见第一步第 5 条）。
4. **契约用 `admin-` 前缀**，并在 `EXPORTS` 里单独一组、带注释。

---

## 三、前端（如果这次要动）

**类型是生成物，不要手写 `src/api/types.ts`。**

```bash
cd frontend
npm run gen:types     # 重新生成
npm run check:types   # 只比对（期望指纹会变，变了就是对的）
npm run build         # 先 vue-tsc 再打包；类型错误会让构建失败（故意的）
```

* 用户端改动在 `src/views/`、`src/components/`、`src/stores/`（Vant）。
* 后台改动在 `src/admin/`（Element Plus **按需**引入，别 `app.use(ElementPlus)`，
  否则用户端首屏会变重）。
* `src/api/http.ts` 是**唯一**发请求的地方，别在组件里 `fetch`。
* 新接口加到 `src/api/client.ts`（参数名和后端**一字不差**）。
* `src/App.vue` 是**用户端和后台共用**的根组件 —— 加全局逻辑前先问一句
  "它对不对后台生效"（踩过：用户端的"已在别的设备上使用"弹窗漏进了后台）。

---

## 四、粘贴板：一次改动要跑的命令

```bash
# 1. 契约（改了 Pydantic 就必须跑）
cd backend && ./.venv/Scripts/python.exe tools/export_contracts.py

# 2. 后端测试
./.venv/Scripts/python.exe -m pytest

# 3. 爬虫测试（改了 crawler/ 才需要）
cd ../crawler && ../backend/.venv/Scripts/python.exe -m pytest

# 4. 前端类型 + 构建（动了契约或前端才需要）
cd ../frontend && npm run check:types && npm run build
```

起服务（**uvicorn 没加 `--reload`，改后端代码要手动重启**）：

```bash
cd backend && nohup ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/plove-backend.log 2>&1 < /dev/null &
cd frontend && nohup npx vite --port 5173 --host 127.0.0.1 > /tmp/plove-frontend.log 2>&1 < /dev/null &
```

后台令牌在本机 `backend/.env` 里（当前是 `admin`），**改它要重启进程**。

---

## 五、完成的定义（DoD）

一次改动**算完成**，要同时满足：

- [ ] `pytest` 全绿，**且新行为有对应的用例**（含负面用例：错令牌 / 未激活 / 空配置）
- [ ] 契约已导出，`test_contracts_on_disk_are_not_stale` 绿
- [ ] `npm run check:types` 绿（动了契约时）
- [ ] 真的**跑起来点过一遍**（不是只看测试绿）
- [ ] 文档：写了"为什么"和"**没做什么**"
- [ ] `PROGRESS.md` 的数字同步了

---

## 六、新对话的开场白（直接抄，把 `<...>` 换掉）

```
先读这几个文件，再动手：
- PROGRESS.md                       （当前状态、验证数字、已拍板决策、踩过的坑）
- docs/how-to-add-a-feature.md      （加功能的固定动作，这份）
- docs/architecture.md              （整体设计）
- docs/steps/07-admin-panel.md      （最新一步，格式照抄它）

这次要做的：<一句话说清要什么>
属于哪一类：<后台接口 / 内容接口 / 新源站 / 前端>

规矩（照 docs/how-to-add-a-feature.md 走）：
- 契约是唯一事实源，改完 Pydantic 必须跑 tools/export_contracts.py
- service 不 import fastapi、不 commit；写接口在路由里 commit_now(db)
- 测试离线、不碰真库、不依赖开发机 .env
- 做完写文档 + 同步 PROGRESS.md 的数字
- 后端进程没开 --reload，改完要重启才生效

先别写代码：先跟我说你打算怎么做（接口形状、放哪个文件、怎么测），我确认后再动手。
```

> 最后一句建议保留。这个项目里**想清楚形状**本身就是一半的工作量，
> 而模型的字段一旦生成到契约里，改起来要动三端。

---

## 七、容易踩的坑（速查）

| 坑 | 记住 |
| --- | --- |
| `get_db` 的 commit 在**响应之后** | 写接口一律 `commit_now(db)`；"窗口很小" ≠ "时序上必然" |
| 守卫别写在单个路由上 | 挂 router，否则新接口迟早漏鉴权 |
| 两个 `APIKeyHeader` 不给 `scheme_name` 会撞名 | Swagger 里会发错令牌 |
| HTTP 头不能放非 ASCII | 中文一律走 body |
| 契约 JSON 是生成物 | 别手改；改模型再导出 |
| 前端 `src/api/types.ts` 是生成物 | 别手改 |
| `<video>` 挂在 `v-if` 后面 | 赋值后要 `await nextTick()` 再挂，Vue 渲染是异步的 |
| 缓存/熔断只在真跑时才暴露 | 改这块要**数爬虫被调了几次**（`crawler_counter`），响应长得一模一样看不出来 |
| `__init__.py` 会被当成一个源 | 下划线开头**恰好通过** key 正则，别把文件放错层 |
| Windows 控制台是 GBK | 脚本里别输出 `✓` 这类符号；爬虫要 `python -X utf8` |
| 测试依赖开发机 `.env` | 夹具里**显式钉死**每个要用的配置 |
