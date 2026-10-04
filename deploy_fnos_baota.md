# 🐂 飞牛 NAS (fnOS) 宝塔面板部署与平滑升级指南

> **适用场景**：在运行飞牛 NAS (fnOS) 的私有云设备中，通过**宝塔 Linux 面板**（Docker 容器版或宿主安装版）部署或升级 **Plove 1.0** 影视聚合与流媒体中继系统。  
> **编写日期**：2026-10-03  
> **目标版本**：Plove 1.0 (已合入全栈安全加固、HLS 媒体代理鉴权、单会话抢占与模块化重构)

---

## 🧭 架构与端口拓扑规划

在飞牛 NAS 的内网局域网中（假设 NAS 局域网 IP 为 `192.168.31.5`），系统通常分为三个部分：

```text
       [ 手机 / 平板 / 电视 / 电脑浏览器 ]
                       │
       ┌───────────────┴───────────────┐
       │     飞牛 NAS 内网或公网域名     │
       └───────────────┬───────────────┘
                       │ 访问端口（例：8099 或 4000）
       ┌───────────────▼───────────────┐
       │       宝塔 Nginx 静态站点      │ ──> 提供前端静态网页 (dist)
       └───────────────┬───────────────┘
                       │ location /api/ 内部反代
       ┌───────────────▼───────────────┐
       │   Plove 后端 FastAPI 微服务   │ ──> 监听 127.0.0.1:4001
       └───────────────┬───────────────┘
                       │ 数据库读写
       ┌───────────────▼───────────────┐
       │  MySQL 容器 (端口映射: 33306)  │ ──> 数据持久化 (激活码、设备绑定)
       └───────────────────────────────┘
```

| 组件名称 | 推荐端口 | 说明 |
| :--- | :--- | :--- |
| **前端站点 (Nginx)** | `8099` 或 `4000` | 终端用户观影入口、管理后台入口（对外开放） |
| **后端 API (Uvicorn)** | `127.0.0.1:4001` | 仅限内网/本地回环监听，由 Nginx 反代转发 |
| **MySQL 数据库** | `192.168.31.5:33306` | 飞牛 Docker 部署或宝塔自带 MySQL |

---

## ⚡ 场景一：已有旧版本的「平滑升级」步骤 (推荐)

如果你在飞牛 NAS 的宝塔中已经部署过早期版本，请按以下 5 步执行**不丢数据平滑升级**：

### 1. 进入后端目录拉取最新代码
打开宝塔面板 ➔ 左侧菜单 **【终端】**（或使用 SSH 连接飞牛 NAS）：
```bash
# 进入你原来部署的代码根目录（以 /www/wwwroot/Plove 为例）
cd /www/wwwroot/Plove

# 备份当前正在使用的 .env 配置文件（非常重要）
cp backend/.env backend/.env.backup

# 拉取 GitHub 远端 main 分支最新代码
git fetch --all
git reset --hard origin/main
```

### 2. 更新后端虚拟环境依赖
Plove 1.0 重构了模块化服务并增加了安全依赖，需要刷新安装包：
```bash
cd /www/wwwroot/Plove/backend

# 激活现有的虚拟环境（假设虚拟环境为 .venv 或 pyenv 管理）
source .venv/bin/activate
# 或者使用宝塔 Python 项目管理器对应的 python 路径
# /www/server/pyporject_evn/plove_venv/bin/pip install -e .

pip install --upgrade pip
pip install -e .
```

### 3. 更新 `backend/.env` 配置文件（必做安全项）
Plove 1.0 启用了严格弱口令拦截机制，原先的 `admin` 弱口令已被禁止。请编辑 `backend/.env`：
```bash
nano /www/wwwroot/Plove/backend/.env
# 或直接在宝塔面板的【文件】管理器中双击打开 backend/.env
```
确认并调整以下配置项：
```ini
PLOVE_ENV=prod
PLOVE_LOG_LEVEL=INFO
PLOVE_HOST=127.0.0.1
PLOVE_PORT=4001

# 🔴 关键：必须换成 32 字符以上的长随机强令牌（原弱口令 admin 已被拦截）
PLOVE_ADMIN_TOKEN=PloveAdm_9mK8xR2vL5tW7zY1bN4pQ6sJ3hF0cE8u

# 🔴 生产环境强制关停 Swagger 文档（防接口形状泄露）
PLOVE_DOCS_ENABLED=false

# 保持你原来的 MySQL 数据库连接配置不变
PLOVE_DATABASE_URL=mysql+pymysql://plove_test:你的密码@192.168.31.5:33306/plove_test?charset=utf8mb4
```

### 4. 重新构建前端静态资源
Plove 1.0 前端新增了 Hls.js 凭据自动挂载、海报智能防盗链中继及后台安全通信逻辑，需重新编译：
```bash
cd /www/wwwroot/Plove/frontend

# 安装依赖并打包
npm install
npm run build
```
打包成功后，将在 `/www/wwwroot/Plove/frontend/dist` 生成全新的前端静态页面。

### 5. 重启后端进程
- **如果使用宝塔【Python 项目管理器】**：
  在宝塔面板 ➔ 【网站】或【软件商店】 ➔ 【Python 项目管理器】中，找到 Plove 项目，点击 **【重启】**。
- **如果使用宝塔【Supervisor 进程守护】**：
  在 Supervisor 管理器列表中，找到对应进程，点击 **【重启】**。
- **命令行方式**：
  ```bash
  # 查看旧进程 PID 并优雅重启
  pkill -f "uvicorn app.main:app"
  nohup /www/wwwroot/Plove/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 4001 --workers 2 > /www/wwwroot/Plove/backend/run.log 2>&1 &
  ```

---

## 🛠️ 场景二：全新安装部署详细图文流程

