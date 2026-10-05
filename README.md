# 🎬 Plove 影视聚合系统 —— 全栈架构与接手部署指南

> **Plove 1.0** 是一套现代化全端自适应的影视聚合流媒体系统，集成了**终端沉浸观影（Netflix 级视觉）**、**自研流媒体中继与防盗链代理**、**源站加密海报动态流式解密与图床加速**、**Telegram 官方机器人智能运维中枢**、**现代安全运维控制大屏**以及**纯本地爬虫自动化工坊**。

---

## 🛠️ 技术栈总览

### 1. 后端技术栈 (Backend)
- **核心框架**：Python 3.11+ / Python 3.12 / FastAPI 0.115+ / Uvicorn 0.30+
- **数据与 ORM**：SQLAlchemy 2.0（生产环境推荐 MySQL 8.0，本地/测试环境支持 SQLite 内存库）、PyMySQL、Cryptography
- **架构契约**：Pydantic v2 强类型约束，全局输出统一 JSON 响应信封（`Envelope[T]`）与单一来源错误码系统（`ErrorCode`）
- **高并发与可用性**：
  - **SingleFlight 并发合并锁**：相同剧集流地址请求并发时合并为一个子进程，防止击穿源站
  - **两级动态限流与熔断器 (Circuit Breaker)**：每站并发上限 2，全站并发上限 4，连续失败达阈值自动触发冷却熔断
  - **多层级内存缓存**：首页与分类列表智能 LRU 缓存，播放直链永不缓存保证时效
- **流媒体与代理引擎**：
  - HLS (`m3u8` 清单 / `ts` 媒体切片 / `AES-128` 密钥) 递归解析改写与中继
  - 动态站点伪装容器解封装（还原标准 MPEG-TS 串流）
  - 第三方海报图片防盗链欺骗代理与本地持久化磁盘缓存（ETag 304 协商，WebP 实时转换）
- **加密海报动态流式解密引擎**：
  - 支持源站 AES-128-CBC / ECB / GCM 前端加密封面动态流式解密
  - 动态 URL 前缀替换路由与免费 CDN 边缘代理配置
  - 智能 AI 逆向配置导入解析器
- **代理节点池与网络中继**：
  - 集成 Xray 核心内核，支持 VLESS、VMess、Shadowsocks、Trojan 及 HTTP/SOCKS5 协议节点池
  - 为爬虫站点采集及外部通知提供智能代理链路穿透
- **Telegram 官方机器人运维中心 (Webhooks)**：
  - 专属 Telegram 官方 Bot API 协议，支持国内网络环境 HTTP / SOCKS5 代理穿透与 Bot 自动探测
  - **9 大核心监控规则矩阵**：站点巡检自检、内容源连续异常与熔断、探针自愈恢复、代理节点离线、激活码首次激活、同码多端冲突踢号、接口防刷限流告警、每日运营大盘、集群启动就绪
  - **原生 HTML 富文本广播**：支持加粗 `<b>`、等宽代码块 `<code>`、引用块 `<blockquote>`、剧透遮罩 `<tg-spoiler>` 等原生渲染
  - **站点清单与连通性自检报告**：一键生成全站内容源健康度、熔断保护状态与网络代理清单推送到 Telegram
- **安全与风控体系**：
  - 纯标准库实现**内存滑动窗口速率限制器**（防激活码暴力破解，超限返回 429）
  - 管理员强令牌校验（使用 `secrets.compare_digest` 防时序侧信道攻击，强校验拦截常见弱口令）
  - 代理端点设备令牌 (`X-Device-Token`) / 管理员凭证双轨访问守卫
  - 深度 SSRF 探测拦截（拦截内网 IP、云厂商元数据、高危端口）
  - 全局安全防护响应头（`nosniff`, `DENY`, `X-XSS-Protection`）

### 2. 前端技术栈 (Frontend)
- **核心底座**：Vue 3.5+（Composition API / `<script setup>`）/ TypeScript 5.7+ / Vite 6.0+
- **状态管理与路由**：Pinia 2.3+ / Vue Router 4.5+
- **UI 组件体系**：
  - **Element Plus**：安全运维控制台全功能交互、状态大屏与现代化卡片弹窗
  - **Vant 4**：移动端与 H5 响应式组件适配
  - **原生 CSS (Vanilla CSS)**：1:1 像素级复刻 Netflix 沉浸式暗黑极简视觉与流式微动画
  - **全局弹窗居中引擎**：全站弹窗视口绝对居中保护，Header/Footer 永不溢出视口，内部自适应平滑滚动
