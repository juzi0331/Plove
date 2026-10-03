# 🎬 Plove 影视聚合系统 —— 全栈架构与接手部署指南

> **Plove 1.0** 是一套现代化全端自适应的影视聚合流媒体系统，集成了**终端沉浸观影（Netflix 级视觉）**、**自研流媒体中继与防盗链代理**、**安全运维控制台**以及**纯本地爬虫自动化工坊**。

---

## 🛠️ 技术栈总览

### 1. 后端技术栈 (Backend)
- **核心框架**：Python 3.11+ / FastAPI 0.115+ / Uvicorn 0.30+
- **数据与 ORM**：SQLAlchemy 2.0（生产环境推荐 MySQL 8.0，本地/测试环境支持 SQLite 内存库）、PyMySQL、Cryptography
- **架构契约**：Pydantic v2 强类型约束，全局输出统一 JSON 响应信封（`Envelope[T]`）与单一来源错误码系统（`ErrorCode`）
- **高并发与可用性**：
  - **SingleFlight 并发合并锁**：相同剧集流地址请求并发时合并为一个子进程，防止击穿源站
  - **两级动态限流与熔断器 (Circuit Breaker)**：每站并发上限 2，全站并发上限 4，连败 5 次自动触发冷却熔断
  - **多层级内存缓存**：首页与分类列表智能 LRU 缓存，播放直链永不缓存保证时效
- **流媒体与代理引擎**：
  - HLS (`m3u8` 清单 / `ts` 媒体切片 / `AES-128` 密钥) 递归解析改写与中继
  - 动态站点伪装容器解封装（还原标准 MPEG-TS 串流）
  - 第三方海报图片防盗链欺骗代理与本地持久化缓存（ETag 304 协商）
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
  - **Element Plus**：安全运维控制台全功能交互
  - **Vant 4**：移动端与 H5 响应式组件适配
  - **原生 CSS (Vanilla CSS)**：1:1 像素级复刻 Netflix 沉浸式暗黑极简视觉与流式微动画
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
│   │   ├── admin/        # 安全运维控制台全套源码（站点编排/缓存中心/发码/节点监控）
│   │   ├── api/          # 跨端客户端 API 与会话凭证管理
│   │   ├── components/   # Netflix 风格卡片、导航栏等公共组件
│   │   ├── stores/       # Pinia 状态树（设备激活态、站点源列表等）
│   │   ├── views/        # 用户端页面（落地页/首页/分类/详情/播放器沙盒）
│   │   └── utils/        # 格式化、海报代理智能包装工具库
│   ├── vite.config.ts    # 监听 0.0.0.0:4000，反代 /api 至后端 4001
│   └── .env              # 前端配置（VITE_ADMIN_PATH 安全入口等）
│
├── backend/              # 后端核心微服务（FastAPI + SQLAlchemy + Pydantic v2）
│   ├── app/
│   │   ├── api/          # 薄路由层（v1/catalog, v1/activation, v1/system, v1/admin/）
│   │   ├── core/         # 基础内核（配置、安全SSRF、日志、异常处理、限流器、中间件）
│   │   ├── crawler/      # 爬虫子进程调度器、并发守卫与注册表
│   │   ├── db/           # 数据库引擎与会话工厂
│   │   ├── models/       # SQLAlchemy 数据表模型（ActivationCode, Device, SiteSetting）
│   │   ├── schemas/      # Pydantic 契约模型（唯一来源）
│   │   └── services/     # 核心业务服务（媒体代理、爬虫编排、激活码、站点控制）
│   ├── data/             # 图片代理本地持久化磁盘缓存（img_cache）
│   ├── tests/            # 308+ 自动化单元、集成与安全回归测试套件
│   ├── .env              # 后端环境变量（运行环境、密钥、数据库连接）
│   └── pyproject.toml    # Python 项目配置与标准依赖清单
│
├── crawler/              # 爬虫自动化工坊（SDK + 站点集 + 独立体检控制台）
│   ├── crawler_kit/      # 纯标准库爬虫工具包（Client, parse, clean, cli）
│   ├── sites/            # 站点独立采集适配器（如 ai2048.py, ncat21.py 等）
│   └── service/          # 本地爬虫 Web 探索与全链路冒烟测试工坊（127.0.0.1:8088）
│
├── security_audit_report.md # 安全审计报告（防破解、防绕过、鉴权加固）
└── README.md             # 本接手指南
```

---

## 🌐 端口与网络拓扑

| 服务名称 | 监听绑定 | 访问路径 | 职责说明 |
| :--- | :--- | :--- | :--- |
| **服务总控直达 (Portal)** | `0.0.0.0:4001` | `http://<ip>:4001/` | 一屏聚合导航（带防护密码，便于快速跳转各端） |
| **前端用户端 (Frontend)** | `0.0.0.0:4000` | `http://<ip>:4000/` | 终端影视浏览与播放；请求由 Vite / 反代服务转发至后端 |
| **安全运维控制台 (Manage)** | `0.0.0.0:4000` | `http://<ip>:4000/_manage` | 安全混淆入口；用于站点启停、广告清洗、激活码管理 |
| **后端 API 网关 (Backend)** | `0.0.0.0:4001` | `http://<ip>:4001/api/v1` | 业务与代理接口；生产环境强制禁用 `/docs` 以防泄露接口形状 |
| **爬虫体检工坊 (Crawler)** | `127.0.0.1:8088` | `http://127.0.0.1:8088/` | **仅限纯本地访问**；提供站点 AI 提示词生成与全链路体检沙盒 |

