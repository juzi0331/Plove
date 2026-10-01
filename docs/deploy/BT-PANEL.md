# 用宝塔面板部署（替代裸机 systemd + nginx）

宝塔把 systemd、nginx、MySQL、证书、定时任务都包进界面了，所以**大部分步骤不用敲命令**。
[CHECKLIST.md](CHECKLIST.md) 的**顺序和验证方法照样适用**，只是把"敲命令"换成"点界面"。

> 界面上的叫法会随宝塔版本略有不同（Python 项目管理器的位置尤其常见变体）。
> 下面写的是**概念位置**；找不到时在软件商店里搜 "Python" 即可。

## 一、该用哪些、不该用哪些

| 仓库里的东西 | 在宝塔上 | 为什么 |
| --- | --- | --- |
| [CHECKLIST.md](CHECKLIST.md) | ✅ **照着走** | 顺序和验证方法是通用的 |
| [.env.prod.example](.env.prod.example) | ✅ 用 | 配置一模一样，删掉已被宝塔接管的项即可 |
| [check.sh](check.sh) | ✅ **跑它** | 面板不会告诉你"源站认不认这台机器" |
| [backup.sh](backup.sh) | ⚖️ **二选一** | 用宝塔的"计划任务 → 备份数据库"更省事；别两套同时跑 |
| [systemd/plove-backend.service](systemd/plove-backend.service) | ❌ **不用** | 宝塔自己管进程（Python 项目） |
| [nginx/plove.conf](nginx/plove.conf) | ⚖️ 参考 | 用界面的"反向代理"生成；只有要加超时那几行时才手改宝塔生成的配置 |

## 二、宝塔**吃掉的三个错误信息**（所以顺序不能变）

面板的好处是省事，代价是**出问题时它把错误吞了**：你只看到"服务未启动"，
看不到那段 traceback。所以**顺序必须是**：

```
1. 宝塔终端里 ▶ 先跑爬虫（验证源站认不认这台机器）
2. 宝塔终端里 ▶ 建 venv、装依赖、跑 pytest
3. 宝塔终端里 ▶ 手动 uvicorn 跑起来 + curl /health
4. 上面都通了 ▶ 才交给"Python 项目"托管
5. 最后 ▶ 面板里配反向代理 + 证书
```

**先把东西跑起来，再交给任何"管理器"。** 反过来做，你分不清是"我的配置错"
还是"面板的配置错"。

## 三、宝塔版的四步

### 1. 终端里先验源站（**最重要**）

面板 → **终端**，然后：

```bash
cd /www/wwwroot/plove            # 或者你放代码的地方
python3 crawler/sites/ncat21.py home | head -c 300; echo
time python3 crawler/sites/ncat21.py home > /dev/null
```

判断标准和 [CHECKLIST 第 2 步](CHECKLIST.md) 完全一样：
**有没有数据 / 花了多久 / 闸门还灵不灵**。被拦就别往下走了，先解决这个。

### 2. 终端里把后端跑起来

```bash
cd /www/wwwroot/plove/backend
python3 -m venv .venv                 # 要 3.11+，python3 --version 先看一眼
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest            # 期望 164 passed, 2 skipped

# 配置
cp ../deploy/.env.prod.example .env
chmod 600 .env
vi .env                               # 填数据库密码、PLOVE_ADMIN_TOKEN
.venv/bin/python tools/init_db.py     # 建表

# 手动跑一次（前台，看得到报错）
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个终端 `curl -s http://127.0.0.1:8000/api/v1/health; echo`，看到 `ok:true` 就成了。

### 3. 交给面板托管

**软件商店 → Python 项目管理器**（新版可能是 **网站 → Python 项目**）。