- **播放引擎**：Hls.js 1.5+（支持 AES-128 软解兜底、起播容错自愈、掉线平滑重试与 iOS 原生 HLS 回退）
- **跨端适配**：纯静态无状态编译，支持 Web、PWA 以及使用 Capacitor 封装打包为 iOS IPA 与 Android APK

### 3. 爬虫自动化工坊 (Crawler & SDK)
- **底层工具箱**：自研 `crawler_kit`（零大型第三方依赖，仅依托 Python 标准库实现高效抓取与 HTML 文本解析）
- **安全沙盒**：严格的 AST 静态语法审查，禁止非安全系统调用
- **进程级隔离**：独立子进程调度，严格标准信封通信（Stdout 输出单行 JSON 信封，调试日志走 Stderr）
- **Web 智能工坊**：纯本地监听（127.0.0.1:8088），支持 AI 启发式 Prompt 生成与 5 步递进式全链路冒烟体检

---

## 📁 目录规范与职责边界

```text
Plove1.0/
├── frontend/             # 前端工程（Vue 3 + Vite + Vant + Element Plus + Hls.js）
│   ├── src/
│   │   ├── admin/        # 安全运维控制台
│   │   │   ├── theme.css # 全局管理端主题与视口居中弹窗引擎
│   │   │   ├── views/
│   │   │   │   ├── DashboardView.vue      # 总览看板（源站流量/并发大盘与自建站指标）
│   │   │   │   ├── ImageProxyView.vue     # 图片缓存与海报防盗链总控
│   │   │   │   ├── SystemNoticeView.vue   # 全站公告与停服维护广播中心
│   │   │   │   ├── WebhooksView.vue       # Telegram 机器人管理与推送中心
│   │   │   │   ├── image-proxy/           # 图床加速路由与加密海报动态解密模块
│   │   │   │   ├── notice/                # 维护闸门与广播模态配置
│   │   │   │   ├── proxy-nodes/           # Xray 代理节点池管理
│   │   │   │   ├── codes/                 # 激活码资产与绑定设备管控
│   │   │   │   └── sites/                 # 站点适配编排与策略详情
│   │   ├── api/          # 跨端客户端 API 与会话凭证管理
│   │   ├── components/   # Netflix 风格卡片、导航栏等公共组件
│   │   ├── stores/       # Pinia 状态树（设备激活态、站点源列表等）
│   │   ├── views/        # 用户端页面（落地页/首页/分类/详情/播放器）
│   │   └── utils/        # 格式化、海报代理智能包装工具库
│   ├── vite.config.ts    # 监听 0.0.0.0:4000，反代 /api 至后端 4001
│   └── .env              # 前端配置（VITE_ADMIN_PATH 安全入口等）
│
├── backend/              # 后端核心微服务（FastAPI + SQLAlchemy + Pydantic v2）
│   ├── app/
│   │   ├── api/          # 薄路由层（v1/catalog, v1/activation, v1/system, v1/admin/）
│   │   ├── core/         # 基础内核（配置、安全SSRF、日志、限流器、中间件）
│   │   ├── crawler/      # 爬虫子进程调度器、并发守卫与注册表
│   │   ├── db/           # 数据库引擎与会话工厂
│   │   ├── models/       # SQLAlchemy 数据表模型（ActivationCode, Device, SiteSetting）
│   │   ├── schemas/      # Pydantic 契约模型（唯一来源）
│   │   └── services/     # 核心业务服务（流媒体代理、爬虫编排、激活码、Webhook服务）
│   │       ├── image_proxy/ # 海报防盗链中继与动态解密处理
│   │       └── webhook/     # Telegram 机器人调度、签名限流、消息美化与审计
│   ├── data/             # 图片代理本地持久化磁盘缓存（img_cache）
│   ├── tests/            # 自动化单元、集成与安全回归测试套件
│   ├── .env              # 后端环境变量（运行环境、密钥、数据库连接）
│   └── pyproject.toml    # Python 项目配置与标准依赖清单
│
├── crawler/              # 爬虫自动化工坊（SDK + 站点集 + 独立体检控制台）
│   ├── crawler_kit/      # 纯标准库爬虫工具包（Client, parse, clean, cli）
│   ├── sites/            # 站点独立采集适配器（本地编写，动态插拔）
│   └── service/          # 本地爬虫 Web 探索与全链路冒烟测试工坊（127.0.0.1:8088）
│
└── README.md             # 本系统全栈架构指南
```

