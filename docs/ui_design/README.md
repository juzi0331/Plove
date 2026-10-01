# PLOVE 奈飞级未激活落地页 (纯净版源码)

本目录为官方 1:1 像素级复刻的纯净版激活首页源码，已去除所有冗余代码、弹窗与调试配置，开箱即用。

---

## 📁 目录结构

```text
UI/
├── activation_page.html    # 独立免编译 HTML5 纯净版（双击即可直接在浏览器运行）
├── index.html              # 静态 Web 服务器默认入口（与 activation_page.html 相同）
├── logo.png                # 官方 1:1 标准规格 PLOVE 字标（370x100 px, 37:10 宽高比）
├── README.md               # 本说明文档
└── vue_components/         # Vue 3 + TypeScript 纯净组件包
    ├── ActivationView.vue  # 落地激活页完整主视图（含 15px 圆角输入框与按钮、热播前十名）
    ├── HeroBackdrop.vue    # 错落 4 排真实电影海报墙 + 官方纯 CSS 地平线贝塞尔曲线消融弧
    ├── BrandLogo.vue       # 148x40 px 品牌 Logo 渲染组件（带悬浮平滑微放动效）
    └── logo.png            # 对应的 Logo 静态素材
```

---

## 🎨 关键视觉参数与修改位置

### 1. 输入框与“開始使用”按钮的圆角（当前：15px）
- **在 `activation_page.html` 中**：
  - 输入框：搜索 `.nf-input { border-radius: 15px; }`
  - 按钮：搜索 `.nf-cta-btn { border-radius: 15px; }`
- **在 `vue_components/ActivationView.vue` 中**：
  - 约第 404 行：`.nf-input { border-radius: 15px; }`
  - 约第 450 行：`.nf-cta-btn { border-radius: 15px; }`

### 2. 贝塞尔曲线最高点位置（当前：首屏视口约 81% 高度）
- **在 `activation_page.html` 中**：
  - 搜索 `.nf-hero { height: 92vh; min-height: 720px; }`
  - 调大 `height`（如 `96vh` 或 `100vh`）曲线顶点进一步下移；
  - 或者在 `.nf-curve-container { bottom: 0; }` 改为负值（如 `bottom: -20px`）直接下压。
- **在 `vue_components/ActivationView.vue` 中**：
  - 约第 386 行：`.nf-hero { height: 92vh; min-height: 720px; }`

### 3. 左上角 Logo 尺寸（当前：固有 370x100，渲染 148x40）
- 渲染大小：`148 × 40 px`
- 宽高比：`37 : 10` (3.7)
- 固有尺寸：`370 × 100 px`
- 图片路径：`logo.png`