| 项 | 填什么 |
| --- | --- |
| 项目路径 | `/www/wwwroot/plove/backend` —— **必须指到 `backend/`**，因为启动用的是 `app.main:app` |
| Python 版本 | **3.11 或更高** |
| 启动方式 | uvicorn / 自定义命令 |
| 启动命令 | `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| 端口 | `8000`（**只给本机 nginx 用**，不要在防火墙里对外放行） |

⚠️ **不要选"多进程 / workers > 1"，也不要用默认的多 worker gunicorn。**

缓存、防击穿、熔断、预热执行器**全是进程内状态**：多 worker 会让它们各自为政 ——
缓存命中率除以 N、**预热会跑 N 遍**（等于把源站请求量乘 N）。
如果面板只让填 gunicorn，那就用 `gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app`
（关键是那个 `-w 1`）。理由见 [README.md](README.md)。

**环境变量只在 `.env` 里配。** 面板上如果也有填环境变量的地方，**留空** ——
环境变量的优先级高于 `.env`，两处都填就会出现"我明明改了 .env 怎么不生效"。

启起来之后：

```bash
curl -s http://127.0.0.1:8000/api/v1/health; echo
```

### 4. 面板里配反向代理 + 证书

**网站 → 添加站点**（纯静态即可，反代不需要 PHP）→ 填你的域名 →
**设置 → 反向代理 → 添加反向代理**：

```
代理名称：plove
目标 URL：http://127.0.0.1:8000
发送域名：$host
```

**设置 → SSL → Let's Encrypt** 一键签证书，然后打开**强制 HTTPS**。

然后加两处**超时**（宝塔生成的 nginx 配置里）：

```nginx
proxy_connect_timeout 5s;
proxy_send_timeout    75s;
proxy_read_timeout    75s;
```

**为什么非要加：** 应用的单请求最坏情况是"爬虫超时 25s + 排队 20s" ≈ 45s。
如果 nginx 用默认值先把连接掐掉，你看到的是一张 nginx 的 504 HTML 页，
而不是应用那个**带 `request_id` 的 JSON 错误信封** —— 后者才能拿去查日志。

宝塔的站点配置在 `/www/server/panel/vhost/nginx/<域名>.conf`，
可以直接改那个文件（**别改 `/etc/nginx/nginx.conf`**，那个是面板自己的），
改完在面板里点"重载配置"。

**验证：**

```bash
curl -sI https://你的域名/api/v1/health | head -3   # 200
curl -sI http://你的域名/api/v1/health  | head -3   # 301
```

最后跑自检（面板终端里）：

```bash
cd /www/wwwroot/plove
BASE_URL=https://你的域名 ADMIN_TOKEN=你的后台令牌 bash deploy/check.sh
```

## 四、宝塔上的 MySQL：一个**必踩**的坑

```
Access denied for user 'plove'@'127.0.0.1'
```

宝塔建库时默认授权的来源是 **`localhost`**，而我们的应用是走 **TCP 连 `127.0.0.1`** 的。

在 MySQL 眼里这是**两个不同的来源**：`localhost` 走 Unix socket，`127.0.0.1` 走 TCP。
所以授权了 `@'localhost'` ≠ 允许 `@'127.0.0.1'`。

改法（宝塔终端里）：

```bash
mysql -u root -p
```

```sql
-- 看当前授权的是哪个来源
SELECT user, host FROM mysql.user WHERE user = 'plove';

-- 补一个 TCP 来源的授权（密码和建库时一致）
GRANT ALL PRIVILEGES ON plove.* TO 'plove'@'127.0.0.1' IDENTIFIED BY '你的密码';
FLUSH PRIVILEGES;
```

这个坑在开发时已经踩过一次（那次是因为 NAS 上的库只授权了 `localhost`），
只是原因不同：那次是跨机器，这次是同机器但走 TCP。

**别图省事授权成 `'plove'@'%'`** —— 那等于允许任何来源连你的数据库，
而数据库**完全不需要**对外暴露（它和 API 在同一台机器上）。

另外顺手确认两项：

```sql
SHOW VARIABLES LIKE 'character_set_database';   -- 要 utf8mb4
SELECT @@sql_mode;                              -- 要含 STRICT_TRANS_TABLES
```

## 五、备份：用宝塔的"计划任务"

**计划任务 → 添加任务 → 类型：备份数据库**：

| 项 | 值 |
| --- | --- |
| 任务类型 | 备份数据库 |
| 数据库 | `plove` |
| 备份到 | 本地（**日后想办法再传一份到别处**） |
| 保留份数 | 14 |
| 执行周期 | 每天 04:10 |

比 [backup.sh](backup.sh) 省事，所以**用这个就别再挂 crontab 那一条**，
否则一天会备两次（不致命，但没必要）。

⚠️ **但还是那句话：没演练过的备份等于没有备份。**
宝塔的备份目录在 `/www/backup/database/`，去那里看一眼：

```bash
ls -lh /www/backup/database/            # 有文件、大小合理吗
gunzip -c /www/backup/database/xxx.sql.gz | head -20   # 像 SQL 吗
```

## 六、公网上的宝塔面板本身：必须加固

**这是这套方案最大的风险面。** 面板被攻破 = 整台机器沦陷（它能执行任意命令、
能改任意文件、能读到你所有的密码）。

最少做这四件事（**面板 → 设置**）：

1. **改掉默认的 8888 端口**（换个高位端口）；
2. **面板开 HTTPS**；
3. **开二次验证**（动态口令）；
4. **限制访问 IP**：能固定 IP 就填白名单；不能的话至少别把面板端口放进公网扫描的常见列表。

另外：面板的**默认密码改掉**、**别用 root 直连 SSH**（用密钥 + 非 22 端口）、
宝塔的"安全"页里确认 **3306 和 8000 没有对外放行**。

## 七、常见问题（宝塔版）

| 现象 | 原因 / 怎么办 |
| --- | --- |
| 面板显示"服务未启动"，但没细节 | 去看项目的**日志文件**（面板里有），或者干脆用终端手动跑一遍看报错 |
| `.env` 改了不生效 | 面板里也配了同名环境变量（**优先级更高**）；或者进程没重启 |
| `Access denied for user 'plove'@'127.0.0.1'` | 见第四节：授权来源是 `localhost`，补 `@'127.0.0.1'` |
| 反向代理 502 | 目标写成了 `https://`、或端口不对；面板 → 反向代理里检查目标 URL |
| 改了 `/etc/nginx/nginx.conf` 没反应 | 宝塔用自己管理的配置，见第四节第 4 步末尾 |
| 预热没跑 / 跑了两遍 | 一遍是对的；两遍说明起了**两个进程**（面板的项目 + 你手工的那个，或 workers > 1） |
| 504 而且是一张 HTML | nginx 超时，见第三节第 4 步那个 75s |
