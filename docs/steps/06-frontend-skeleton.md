# 步骤 6 · 前端骨架：从零到能播

> 完成：2026-09-30 ｜ 代码：[frontend/](../../frontend/) ·
> [tools/gen-types.mjs](../../frontend/tools/gen-types.mjs) ·
> [src/api/http.ts](../../frontend/src/api/http.ts) ·
> [src/views/PlayerView.vue](../../frontend/src/views/PlayerView.vue)
>
> 验证：`vue-tsc` **0 错误** · `vite build` 通过 · 契约指纹一致 ·
> **真机走完**：激活 → 选源 → 首页 → 详情 → 播放
> （`<video>` 真的出画面：`readyState=4`、时长 **7591s**、1920×1040、`currentTime` 在走）

前端在此之前是**零行代码**。这一步的目标不是\"做好看\"，而是：

> **把整条链路接通，让页面能播出一集真实的剧。**

界面还很粗（没有搜索、没有收藏、没有下拉刷新），但**每个页面都连着真后端、真源站**。
\"精细化调整\"接在这一步之后，而且可以一直对着真数据调。

---

## 一、这一步交付了什么

```
frontend/
├── package.json          Vue3 + Vite + TS + Vant + hls.js + Pinia + vue-router
├── vite.config.ts        dev 把 /api 代理到 127.0.0.1:8000；产物按库分包
├── index.html            移动端 viewport（含 viewport-fit=cover，给刘海屏留安全区）
├── tools/gen-types.mjs   ★ 契约 → TS 类型（生成的，不手写）
└── src/
    ├── api/
    │   ├── types.ts      ★ 生成物（25 个类型 ← 18 个契约）
    │   ├── http.ts       ★ 唯一发请求的地方：拆信封 / 带令牌 / 超时 / 翻译错误码
    │   ├── client.ts     12 个接口的函数（参数名和后端一字不差）
    │   └── session.ts    设备令牌 + \"被踢\"的通知通道
    ├── stores/           device（激活/心跳/被踢）· sites（选源）
    ├── router/           路由 + 未激活一律赶回 /activate
    ├── components/       VodCard（影片卡）· StateBlock（加载/出错/空 三态）
    └── views/            激活 · 选源 · 首页 · 分类 · 详情 · 播放
```

---

## 二、四个决定了整个前端形状的选择

### 1. 前端永远只写 `/api/v1`，不写真主机名

开发时由 `vite.config.ts` 的 proxy 转到本机后端；上线后前端和后端**同源**
（nginx 一个域名既发静态文件又反代 `/api`）。

**为什么值得当规矩：** 同源意味着**根本不存在 CORS**。而 CORS 正是当初否掉
\"前端直连源站\"方案的三堵墙之一 —— 现在我们从设计上就不会碰到它，
而不是靠配一堆响应头去绕。

### 2. 类型是**生成的**，不是手写的

```
Pydantic 模型  ──export_contracts.py──▶  contracts/schemas/*.json  ──gen-types.mjs──▶  src/api/types.ts
   （后端唯一事实源）                        （18 个契约）                               （前端不手改）
```

**为什么非这样不可：** 手写的 `interface VodItem` 在字段改名时**不会报错** ——
它只会安静地和实际响应不一致，等线上出现 `undefined` 才发现。
生成的类型则是编译期就炸。

两条命令和后端的 `export_contracts.py` 对着：

```bash
cd frontend
npm run gen:types     # 重新生成
npm run check:types   # 只比对；过期退出码 1（可以当部署门禁）
```

生成器只实现契约里用到的 JSON Schema 子集，**遇到不认识的形状直接报错退出**，
而不是悄悄生成一个 `any` —— 悄悄降级成 `any` 正是这套机制要防的那种失败。

### 3. `http.ts` 是唯一发请求的地方

它一次解决四件分散在各页面里必然会写错的事：

| 它做的事 | 不做会怎样 |
| --- | --- |
| 拆信封（`ok:false` 就抛异常） | 每个页面都要 `if (res.ok)`，忘一个就把错误当数据渲染 |
| 带上设备令牌 | 少一个接口忘了带，那个接口永远 401 |
| 60 秒超时（后端最坏 ~45 秒） | 用户对着转圈一直等 |
| 错误码 → 人话 | 首页说\"源站超时\"、详情说\"网络错误\"，同一件事两种说法 |

错误一律是 `ApiError`，**带 `requestId`**。把这个 id 打给用户，
就能在服务端日志里直接定位这一次请求 —— 比\"几点、哪个接口\"这种描述有用得多。

### 4. `session.ts` 为什么单独存在