### 第 1 步：宝塔环境与基础插件准备
在宝塔面板的 **【软件商店】** 中安装以下基础组件：
1. **Nginx**（版本推荐 1.22 ~ 1.26）
2. **Python 项目管理器**（或 **Supervisor 进程管理**）
3. **Node.js 版本管理器**（安装 Node.js `v18.x` 或 `v20.x`）
4. **MySQL**（若使用飞牛已有的 Docker MySQL，可不装）

---

### 第 2 步：下载代码与配置环境

1. 打开宝塔终端，克隆最新仓库代码到网站目录：
   ```bash
   cd /www/wwwroot
   git clone https://github.com/juzi0331/Plove.git Plove
   cd /www/wwwroot/Plove/backend
   ```
2. 创建 Python 运行虚拟环境并安装依赖：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .
   ```
3. 复制并编辑环境配置文件：
   ```bash
   cp .env.example .env
   nano .env
   ```
   主要修改：
   - `PLOVE_ENV=prod`
   - `PLOVE_ADMIN_TOKEN`：设置高强度运维密钥（记录下来，后台登录要用）
   - `PLOVE_DATABASE_URL`：填写真实的 MySQL 连接地址（如 `mysql+pymysql://用户:密码@192.168.31.5:33306/库名?charset=utf8mb4`）
4. 执行数据库建表初始化：
   ```bash
   python tools/init_db.py
   # 签发首个 30 天激活码（备用）
   python tools/issue_code.py --days 30
   ```

---

### 第 3 步：在宝塔中托管后端服务

推荐使用 **【Supervisor 进程管理器】** 或 **【Python 项目管理器】**：

#### 方案 A：使用 Supervisor 进程管理器（最稳定）
1. 宝塔面板 ➔ 打开【Supervisor 进程管理】➔ 点击 **【添加守护进程】**；
2. 填写参数：
   - **名称**：`plove-api`
   - **启动用户**：`www` 或 `root`
   - **运行目录**：`/www/wwwroot/Plove/backend`
   - **启动命令**：
     ```bash
     /www/wwwroot/Plove/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 4001 --workers 2
     ```
   - **进程数量**：`1`
3. 保存后点击启动，观察日志确认显示 `Uvicorn running on http://127.0.0.1:4001`。

---

### 第 4 步：编译前端并配置 Nginx 站点

1. 编译前端：
   ```bash
   cd /www/wwwroot/Plove/frontend
   npm install
   npm run build
   ```
   产物位于 `/www/wwwroot/Plove/frontend/dist`。

2. 在宝塔面板 ➔ **【网站】** ➔ **【添加站点】**：
   - **域名**：填写你的飞牛 NAS 内网 IP + 端口（例如 `192.168.31.5:8099`），或者你的外网 DDNS 域名。
   - **根目录**：指向前端打包目录 `/www/wwwroot/Plove/frontend/dist`。
   - **PHP 版本**：纯静态。

3. 点击站点名 ➔ 进入 **【配置文件】**，将配置替换或补充为以下完整的反向代理配置：

```nginx
server {
    listen 8099;
    server_name 192.168.31.5;

    root /www/wwwroot/Plove/frontend/dist;
    index index.html;

    # 客户端上传限制
    client_max_body_size 50M;

    # SPA 单页面路由刷新防 404
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 与 HLS 流媒体切片反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:4001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 针对流媒体中继非常关键的优化：关闭缓冲、长超时防切片断流
        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 静态资源强缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # 安全防护响应头
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
}
```
保存配置后，点击 **【重载配置】**。

---

## 🔍 验证与后台管理登录

1. **测试前台用户端**：
   - 浏览器打开 `http://192.168.31.5:8099/`；
   - 输入先前生成的激活码激活设备，进入电影主页，点击播放测试视频秒播与海报加载。
2. **测试运维控制台**：
   - 浏览器打开 `http://192.168.31.5:8099/_manage/login`；
   - 输入在 `.env` 中配置的 `PLOVE_ADMIN_TOKEN` 强令牌；
   - 登录进入控制台，可进行站点管理、节点测速、激活码批量生成与海报代理缓存清理。

---

## 常见问题排查 (Troubleshooting)

### Q1: 提示 `401 Unauthorized` 或视频无法播放？
- **排查**：Plove 1.0 给所有代理端点（`/api/v1/proxy/stream/*`）增加了鉴权。如果升级后前端未重新 `npm run build`，播放器可能不会携带凭据导致 401。
- **解决**：在 `frontend` 目录重新执行 `npm run build`，并清除浏览器本地缓存刷新。

### Q2: 报错 `MySQL (1130, "Host ... is not allowed to connect to this MySQL server")`？
- **原因**：飞牛 NAS 容器访问 MySQL 时 IP 权限未开放。
- **解决**：进入 MySQL 执行授权命令：
  ```sql
  GRANT ALL PRIVILEGES ON plove_test.* TO 'plove_test'@'%' IDENTIFIED BY '你的密码';
  FLUSH PRIVILEGES;
  ```

### Q3: 登录后台提示 `管理令牌过于简单，存在严重安全隐患`？
- **原因**：Plove 1.0 的安全防御拦截了 `admin`, `123456`, `password` 等弱口令。
- **解决**：在 `backend/.env` 中更换 `PLOVE_ADMIN_TOKEN` 为包含字母大小写与数字的强密钥（长度至少 16 位以上）。

### Q4: 飞牛 NAS 外网访问如何配置？
- 飞牛 NAS 内置了 **fnOS 远程访问 (fnconnect)** 或可在路由器配置 **端口转发**（将外网端口映射到 Nginx 站点的 `8099`）；
- 若配置了 HTTPS / SSL，请确保在宝塔站点中一键申请 Let's Encrypt 证书并强制开启 HTTPS。
