# 上线清单：从一台空 VPS 到能访问

> 每一步都写了**怎么验证**。**没验证过就等于没做** —— 尤其第 2 步和第 10 步。
> 假设：Ubuntu 22.04/24.04、你把代码放在 `/opt/plove`、域名指向这台机器。
> 命令里出现 `plove.example.com` 的地方换成你自己的域名。

---

## 先想清楚：你是要"试跑"还是"上线"

| 你想要的 | 看哪份 | 多久 |
| --- | --- | --- |
| **"这台机器到底能不能用？"**（不碰 MySQL / nginx / 域名，试完可删） | **[VPS-SMOKE-TEST.md](VPS-SMOKE-TEST.md)** | 20 分钟 |
| **"别人能访问了"**（上线、备案、证书、备份） | **就是你现在看的这份** | 1~2 小时 |

**建议先试跑。** 第 2 步（源站认不认这台机器）是整份清单里**唯一**一件
"本地怎么测都测不出来、而且失败就得改方案"的事 ——
把它的成本做到最小（20 分钟、零安装、零残留），比一次性走完整套再发现要划算。

---

## 0. 开工前先确认三件事

| 事项 | 为什么现在就要确认 |
| --- | --- |
| **域名已解析到这台机器** | 没有域名就只能用 IP，而 **ipa 里的 WKWebView 拦明文 http**，且 IP 一变壳就废、只能重新打包 —— 那"只打包一次"的前提就没了 |
| **VPS 规格**：≥ 1 核 1G、10Mbps | 后端本身很轻，瓶颈是带宽和源站延迟，不是 CPU |
| **你有 root（或 sudo）** | 下面全程需要 |

顺手记下这台机器的**真实出口位置**（`curl -s ipinfo.io`）—— 第 2 步的结果要和它对照看。

---

## 1. 系统准备

```bash
apt update && apt upgrade -y
timedatectl set-timezone Asia/Shanghai        # 日志时间对得上人话；库里存的一律是 UTC
```

建一个专用用户（**不要用 root 跑服务**）：

```bash
useradd --system --create-home --shell /usr/sbin/nologin plove
mkdir -p /opt/plove
chown -R plove:plove /opt/plove
```

防火墙：**只开 22 / 80 / 443**。

```bash
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

> ⚠️ **不要开 3306 和 8000。** 数据库和 API 都只监听回环，外面必须经过 nginx。
> 把 3306 开到公网 = 把数据库摆到大街上，几小时内就会有爆破。

**验证：** `ss -tlnp | grep -E '3306|8000'` 现在**应该什么都没有**（还没装），
装完之后也只应该看到 `127.0.0.1`。

---

## 2. ⛳ 先在这里跑一次爬虫（**最重要的一步**）

**在装任何东西之前做。** 这一步 5 分钟，但它能决定整个方案要不要调整：

```bash
apt install -y python3 python3-pip git
cd /opt/plove
git clone <你的仓库地址> .                # 或者用你惯用的同步方式