---

## 🌐 端口与网络拓扑

| 服务名称 | 监听绑定 | 访问路径 | 职责说明 |
| :--- | :--- | :--- | :--- |
| **服务总控直达 (Portal)** | `0.0.0.0:4001` | `http://<ip>:4001/` | 一屏聚合导航（带防护密码，便于快速跳转各端） |
| **前端用户端 (Frontend)** | `0.0.0.0:4000` | `http://<ip>:4000/` | 终端影视浏览与播放；请求由 Vite / 反代服务转发至后端 |
| **安全运维控制台 (Manage)** | `0.0.0.0:4000` | `http://<ip>:4000/_manage` | 安全混淆入口；用于站点启停、发码、Telegram 机器人配置 |
| **后端 API 网关 (Backend)** | `0.0.0.0:4001` | `http://<ip>:4001/api/v1` | 业务与代理接口；生产环境强制禁用 `/docs` 以防泄露接口形状 |
| **爬虫体检工坊 (Crawler)** | `127.0.0.1:8088` | `http://127.0.0.1:8088/` | **仅限纯本地访问**；提供站点 AI 提示词生成与全链路体检沙盒 |

---

## 🚀 5 分钟本地开发极速起跑

### 1. 启动后端核心服务 (端口 4001)

```bash
cd backend

# 创建并激活虚拟环境 (以 Windows 为例，Linux/macOS 使用 source .venv/bin/activate)
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"

# 检查 .env 配置（设置 PLOVE_ADMIN_TOKEN 强密码及数据库，默认支持 SQLite）
# 启动 Uvicorn 服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 4001 --reload
```
> 健康检查接口：`http://127.0.0.1:4001/api/v1/health`

### 2. 启动前端用户端与控制台 (端口 4000)

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```
> - 前台用户访问：`http://127.0.0.1:4000/`  
> - 后台控制台入口：`http://127.0.0.1:4000/_manage/login`（输入 `.env` 中配置的 `PLOVE_ADMIN_TOKEN`）

### 3. 运行全量测试验证

```bash
# 运行后端单元测试与安全专项测试套件
cd backend
pytest
```

---

## 🛡️ 安全与生产部署规范

### 1. 环境变量脱敏示例 (`backend/.env`)

```env
# 运行环境: development | staging | production
ENVIRONMENT=production

# 管理员安全强令牌 (严禁使用弱口令，系统启动时会自动校验强度)
PLOVE_ADMIN_TOKEN=YourVeryStrongAdminToken_AtLeast16Chars_2026!

# 数据库连接串 (推荐 MySQL 8.0)
DATABASE_URL=mysql+pymysql://plove_user:YourDbPassword@127.0.0.1:3306/plove_db?charset=utf8mb4

# 允许跨域前端白名单
CORS_ORIGINS=https://your-domain.com

# 基础目录与代理配置
STORAGE_DIR=data
```

### 2. Telegram 机器人配置与代理穿透

在管理后台「Telegram 机器人管理」模块中，支持配置官方 Bot 凭证：
- **Bot Token 示例**：`123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_EXAMPLE`
- **目标频道/群组 Chat ID 示例**：`-1001234567890`
- **网络代理穿透**：针对国内无直连网络环境的服务器，可在弹窗中直接选用内置节点池中转，或填入独立代理地址（如 `http://127.0.0.1:7890`）。

### 3. 节点网络池管理 (Xray 集成)

系统内置对 Xray-core 的直接进程管理与配置下发：
- 支持标准 `vless://` / `vmess://` / `ss://` / `trojan://` 节点连接串一键解析。
- 系统自动在本机开放独立本地端口（如 `127.0.0.1:10808`），为指定爬虫站点无感打通中转通道，杜绝封禁风险。

---

## 📄 开源与商业授权声明

本项目代码资产受专有软件版权保护。未经授权许可，严禁擅自转售、二次打包分发或用于未经许可的商业运营。