它只管两件事：**令牌存哪**、**被踢了通知谁**。

如果令牌住在 Pinia store 里，就会出现这个循环：
`http.ts`（要读令牌）→ store → `client.ts`（要发请求）→ `http.ts`。
用一个不依赖任何框架的小模块把它打断，问题就没了 —— 路由守卫也因此能在
Pinia 装好之前就判断\"激活了没有\"。

---

## 三、\"被踢\"这条规则，前端必须一起守

后端的设计是：**活跃位只在有人主动抢的时候才变**，没有心跳超时释放。前端照做：

| 做 | 不做 |
| --- | --- |
| 心跳返回 `is_active: false` → 立即停播 + 弹窗 | ❌ 不能自己抢回来（两台设备会无限互踢） |
| 弹窗里放一个明确的\"在此设备继续\"按钮 | ❌ 不能自动点它 |
| 心跳**失败**时什么都不做（网络抖一下不该踢人） | ❌ 不能因为一次超时就清令牌 |
| 任何接口回 `SESSION_KICKED` → 走同一套处理（在 `App.vue`，不在各页面） | ❌ 不能每个页面各写一份 |

那个\"继续\"按钮是产品设计的一部分，不是 UI 装饰。

---

## 四、现在能干什么

| 页面 | 路由 | 用的接口 |
| --- | --- | --- |
| 激活 | `/activate` | `POST /activation/redeem` |
| 选源 | `/sites` | `GET /sites` |
| 首页 | `/` | `GET /sites/{key}/home` |
| 分类 | `/category/:tid` | `GET /sites/{key}/category?tid&page`（无限下拉） |
| 详情 | `/detail/:vodId` | `GET /sites/{key}/detail?vod_id` |
| 播放 | `/play/:vodId/:ep` | `GET /sites/{key}/playback?vod_id&ep&line&play_id` |

已经照顾到的三件真事：

* **分类不写死**：用的是源站返回的 `categories`（`ncat21` 上是 电影/连续剧/动漫/综艺纪录/短剧），
  换源不用改前端一行。
* **多线路**：详情页按 `lines` 分组，集号重复也不会串（靠 `line` 区分）。
  `ncat21` 这一部有 **18 条线路**。
* **`play_id` 从详情带到播放页**：实测能让后端省掉一次源站请求
  （`7.2s → 4.0s`）。详情页本来就有这个值，白拿的加速。

---

## 五、怎么跑起来

```powershell
# 1. 后端（另一个窗口，别关）
cd E:\Pychon-code\NY\Plove1.0\backend
.\.venv\Scripts\python.exe tools\init_db.py
.\.venv\Scripts\python.exe tools\issue_code.py --days 30
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 2. 前端
cd E:\Pychon-code\NY\Plove1.0\frontend
npm install
npm run dev            # → http://127.0.0.1:5173
```

浏览器开 F12 → 设备工具栏 → 选个手机尺寸（iPhone 14 之类）。
没激活会被自动赶到 `/activate`，填码 → 首页 → 点海报 → 详情 → 选集 → 播放。

`npm run build` 会先跑 `vue-tsc`（类型检查）再打包 —— **类型错误会让构建失败**，
这是故意的：类型检查是这条链上唯一能自动发现\"前端和后端对不上\"的环节。

---

## 六、联调时抓到并修掉的三个问题

### 1. 生成器报了 6 处\"契约冲突\"——其实是我的比较太严

第一次跑 `gen:types` 直接失败：

```
Episode：catalog-detail.json 与 episode.json 里定义不一致
VodItem：catalog-detail.json 与 vod-item.json 里定义不一致
...（共 6 处）
```

原因不是后端写错了，而是：**`VodItem` 这类类型在多个契约里各定义了一份**
（独立的 `vod-item.json`，以及嵌在 `catalog-home.json` 等文件 `$defs` 里的副本），
独立那份带顶层 `description`，副本没有 —— 语义完全相同，JSON 文本不同。

改法：**比较\"生成的 TS 文本\"，而不是比较原始 JSON**。我们真正关心的是
\"它们会不会产生不同的类型\"，注释差异不影响这一点。真不一致时仍然报错并列出
是哪两个文件 —— 那时宁可让人去改后端，也不该让前端替它选一个。

### 2. 视频拿到了地址却是空的（**这个最值得记**）

现象：播放页请求全部 200，Network 面板干干净净，**但 `<video>` 没有 `src`**。

原因：`<video>` 挂在 `v-if="playback"` 后面。代码是这样的：