sudo -u plove python3 crawler/sites/ncat21.py home | head -c 300; echo
sudo -u plove python3 crawler/sites/ai2048.py home | head -c 300; echo
```

> **爬虫是零依赖的**（只用标准库 + `crawler_kit`），所以这里**不需要 venv、不需要 pip install**。
> 想让这一步更省事（连代码怎么传上去都不操心），用
> [VPS-SMOKE-TEST.md](VPS-SMOKE-TEST.md) —— 它是这一步的展开版。

**要看的不是"能不能跑"，而是这三件事：**

| 看什么 | 正常 | 不正常意味着 |
| --- | --- | --- |
| **有没有数据** | `{"ok": true, "data": {...}}` | 源站**封了机房 IP**。这类站对 IDC 网段很敏感，在家能抓、在服务器上被封很常见 |
| **花了多久** | `time` 一下，和开发机对比 | 明显更慢 → `PLOVE_CRAWLER_TIMEOUT` 要跟着调大（开发机量的是 20s/25s） |
| **闸门还灵不灵** | `ncat21` 能正常返回 | `BLOCKED` → 那道 `cdndefend` 是按 IP+cookie 的，换 IP 就是全新挑战 |

```bash
time sudo -u plove python3 crawler/sites/ncat21.py home > /dev/null
```

**结果处理：**

* ✅ 都正常 → 记下耗时，继续往下。
* ⚠️ 慢但能跑 → 把 `PLOVE_CRAWLER_TIMEOUT` 调到 **实测最坏值的 2 倍**。
* ❌ 被拦 → **先别继续部署**。可选的路：换一台机器、加代理出口、
  或者把该源标成 `mode: proxy` 走流代理（阶段 9）。这时调整方案比部署完再发现有价值得多。

---

## 3. Python 环境

```bash
apt install -y python3-venv python3-dev build-essential
python3 --version        # 需要 >= 3.11
```

| 系统 | 自带 Python | 怎么办 |
| --- | --- | --- |
| Ubuntu 24.04 | 3.12 | ✅ 直接用 |
| Debian 12 | 3.11 | ✅ 直接用 |
| Ubuntu 22.04 | 3.10 | ❌ 装 3.11：`add-apt-repository ppa:deadsnakes/ppa && apt install python3.11 python3.11-venv` |

```bash
cd /opt/plove/backend
sudo -u plove python3 -m venv .venv
sudo -u plove .venv/bin/pip install --upgrade pip
sudo -u plove .venv/bin/pip install -e ".[dev]"
```

> **为什么要装 `[dev]`（pytest 等）？** 为了能**在服务器上跑一遍测试**。
> "本地绿、线上炸"这类事故，只有真在这台机器上跑一次才排得掉。
> 代价是几十 MB 磁盘，值得。

**验证：**

```bash
sudo -u plove .venv/bin/python -c "import app; print(app.__version__)"
sudo -u plove .venv/bin/python -m pytest              # 期望 164 passed, 2 skipped
```

---

## 4. MySQL

```bash
apt install -y mysql-server
mysql_secure_installation          # 走一遍，root 密码设上、匿名用户删掉
```

建库建用户（**只允许从回环连**）：

```bash
mysql -u root -p
```

```sql
CREATE DATABASE plove CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'plove'@'127.0.0.1' IDENTIFIED BY '在这里放一个强密码';
GRANT ALL PRIVILEGES ON plove.* TO 'plove'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

**验证三项**（这三项就是最容易翻车的地方，开发时已经踩过一遍）：

```sql
SHOW VARIABLES LIKE 'version';              -- 5.7 或 8.x 都行
SHOW VARIABLES LIKE 'character_set_database';  -- 要 utf8mb4
SELECT @@sql_mode;                          -- 要含 STRICT_TRANS_TABLES
```

建表：

```bash
cd /opt/plove/backend
sudo -u plove .venv/bin/python tools/init_db.py
```

预期输出里有 `建表完成，共 2 张: activation_codes, devices`。

> **绑地址检查：** `ss -tlnp | grep 3306` 应该看到 `127.0.0.1:3306`。
> 如果是 `0.0.0.0:3306`，去 `/etc/mysql/mysql.conf.d/mysqld.cnf` 把
> `bind-address` 改回 `127.0.0.1` 再重启。

---

## 5. 写配置

```bash
cp /opt/plove/deploy/.env.prod.example /opt/plove/backend/.env
chmod 600 /opt/plove/backend/.env
chown plove:plove /opt/plove/backend/.env
```

然后**逐行改**，至少这三处：

1. `PLOVE_DATABASE_URL` 里的密码 —— 和上面 SQL 里那个一致；
2. `PLOVE_ADMIN_TOKEN` —— 用 `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` 生成。
   **必须填**：留空等于后台接口全部拒绝（故意的，防止裸奔）；
3. 第 2 步里如果发现源站慢，`PLOVE_CRAWLER_TIMEOUT` / `_PLAY` 一起调大。

**验证配置读进来了：**

```bash
sudo -u plove .venv/bin/python -c "
from app.core.config import get_settings
s = get_settings()
print('env      =', s.env)
print('数据库   =', s.database_url.split('@')[-1])
print('爬虫目录 =', s.crawler_dir)
print('预热     =', s.warmup_enabled, s.warmup_interval_seconds)
print('后台令牌 =', '已配置' if s.admin_token else '**空的，后台不可用**')
"
```

