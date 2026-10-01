# Plove 前端代码审计指引 (Frontend Audit Guide)

> 备份时间：2026-09-30  
> 源码目录：`UI/frontend/`（已剔除 `node_modules` 与构建产物 `dist`，保持 100% 纯净代码）

---

## 一、技术栈与运行环境
- **核心框架**：Vue 3.5+ (Composition API, `<script setup lang="ts">`)
- **构建工具**：Vite 6.x
- **类型系统**：TypeScript 5.x + `vue-tsc`（类型严格校验）
- **路由状态**：`vue-router` 4.x + `pinia` 2.x
- **流媒体播放引擎**：`hls.js` + 原生 HTML5 Video (针对 iOS / Safari 原生 HLS 回退)
- **UI 风格**：Netflix 官方 1:1 暗黑影院流媒体沉浸风格 (纯原生 CSS 变量系统，无冗余 CSS 框架)

---

## 二、目录架构与关键审计文件

### 1. 核心视图 (`src/views/`)
- **[ActivationView.vue](src/views/ActivationView.vue)**：
  - 用户激活码输入、卡密有效性校验、设备指纹生成与令牌绑定；
  - 核心安全：AES 凭据加密交互、激活状态防穿透。
- **[HomeView.vue](src/views/HomeView.vue)**：
  - 首页 Netflix 官方大屏看板：16:9 Billboard 头图海报、多分类横版滑轨 (NetflixCard)；
  - 动态片源站点下拉切换、VIP 头像真实到期时间与精确剩余天数展示。
- **[CategoryView.vue](src/views/CategoryView.vue)**：
  - 16:9 响应式无限瀑布流、触底无感分页追加；
  - **核心缓存机制**：`categoryCache` 模块级持久缓存，记录已加载多页影片、分页与精确 `scrollY`，跳入详情页再返回零丢失、零重载。
- **[DetailView.vue](src/views/DetailView.vue)**：
  - 16:9 宽银幕 Hero 画卷、剧情简介展开、双栏选集矩阵、演员阵容档案与“更多类似好片”滑轨；
  - **防套娃导航**：`selectRelated` 使用 `router.replace`，记录初始外部来源 `initialReferrer`，返回时一键退出至大厅。
- **[PlayerView.vue](src/views/PlayerView.vue)**：
  - 全屏纯黑影院播放大厅 (Cinema Theater)；
  - **流媒体容错**：HLS / MP4 自适应流、分片网络中断重连、错误恢复自救；
  - **交互体验**：3.5s 智能感应 HUD 悬浮顶栏、右侧毛玻璃“選集大廳”抽屉直接切集切线路。

### 2. 状态管理与网络层 (`src/stores/` & `src/api/`)
- **`src/stores/device.ts`**：
  - 客户端设备状态机：激活码、Token、过期时间（`expiresAt`）、剩余天数（`daysLeft`）、精准格式化剩余时间；
  - 心跳机制（`heartbeatOnce`）与踢线状态管理（`kicked`）。
- **`src/stores/sites.ts`**：
  - 多片源站点注册、当前片源切换与列表缓存。
- **`src/api/http.ts` & `src/api/client.ts`**：
  - 统一 HTTP 封装、错误描述解析、Token 鉴权头注入。
- **`src/api/session.ts`**：
  - 本地设备凭据安全存取与隔离。

### 3. 全局样式与滚动条 (`src/styles/app.css`)
- Netflix 级全局色彩变量系统（`--plove-bg: #000000`）；
- 全局现代微光细滚动条适配（彻底告别 Windows 原生浅灰宽滚动条）。

---

## 三、代码审计重点建议关注项
1. **设备并发与踢线抢位逻辑**：
   - 检查 `App.vue` 中的 `van-dialog` 踢线提醒与 `continueHere` 恢复机制，确认是否存在单设备令牌被顶替后的无限循环风险。
2. **播放流媒体请求头安全性**：
   - `PlayerView.vue` 中 `hls.xhrSetup` 针对防盗链 headers 的透传与浏览器禁止设置受限头的异常捕获机制。
3. **路由守卫拦截**：
   - `src/router/index.ts` 中针对未激活设备重定向至 `/activate`、已激活设备禁止重复进入激活页、后台管理系统独立的 `X-Admin-Token` 隔离审计。
4. **内存泄漏防护**：
   - 各组件的 `window.addEventListener('scroll')`、`hls.destroy()`、`setTimeout` 计时器在 `onBeforeUnmount` 中是否均已 100% 妥善释放。
