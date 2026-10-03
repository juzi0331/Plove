# 步骤 9 · 后台 UI 重设计（第一批：只动前端）

> 完成：2026-09-30 ｜ 范围：**只动前端**，后端 19 个接口与 27 份契约**一行未改**。
> （编号说明：步骤 8 是另一个线程做的用户端重设计 —— 用户端与后台是两条线，各有一份文档。）
> 提案与完整功能清单见 [docs/admin-redesign-plan.md](../admin-redesign-plan.md)。
>
> 验证：`vue-tsc --noEmit` **0 错误** · `vite build` 通过（5.8s）·
> 浏览器里真点过一遍：登录 → 总览 → 激活码（6 个真码）→ 设备 → 只读模式 →
> 暗色模式 → 双击进设备。
>
> **为什么先做这一批：** 提案里它全是"纯前端"（23 项），零契约风险，
> 也最能看出"新后台"的样子 —— 不满意的话，改的是样式与组件，不是数据形状。

---

## 一、这一批到底改了什么

| 提案编号 | 做了什么 | 在哪 |
| --- | --- | --- |
| G1 视觉体系 | 设计 token + Element 主题覆盖 + 公共布局类 | [theme.css](../../frontend/src/admin/theme.css) |
| G2 分组导航 | 深色侧栏、分组菜单（概览 / 运营）、图标、可折叠（记住状态） | [AdminShell.vue](../../frontend/src/admin/AdminShell.vue) |
| G3 面包屑 + 标题 | 面包屑来自路由 `meta`；浏览器标题 `Plove 后台 · 设备` | AdminShell + [router/index.ts](../../frontend/src/router/index.ts) |
| G4 状态三件套 | 骨架屏 / 空状态（带下一步按钮）/ 错误态（带重试） | 三个新组件（见第三节） |
| G5 相对时间 | 「4 分钟前」，悬停看绝对时间，自己每 30 秒重算 | TimeAgo.vue |
| G6 暗色模式 | 浅色 / 深色 / 跟随系统，偏好存 `localStorage` | [ui.ts](../../frontend/src/admin/ui.ts) |
| G7 自动刷新可配 | 顶栏配置（开关 + 3/5/10/30s），总览页照它跑 | AdminShell + DashboardView |
| G11 表格体验 | 列宽记忆、粘性表头、双击进设备、工具栏粘住 | CodesView |
| A1 告警横幅 | 熔断 / 预热失败 / TTL=0 / 预热没开，打开就能看见 | DashboardView |
| A2 源健康卡片 | 每源一张卡，冷却倒计时一秒秒跳 | SourceHealthCard.vue |
| B7 发码预设与记忆 | 7/30/90/365 天一键；记住上次时长与数量 | CodesView + ui.ts |
| B8 行内复制 | 每行一个复制按钮（悬停出现） | CodesView |
| B9 状态高亮 | <24h 变黄、已到期变灰、已停用划线 | CodesView + theme.css |
| C2 在线判定 | 「活跃位 / 最近活跃（5 分钟内）/ 离线」 | DevicesView |
| F4 只读模式 | 顶栏一键禁用所有写操作，**api 层兜底** | ui.ts + [api.ts](../../frontend/src/admin/api.ts) |

---

## 二、新增 / 改动的文件

| 文件 | 什么性质 |
| --- | --- |
| `frontend/src/admin/theme.css` | **新增**：token、Element 主题覆盖、公共布局类 |
| `frontend/src/admin/ui.ts` | **新增**：主题 / 只读 / 自动刷新 / 发码记忆 |
| `frontend/src/admin/components/*.vue` | **新增 6 个**（见第三节） |
| `frontend/src/admin/AdminShell.vue` | 重写（分组侧栏 + 顶栏 + 面包屑） |
| `frontend/src/admin/views/*.vue` | 4 个页面全部重写（登录 / 总览 / 激活码 / 设备） |
| `frontend/src/admin/api.ts` | 每个写操作前加 `assertWritable()` |
| `frontend/src/router/index.ts` | 后台路由加 `meta.title` / `meta.crumb` |
| `frontend/package.json` | 新增依赖 `@element-plus/icons-vue`（官方图标包） |