---

## 🚀 5 分钟本地开发极速起跑

### 1. 启动后端核心服务 (端口 4001)

```bash
cd backend

# 创建并激活虚拟环境 (以 Windows 为例，Linux/macOS 使用 bin/activate)
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

### 3. 启动爬虫本地工坊（端口 8088，可选）

```bash
# 在项目根目录下执行
python -m uvicorn crawler.service.main:app --host 127.0.0.1 --port 8088 --reload
```
> 爬虫 Web 体检工作台：`http://127.0.0.1:8088/`

### 4. 运行全量测试验证

```bash
# 运行后端单元测试与安全专项测试套件（308+ 测试项全绿）
cd backend
pytest

# 运行前端 TypeScript 强类型校验
cd ../frontend
npm run typecheck
```

---

## 🐧 简易 VPS 生产部署指南

推荐使用 **Ubuntu 22.04+ / Debian 11+**，以 **Systemd 守护后端进程 + Nginx 动静分离反代** 方式进行极简生产部署。

### 步骤 1：VPS 基础环境安装

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv nodejs npm nginx git
```

### 步骤 2：部署后端服务 (Systemd 守护)

1. 克隆代码并安装后端依赖：
   ```bash
   cd /var/www/
   git clone <your-repo-url> Plove
   cd /var/www/Plove/backend

   python3 -m venv .venv
   ./.venv/bin/pip install --upgrade pip
   ./.venv/bin/pip install -e .
   ```

2. 配置生产环境配置文件 `/var/www/Plove/backend/.env`：
   ```ini
   PLOVE_ENV=prod
   PLOVE_LOG_LEVEL=INFO
   PLOVE_HOST=127.0.0.1
   PLOVE_PORT=4001
   # 必须使用生成的强随机管理令牌（至少 32 字符）
   PLOVE_ADMIN_TOKEN=换成你的长随机高强度密钥_至少32位
   # 生产环境强制关停 Swagger 交互文档
   PLOVE_DOCS_ENABLED=false
   # 数据库连接（支持 MySQL 或 本地 SQLite）
   PLOVE_DATABASE_URL=sqlite:////var/www/Plove/backend/data/plove.db
   ```

3. 创建 Systemd 守护服务文件：
   ```bash
   sudo nano /etc/systemd/system/plove-backend.service
   ```
   写入以下内容：
   ```ini
   [Unit]
   Description=Plove Backend API Service
   After=network.target

   [Service]
   Type=simple
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/Plove/backend
   ExecStart=/var/www/Plove/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 4001 --workers 2
   Restart=always
   RestartSec=5
   EnvironmentFile=/var/www/Plove/backend/.env

   [Install]
   WantedBy=multi-user.target
   ```

4. 启动并设置开机自启：
   ```bash
   sudo chown -R www-data:www-data /var/www/Plove/backend/data
   sudo systemctl daemon-reload
   sudo systemctl enable --now plove-backend
   sudo systemctl status plove-backend
   ```

### 步骤 3：编译前端静态包

```bash
cd /var/www/Plove/frontend
npm install
npm run build
# 构建产物将生成在 /var/www/Plove/frontend/dist 目录中
```

### 步骤 4：配置 Nginx 反向代理与动静分离

编辑 Nginx 站点配置：
```bash
sudo nano /etc/nginx/sites-available/plove
```

写入标准反向代理模板（请将 `your-domain.com` 替换为真实域名）：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 客户端上传与缓冲区
    client_max_body_size 50M;

    # 前端静态资源托管
    root /var/www/Plove/frontend/dist;
    index index.html;

    # SPA 路由兜底
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 及流媒体中继反代
    location /api/ {
        proxy_pass http://127.0.0.1:4001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 流媒体切片长连接与关闭代理缓冲
        proxy_buffering off;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # 安全头
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
}
```

启用站点并启动 Nginx：
```bash
sudo ln -s /etc/nginx/sites-available/plove /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> 💡 **申请免费 HTTPS 证书（强烈建议）**：
> ```bash
> sudo apt install -y certbot python3-certbot-nginx
> sudo certbot --nginx -d your-domain.com
> ```

---

## 🔒 核心安全架构说明

1. **设备单在线抢占鉴权**：
   - 激活码为时长制，首次激活起算时长；
   - 凭证由后端直接签发 `device_token`（非客户端自报），多设备轮流登录时后登入者自动将前一设备踢下线（`SESSION_KICKED`），杜绝账号跨设备多开白嫖。
2. **代理资源访问守卫**：
   - 所有 `/api/v1/proxy/stream/*`（m3u8/分片/密钥）与 `/api/v1/proxy/image` 均挂载鉴权守卫；
   - 外部未激活或未携带凭证的抓包拉流一律返回 `401 Unauthorized`，无法将服务器当做公网免费 CDN。
3. **激活防暴力枚举 (Anti-Brute Force)**：
   - 接口级滑动窗口限流器，单个 IP 激活尝试限制 5 次/分钟，高频触发 `429 RATE_LIMITED`；
   - 统一错误消息回包，激活码失效或不存在统一返回“激活码无效或已到期”，消除枚举有效码的信息泄露隐患。
4. **管理控制台蜜罐防御**：
   - 前台源码中默认使用混淆路径 `/_manage`，禁止使用常见的 `/admin`；
   - 对外公开的 `/docs` 和 `/openapi.json` 在 `PLOVE_ENV=prod` 时被强制切断，保护底层接口形状不被逆向探测。

---

祝您使用愉快！如有疑问或建议，欢迎联系项目维护者。