---

## 6. 先手动跑一次（**不要直接上 systemd**）

```bash
cd /opt/plove/backend
sudo -u plove .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个窗口：

```bash
curl -s http://127.0.0.1:8000/api/v1/health; echo
```

看到 `{"ok":true,"data":{"status":"ok",...}}` 就成了。

**为什么不直接上 systemd：** 现在出错，报错信息就打在屏幕上；
上了 systemd 之后错会被吞进 journald，你还得学一遍 `journalctl` 才看得见。
**先把东西跑起来，再交给守护进程。**

看一眼启动日志，应该能见到：

```
后台任务 缓存预热 已启动：60 秒后首次执行，之后每 86400 秒一次
```

（没开预热就不会有这行 —— 那是正常的。）

`Ctrl+C` 停掉。

---

## 7. 交给 systemd

```bash
cp /opt/plove/deploy/systemd/plove-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now plove-backend
systemctl status plove-backend --no-pager
```

**验证：**

```bash
curl -s http://127.0.0.1:8000/api/v1/health; echo    # 没起反代也能先验这一层

# 崩了要能自己起来：杀掉它，看它是否自动回来
systemctl kill -s KILL plove-backend; sleep 4
systemctl is-active plove-backend                   # 期望 active
```

看日志：

```bash
journalctl -u plove-backend -f
journalctl -u plove-backend --since "10 min ago" | grep -i error
```

> ⚠️ **忘了 `--workers` 吗？** 别加。缓存、防击穿、熔断、预热都是**进程内状态**，
> 多 worker 会让它们各自为政（缓存命中率除以 N、预热跑 N 遍）。理由见 [README.md](README.md)。

---

## 8. nginx + HTTPS

```bash
apt install -y nginx
cp /opt/plove/deploy/nginx/plove.conf /etc/nginx/sites-available/plove
ln -s /etc/nginx/sites-available/plove /etc/nginx/sites-enabled/plove
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