---

## 三、组件清单（后续要改界面时按这个点名）

### 1. 自己写的 6 个组件（都在 `frontend/src/admin/components/`）

| 组件 | 用途 | 关键 props |
| --- | --- | --- |
| `PageHeader.vue` | 页面头：标题 + 一句说明 + 右侧操作区 | `title` · `desc` · `#actions` 插槽 |
| `StatCard.vue` | 统计卡：大数字 + 脚注 | `label` · `value` · `unit` · `foot` · `tone`（default/warn/danger/good） |
| `SourceHealthCard.vue` | 单个源的健康卡（冷却倒计时每秒跳） | `health`（`SiteHealth`） |
| `TimeAgo.vue` | 相对时间，悬停看绝对时间 | `value`（ISO 字符串） |
| `EmptyState.vue` | 空状态：说清为什么空 + 下一步 | `title` · `hint` · `#action` 插槽 |
| `ErrorState.vue` | 错误态：错在哪 + 重试 | `message` · `hint` · `@retry` |

### 2. 两个"全局模块"（不是组件，但改界面绕不开）

| 模块 | 管什么 | 对外接口 |
| --- | --- | --- |
| `ui.ts` | 主题、只读、自动刷新、发码记忆 | `ui`（只读响应式对象）· `cycleTheme()` · `setReadOnly()` · `enterAdminUi()/leaveAdminUi()` |
| `theme.css` | 设计 token 与公共类 | 类：`.a-page` `.a-head` `.a-card` `.a-grid` `.a-toolbar` `.a-section` `.a-note` `.a-mono` `.a-muted` `.a-row--warn/--expired/--disabled` |

### 3. 用到的 Element Plus 组件（按页面）

| 页面 | 用到的 Element 组件 |
| --- | --- |
| AdminShell | `ElConfigProvider`（中文 locale）· `ElMenu` · `ElMenuItem` · `ElMenuItemGroup` · `ElBreadcrumb` · `ElBreadcrumbItem` · `ElButton` · `ElIcon` · `ElTooltip` · `ElPopover` · `ElSwitch` · `ElRadioGroup` · `ElRadioButton` |
| DashboardView | `ElButton` · `ElSwitch` · `ElSkeleton` · `ElTable` · `ElTableColumn` · `ElTag` · `ElMessage` |
| CodesView | `ElAlert` · `ElButton` · `ElDialog` · `ElInput` · `ElInputNumber` · `ElSelect` · `ElOption` · `ElPagination` · `ElSkeleton` · `ElTable` · `ElTableColumn` · `ElTag` · `ElMessage` · `ElMessageBox` · `v-loading`（`ElLoading.directive`） |
| DevicesView | `ElButton` · `ElSkeleton` · `ElTable` · `ElTableColumn` · `ElTag` · `ElMessage` · `ElMessageBox` · `v-loading` |
| LoginView | `ElButton` · `ElInput` |

图标（`@element-plus/icons-vue`）：`Odometer` · `Tickets` · `Fold` · `Expand` · `Sunny` · `Moon` · `Monitor` · `Setting`。

> **仍然是按需引入**：没有 `app.use(ElementPlus)`。构建产物里 Element 那几个 chunk
> 只在后台路由加载（`AdminShell` / `CodesView` / `validator` 等），用户端首屏不变重。

---

## 四、设计口径（为什么是这个颜色）

| 项 | 取值 | 理由 |
| --- | --- | --- |
| 底色 / 卡片 / 边框 | `#f6f7f9` / `#fff` / `#ebedf0` | 比 Element 默认的灰更冷、更轻，表格不再"铁板一块" |
| 主色（主操作 / 侧栏激活） | `#2b3445` 深墨色 | 按钮不再是刺眼的 `#409EFF` |
| 品牌色 | `#ee0a24`（与用户端一致） | **只给品牌标识与危险动作** —— 避免"满屏红按钮" |
| 圆角 / 阴影 / 间距 | 10px / 两级 / 4 的倍数 | 视觉节奏统一 |
| 侧栏 | `#1c212c`（暗色下 `#16181d`） | 深色侧栏 + 浅色内容区，是运维面板最熟悉的一种 |