```ts
playback.value = result   // 赋值
attachPlayer(result)      // ← 这一刻 DOM 还没更新，videoEl 还是 null，函数直接 return 了
```

Vue 的渲染是**异步**的，赋值那一瞬间元素还不存在。
修法是 `await nextTick()` 之后再挂载。

**为什么值得写进文档：** 这类失败**完全不产生错误**，不看画面根本发现不了 ——
不看视频、只看请求日志的话，会得出\"一切都好\"的结论。所以现在 `attachPlayer`
在拿不到元素时**会 `console.warn`**，而不是静默返回。

### 3. \"防盗链\"提示误报（一个总出现的警告等于没有警告）

一开始的逻辑是\"`playback.headers` 非空就提示这个源需要代理\"。
实测发现 `ncat21` 会返回 headers（Referer / UA），**但它明明能正常播** ——
于是每个用户都会看到一条唬人的警告。

改成**只在真的播不出来时**才显示。

> 顺带记一条真实的限制：浏览器**不允许**脚本改 `Referer` / `User-Agent`，
> 所以 `playback.headers` 在浏览器里本就大半无效。
> 真正需要它的源要走服务端流代理（阶段 9），`SiteMeta.mode === 'proxy'` 就是在说这件事。

---

## 七、几个写下来的取舍

| 取舍 | 为什么 | 代价 |
| --- | --- | --- |
| **Vant 整包注册** | 骨架阶段先要\"能写\"；按需引入要配 `unplugin-vue-components` | 一个 **78 KB(gz)** 的独立 chunk |
| **hls.js 只在需要时加载** | iOS / WKWebView **原生就能播 m3u8**，那条路不给 hls.js 插手 —— 封 ipa 后走的就是它 | hls chunk **185 KB(gz)**，但桌面浏览器才加载 |
| **`history` 路由**（不是 hash） | ipa 里 WKWebView 的返回手势用 hash 很难受 | nginx 必须把未知路径回落 `index.html`（部署时别忘） |
| **不做搜索** | 两个源都还没实现（`ncat21` 要 token、`ai2048` 接口未找到） | 前端一个搜索框都没放，免得点了回 `UNSUPPORTED` |
| **换源做成首页右上角的\"换源\"** | 源随时可能坏，这是用户当时唯一的自救手段 | 需要一个能立刻重载的 `watch`（已处理重复请求） |

打包结果（实测）：

```
vue        105.98 KB │ gzip:  41.43 KB
vant       219.90 KB │ gzip:  78.09 KB
hls.js     594.02 KB │ gzip: 185.48 KB      ← 只被播放页按需加载
其余按路由分割，每个页面 2~3 KB
```

---

## 八、这一步**没有**做

| 没做 | 说明 |
| --- | --- |
| 好看 | 没有设计稿、没有骨架屏、没有过渡动画。**先接通，再调** |
| 搜索 | 两个源都没实现，界面里也刻意不放 |
| 收藏 / 观看历史 / 续播 | 需要本地存储设计（而且要决定要不要跟账号走 —— 我们没有账号） |
| 下拉刷新 | Vant 有 `PullRefresh`，接上很快，但先验证主链路 |
| 后台管理面板 | 阶段 8。`client.ts` 里已经放好两个后台接口的函数占位 |
| Capacitor / ipa | 最后一步。**但已经为它铺了两处**：iOS 原生播放优先、`history` 路由 |
| 错误上报 | 现在只有 `console.warn` 和 `requestId`，没有汇总 |
| 分片级去广告 | 播放器直接吃源站的 m3u8，没做改写 |

**还发现一处小债**（不影响播放）：`ncat21` 的剧情简介里带 **HTML 标签**（`<br>`），
前端按文本渲染，于是页面上会直接看到 `<br>` 四个字符。
该在爬虫的清洗层处理掉（`crawler_kit/clean.py`），不是前端该渲染 HTML。

---

## 九、下一步

| 方向 | 内容 |
| --- | --- |
| **精细化调整** | 对着真数据调界面：骨架屏、海报尺寸、详情页排版、错误文案 |
| 远程配置（阶段 6b-3） | 源开关 / 公告弹窗 / kill switch —— 前端要加一个启动时的 `config` 拉取 |
| `rou.video` | 第 3 个源（带加密），也是设计\"爬虫生成器\"时的关键样本 |
| 后台面板（阶段 8） | 复用这套 `http.ts` + 生成类型，但用 Element Plus |

> 顺序建议：**先做远程配置再深挖前端**。它是\"加法\"（多一个接口、多几个字段），
> 现在改成本很低；等界面复杂了再回来插，就要动启动流程了。
