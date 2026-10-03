# frontend —— 前端

**骨架已完成**（[步骤 6 文档](../docs/steps/06-frontend-skeleton.md)）：
激活 → 选源 → 首页 → 分类 → 详情 → **播放能出画面**，全部连着真后端、真源站。

界面还很粗（没有搜索、没有收藏、没有骨架屏）—— 那是**下一步的\"精细化调整\"**，
而且可以直接对着真数据调。

## 选型

| 项 | 选型 |
| --- | --- |
| 构建 | Vite |
| 语言 | TypeScript |
| 框架 | Vue3 + Pinia + vue-router |
| 组件 | Vant（用户端）· Element Plus（后台管理，阶段 8） |
| 播放 | hls.js（**iOS 上优先用原生 HLS**，见下） |
| 类型来源 | 由 [contracts/schemas/](../contracts/schemas/) 生成，**不手写** |

## 跑起来

```powershell
cd E:\Pychon-code\NY\Plove1.0\frontend
npm install
npm run dev          # http://127.0.0.1:5173（/api 由 vite 代理到 127.0.0.1:8000）

npm run build        # 先 vue-tsc 类型检查，再打包（类型错会让构建失败）
npm run typecheck    # 只检查
```

后端要另外起一个：

```powershell
cd ..\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

浏览器记得开 F12 的设备工具栏选手机尺寸 —— 用户端是按移动端做的。

## 类型是生成物

```
Pydantic 模型 ──▶ contracts/schemas/*.json ──▶ src/api/types.ts
```

后端改了契约之后：

```bash
npm run gen:types     # 重新生成（日志里会报\"多少个类型 ← 多少个契约\"）
npm run check:types   # 只比对；过期退出码 1
```

生成器在 [tools/gen-types.mjs](tools/gen-types.mjs)，只实现契约里用到的 JSON Schema
子集，**遇到不认识的形状会直接报错退出**，不会悄悄生成 `any`。

## 三条不要破坏的约定

1. **组件里不写 URL 字符串**。所有请求走 [src/api/client.ts](src/api/client.ts)，
   它用 [src/api/http.ts](src/api/http.ts) 统一拆信封、带令牌、超时、翻译错误码。
2. **前端永远只写 `/api/v1`**（相对路径）。开发靠 vite proxy，上线靠 nginx 同源 ——
   同源意味着**根本不存在 CORS**，别为了\"方便\"改成绝对地址。
3. **播放优先走原生 HLS**：iOS / WKWebView 本来就能播 m3u8，
   那条路（也就是日后 ipa 走的路）不要给 hls.js 插手。

## 已知的债

| 项 | 说明 |
| --- | --- |
| Vant **整包**注册 | 一个 78 KB(gz) 的独立 chunk。要瘦身就换 `unplugin-vue-components` 按需引入 |
| 没有骨架屏 / 过渡 | 加载时只有转圈 |
| 搜索没做 | 两个源都还没实现，所以界面上刻意不放搜索框 |
| 没有收藏 / 历史 / 续播 | 需要先想清楚\"跟不跟账号走\"—— 我们没有账号体系 |
| 错误上报 | 只有 `console.warn` 和 `requestId`，没有汇总上报 |

整体计划在 [PROGRESS.md](../PROGRESS.md)。