做法是**用 CSS 变量覆盖 Element 主题**（`--el-color-primary` 等），不改组件用法：
按需引入的收益保留，将来换主题只动 `theme.css`。

---

## 五、怎么验证

```bash
cd frontend
npm run build          # 先 vue-tsc 类型检查，再打包（期望 0 错误）
```

浏览器（后端与前端都起着；后台令牌是本机 `backend/.env` 里的那个）：

1. 开 `http://127.0.0.1:5173/admin/login`，输入后台令牌 → 进总览；
2. 总览：告警横幅 / 统计卡 / 源健康卡片 / 上次预热；
3. 激活码：搜索、列宽拖一下再刷新（宽度记住）、发码对话框（预设按钮 + 上次参数）、
   行内复制、双击一行进设备；
4. 顶栏：**只读**打开后所有写按钮变灰（在发码对话框里点"签发"也会被 api 层拦住）、
   主题点两下切深色 / 跟随系统、自动刷新改间隔；
5. 设备页：活跃位 / 最近活跃 / 离线三种状态、踢下线。

---

## 六、这一批**没有**做

| 没做 | 在哪一批 | 为什么不在这一批 |
| --- | --- | --- |
| 码的**状态筛选 / 排序 / 统计卡**（B1/B2/B3/B4） | 第二批 | 要后端加 `status` / `sort` 参数与 `/admin/stats`，不能只靠前端筛当前页（那是**误导**） |
| 审计日志落库 + 查询（F3、码详情时间线 B5） | 第二批 | 要新表 |
| 全局设备页（C1）、强制接管（C3） | 第二批 | 要新接口 |
| 源自检 / 源内容预览 / 熔断手动重置（D3/D4） | 第二批 | 要新接口 |
| 后台令牌可热改（F1） | 第二批 | 要新表 + 哈希存储 |
| 源开关 / 公告（D1/D2/E1） | 第三批 | 属于远程配置（6b-3），会决定用户端看到什么 |
| 趋势图 / 最近错误流（A4/A9） | 第三批 | 要后端环形采样 |
| 二维码（B6）、命令面板（G9） | 第二/三批 | 前者要加 `qrcode` 小依赖；后者建议等页面多起来再做 |

> 侧边栏现在只有「概览 / 运营」两组 —— 它是**诚实的**：
> 内容源、系统那两组等第二批的页面真的存在了再加，不放指向空白页的菜单。

---

## 七、这一批踩到的坑（都修了）

| 坑 | 教训 |
| --- | --- |
| 模板里写了个**并不存在的 `ElFormLike`** | 占位符当组件写进了文件。构建会报错还算好，**怕的是它长得像真的** |
| 生成类型里的数组是**可选**的（`codes?: CodeListItem[]`） | `data.value.codes.length` 类型不过；一律 `?.` + `?? []` |
| Element 默认是**英文** | 分页显示 `Total 6` / `20/page`。要 `ElConfigProvider` + `zh-cn` locale |
| 面包屑把**当前页**也当成了链接 | 连带浏览器标题退化成「Plove 后台」：`reverse().find(c => !c.to)` 找不到当前页。现在最后一项显式去掉 `to` |
| 源健康卡的冷却倒计时**重复扣时间** | `retry_after` 是"响应那一刻的剩余"，不是绝对时刻。直接减"挂载以来的秒数"，每次刷新都会多扣一遍。改成收到新值时算 `deadline` |
| `ElSwitch` 的 `model-value` 类型比 `boolean` 宽 | 直接把 `setReadOnly` 当处理器会类型不过，要 `(v) => setReadOnly(Boolean(v))` |

---

## 八、下一步

1. **你先看** —— 不满意的地方直接点名组件 / 页面（第三节的清单就是为这个准备的）；
2. 认可后走**第二批**（小契约）：码的状态筛选与统计、审计落库、全局设备页、源自检；
3. 然后才是**第三批**（远程配置：源开关 / 公告）。

> 顺序的理由写在提案里：第一、二批都是加法，不会改变现有 19 个接口的形状；
> 远程配置决定用户端"看到什么"，等后台自己的形状稳定了再动。