先把域名改对（文件里那两处 `plove.example.com`），再签证书：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d plove.example.com
certbot renew --dry-run          # 确认自动续期是通的
```

**验证：**

```bash
curl -sI https://plove.example.com/api/v1/health | head -3      # 200，且是 https
curl -sI http://plove.example.com/api/v1/health | head -3       # 301 跳 https
```

> 顺手一个安全项：证书配好之后，把 nginx 里 `/docs` 那两行注释掉，
> 并在 `.env` 里设 `PLOVE_DOCS_ENABLED=false`（重启生效）。
> Swagger 是你的开发工具，不必摆在公网上。

---

## 9. 全套验证

```bash
cd /opt/plove
BASE_URL=https://plove.example.com ADMIN_TOKEN=你配的令牌 bash deploy/check.sh
```

它会把最关键的四件事一次验完：**应用活着 + 错误也是 JSON + 门是关着的 + 源站认这台机器**。

然后走一遍真实的业务链路：

```bash
cd /opt/plove/backend
sudo -u plove .venv/bin/python tools/issue_code.py --days 30 --note "上线第一个码"
```

拿着这个码去 `/docs`（若已关就用 curl）：

```bash
TOKEN=$(curl -s -X POST https://plove.example.com/api/v1/activation/redeem \
  -H 'Content-Type: application/json' \
  -d '{"code":"PLV-XXXX-XXXX-XXXX","device_name":"上线验证"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['device_token'])")

curl -s -H "X-Device-Token: $TOKEN" https://plove.example.com/api/v1/sites; echo
curl -s -H "X-Device-Token: $TOKEN" https://plove.example.com/api/v1/sites/ncat21/home | head -c 200; echo
```

最后**手动跑一次预热**，把缓存填上（顺便确认预热在服务器上也能跑）：

```bash
curl -s -X POST -H "X-Admin-Token: $ADMIN_TOKEN" \
  "https://plove.example.com/api/v1/admin/cache/refresh?wait=true" | head -c 400; echo
```

> 第一次预热会慢（要等源站，开发机上 2 个源约 31 秒）。

---

## 10. 备份（**必须做，而且必须演练一次**）

```bash
chmod +x /opt/plove/deploy/backup.sh      # 脚本在仓库里
sudo -u plove bash /opt/plove/deploy/backup.sh              # 先手动跑一次，确认能出文件
```

挂定时任务（`crontab -u plove -e`）：

```cron
# 每天凌晨 4:10 备份，保留最近 14 份
10 4 * * * /bin/bash /opt/plove/deploy/backup.sh >> /var/log/plove-backup.log 2>&1
```

**然后演练一次恢复**（不做这一步的备份等于没有备份）：

```bash
ls -lh /var/backups/plove/                                  # 看有没有文件、多大
gunzip -c /var/backups/plove/plove-YYYYmmdd-HHMMSS.sql.gz | head -30   # 肉眼确认是 SQL，不是错误信息
```

真要恢复时：

```bash
gunzip -c /var/backups/plove/xxx.sql.gz | mysql -u plove -p plove
```

**顺便记一条：本地开发库的数据不要搬过来。** 线上是新的库、新发的码；
旧库里躺着测试码和测试设备，搬过来只会把脏数据带到线上。

---

## 11. 日常操作速查

```bash
# 更新代码
cd /opt/plove && sudo -u plove git pull
# 契约过期会让测试变红，顺手确认一下生成物和模型一致
sudo -u plove backend/.venv/bin/python backend/tools/export_contracts.py --check
sudo systemctl restart plove-backend
curl -fsS https://你的域名/api/v1/health

# 看日志
journalctl -u plove-backend -f
journalctl -u plove-backend -n 200 --no-pager | grep -i -e error -e 熔断 -e 预热

# 发码 / 停服务 / 查状态
sudo -u plove backend/.venv/bin/python backend/tools/issue_code.py --days 30 --note "谁"
systemctl stop plove-backend
curl -s -H "X-Admin-Token: $TOKEN" https://你的域名/api/v1/admin/status | python3 -m json.tool
```

> ⚠️ **重启会清空内存缓存。** 下次访问那几个源会回到"第一次"的耗时
> （`ncat21` 首页约 9 秒）。要么避开使用高峰，要么重启后立刻跑一次
> `POST /admin/cache/refresh?wait=true`。

---

## 12. 出问题对照表

| 现象 | 先看哪里 |
| --- | --- |
| 502 Bad Gateway | 后端没起来：`systemctl status plove-backend`、`journalctl -u plove-backend -n 50` |
| 504（而且是一张 HTML 页） | **nginx 等超时了**，不是应用。看 75s 那个 `proxy_read_timeout`，以及应用里 `PLOVE_CRAWLER_TIMEOUT` |
| 每个内容接口都 401 | 没带 `X-Device-Token`（激活过吗？）；注意它和后台的 `X-Admin-Token` 是**两套** |
| 后台接口 403「未启用」 | `PLOVE_ADMIN_TOKEN` 是空的，填上再重启 |
| 某个源全部 503 `UPSTREAM_CIRCUIT_OPEN` | 熔断开着，通常是源站变了或封了这台机器：直接用爬虫本体手跑一次（第 2 步的命令） |
| 源站请求全都 `BLOCKED` | 机房 IP 被针对了。见第 2 步的三种处理 |
| 首页第一次就 9 秒 | 正常（缓存是空的）。等预热跑过、或手动 refresh 一次 |
| 数据库连不上 | `ss -tlnp \| grep 3306`、`PLOVE_DATABASE_URL` 里的密码、`Access denied` 时看授权来源是不是 `127.0.0.1` |

---

## 13. 这一步**没有**做的

| 没做 | 说明 |
| --- | --- |
| 前端静态文件 | 阶段 7。nginx 配置里已经留好注释块 |
| 流代理 | 阶段 9，只有某个源真的需要时才做 |
| 远程配置（源开关 / 公告 / kill switch） | 下一步。有了它才能"不改代码就关掉一个源" |
| 监控告警 | 现在只有 `journalctl` 和 `/admin/status`。出事了靠人发现 |
| CDN / WAF | 用户不到 30 人，不需要 |
| 数据库异地备份 | 现在只备在本机。**机器整台坏掉就一起没了** —— 迟早要传一份到别处 |
