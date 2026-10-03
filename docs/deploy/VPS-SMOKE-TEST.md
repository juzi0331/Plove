# 在 VPS 上"试跑"：20 分钟拿到结论

> 这份和 [CHECKLIST.md](CHECKLIST.md) 是**两件不同的事**，别混。
>
> | | 这份文档（试跑） | [CHECKLIST.md](CHECKLIST.md)（上线） |
> | --- | --- | --- |
> | 要回答的问题 | **这台机器能不能用？** | 别人能不能访问？ |
> | 需要域名 / 证书 | ❌ | ✅ |
> | 需要 MySQL | ❌（用 SQLite） | ✅ |
> | 需要 nginx / systemd | ❌ | ✅ |
> | 监听在哪 | `127.0.0.1:8000`（只有你，靠 SSH 隧道看） | `:443` |
> | 花多久 | **20 分钟** | 1~2 小时 |
> | 做完之后 | 要么删掉，要么接着走 CHECKLIST | —— |
>
> **先做这一步。** 它的产出是一张**实测数字表**，而那张表能决定后面要不要继续 ——
> 尤其是"源站认不认这台机器的 IP"这件事，**在你本机怎么测都测不出来**。

---

## 0. 它到底在测什么（三件事，按重要性排）

1. **源站认不认这台机器？**
   两个源都是国内影视站，对**机房 IP** 很敏感。你在家能抓、在 VPS 上吃 `BLOCKED`，很常见。
   **但如果你已经用别的脚本（哪怕不是这套代码）在这台机器上真的抓到过数据，
   这一条就算验过了** —— 直接跳过去看第 2 条。
2. **从这台机器到源站有多慢？**（**IP 验过之后，这条才是重点**）
   开发机量到 `ncat21` 首页 5.2~8.9s。如果 VPS 上是 25s，
   那 `PLOVE_CRAWLER_TIMEOUT=20.0` 就是错的 —— 上线后会变成一半请求 504。
   **超时参数只能在这个数字出来之后才能定。**
3. **这套代码在这台机器上跑得起来吗？** 依赖装得上吗、测试绿吗、起得来吗。
   最不容易出问题的一条，但也最容易被当成"全部"。

---

## 1. 本机：打包 + 送上去

### Windows 上最容易在这里翻车的三个地方

| 现象 | 原因 |
| --- | --- |
| `tar: backend: Cannot stat: No such file or directory` | 你在 **PowerShell / cmd** 里敲了 `cd /e/Pychon-code/...` —— 那是 Git Bash 的路径写法，Windows 要 `E:\Pychon-code\...`。cd 失败了但你没注意，后面的 `tar` 就在错的目录里跑 |
| `'--exclude=.venv' 不是内部或外部命令` | **cmd 里 `\` 不是续行符**。它把第一行当成一条完整命令跑掉，剩下三行各自当成新命令 —— 所以多行写法只能用在 Git Bash 里 |
| `tar: Cannot open: No such file or directory` | `/tmp/plove.tgz` 里的 `/tmp` 不是 Windows 的路径。**打包时输出到当前目录就好**，别用 `/tmp` |

### 照抄版 —— 选一个（都在 Windows 上实测过，产物约 200 KB、184 个文件）

**A. PowerShell**（推荐，不用装别的东西）：

```powershell
cd E:\Pychon-code\NY\Plove1.0
tar -czf plove.tgz --exclude=.venv --exclude=__pycache__ --exclude='*.db' --exclude=.env --exclude=.git backend crawler contracts deploy docs PROGRESS.md
Get-Item plove.tgz | Select-Object Length,Name
```

**B. Git Bash**（`\` 续行在这里才有效）：

```bash
cd /e/Pychon-code/NY/Plove1.0
tar -czf plove.tgz --exclude=.venv --exclude=__pycache__ --exclude='*.db' --exclude=.env --exclude=.git backend crawler contracts deploy docs PROGRESS.md
ls -lh plove.tgz
```

> **注意用 Windows 自带的 `tar` 也没问题**（`C:\Windows\System32\tar.exe`，bsdtar 3.8）——
> 实测它的排除规则是对的：`.venv` / `__pycache__` / `*.db` / **真的 `backend/.env`** / `.git`
> 全都没进包，只有 `.env.example`、`.env.prod.example` 这种模板保留下来（**那是应该留的**）。
> 所以这个报错跟 tar 无关，是路径和 shell 的事。

### 上传（先把 IP 换成真的）

```powershell
scp plove.tgz root@你的VPS_IP:/tmp/
```

> **`你的VPS_IP` 是占位符，五个字要真的换成 IP**（像 `203.0.113.7`）。
> 忘了换的话报的是 `ssh: Could not resolve hostname 你的VPS_IP` ——
> 那个错看起来像"网络问题"，实际是文案问题。
>
> Windows 10/11 自带 `scp`（OpenSSH 客户端），不用额外装。第一次连会问一次指纹，敲 `yes`。

**注意被排除的两样：**

* `.env` —— 你本机那份指向 NAS 上的 MySQL（`192.168.31.5:33306`），
  传上去只会让服务去连一个它根本连不到的内网地址。**而且里面有密码。**
* `*.db` —— 本机的 SQLite 开发库，没必要带过去。

VPS 上解开：

```bash
mkdir -p /opt/plove
tar -xzf /tmp/plove.tgz -C /opt/plove
ls /opt/plove        # 应看到 backend crawler contracts deploy docs
```

> `/opt/plove` 现在只是"一个试验目录"。**这一步不需要建专用用户、不需要 ufw、不需要改时区**——
> 那些是上线要做的事（CHECKLIST 第 1 步）。试完 `rm -rf /opt/plove` 就干净了。

---

## 2. 先看清这台机器（30 秒）

```bash
curl -s ipinfo.io; echo        # 出口 IP 和城市，记下来
python3 --version              # 需要 >= 3.11（爬虫只要 3.8+，后端要 3.11+）
nproc; free -m; df -h /opt | tail -1
```

**如果 `free -m` 显示总内存小于约 900MB**，先加一块 swap 再往下走
（`pip install` 是这一步最容易 OOM 的地方，而这台机器上还有别的服务在跑）：

```bash
fallocate -l 1G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -m                        # 确认 Swap 那行不是 0
```

---

## 3. ⛳ 跑爬虫（1 分钟，顺便把延迟量出来）

如果你在别的脚本上已经验过"这台机器能抓到"，那这一步就不再有悬念，
它只剩两个作用：**确认我们这套（Python + 闸门求解器）也通**，以及**拿到延迟数字**。

**先说一个好消息：爬虫是零依赖的。** `crawler/` 只用标准库
（[crawler/README.md](../crawler/README.md) 里那条硬约束：站点文件只允许 `import crawler_kit` + 标准库）。
所以**不用装任何东西、不用建 venv**，直接在 VPS 上跑：

```bash
cd /opt/plove

python3 crawler/sites/ncat21.py home | head -c 300; echo
time python3 crawler/sites/ncat21.py home > /dev/null

python3 crawler/sites/ai2048.py home | head -c 300; echo
time python3 crawler/sites/ai2048.py home > /dev/null
```

如果 `python3` 太小众或者不存在：`apt install -y python3` 就行，**仅此一个包**。

### 看这三件事，不是看"能不能跑"

| 看什么 | 正常 | 不正常 = 什么 |
| --- | --- | --- |
| **有没有数据** | `{"ok": true, "data": {...}}` | `{"ok": false, "error": {"code": "BLOCKED"}}` → 源站**封了机房 IP**。这类站对 IDC 网段很敏感，"家里能抓、服务器上被封"是常态 |
| **花了多久** | 和开发机的数字差不多 | 明显更慢 → 第 5 步里 `PLOVE_CRAWLER_TIMEOUT` 要跟着调大 |
| **闸门还灵不灵** | `ncat21` 能正常返回 | `BLOCKED` → 那道 `cdndefend` 是按 IP + cookie 走的，换 IP 等于全新挑战（代码能解，但要看它认不认） |

### 再确认一次"到底抓到了什么"

不要只看 `ok: true`。`home` 的数据里应该真的有一批片名：

```bash
python3 crawler/sites/ncat21.py home | python3 -X utf8 -c "
import json, sys
d = json.load(sys.stdin)
if not d['ok']:
    print('失败:', d['error']); raise SystemExit(1)
data = d['data']
print('分类:', [(c['tid'], c['name']) for c in data['categories']][:6])
print('推荐:', [v['vod_name'] for v in data['recommend']][:6])
"
```

正常应该看到类似：

```
分类: [('1', '电影'), ('2', '连续剧'), ('3', '动漫'), ('4', '综艺纪录')]
推荐: ['年会不能停2', '瘴气营地的青春性事与死亡', '剧场版紧急审讯室THEFINAL']
```

> **那个 `-X utf8` 不是装饰。** 爬虫的 stdout 是**写死的 UTF-8**（见 [crawler/README.md](../crawler/README.md)），
> 而你交互式解释器的 stdout 会跟着终端的编码走。两边不一致时中文就是乱码 ——
> 在 Windows 的 GBK 控制台上必现，在 Linux 上通常不出现，但加上它没有任何代价。
> **乱码会让人误判成"源站改版了"，那是最贵的误判。**

`ok: true` 但列表是空的，说明**源站改版了**（或者返回了一个软拦截页）——
这和"被封锁"是两回事，但同样会毁掉整个方案。

### 顺手把播放链路也验一遍（可选，1 分钟）

播放是最脆的一环（多一次跳转、地址带签名）：

```bash
ID=$(python3 crawler/sites/ncat21.py home | python3 -X utf8 -c "
import json,sys
d=json.load(sys.stdin)['data']['recommend']
print(d[0]['vod_id'])")
echo "拿到的 id: $ID"

time python3 crawler/sites/ncat21.py detail --id "$ID" > /dev/null
time python3 crawler/sites/ncat21.py play --id "$ID" --ep 1 > /dev/null
```

### 三条出路（现在就该做决定）

| 结果 | 怎么办 |
| --- | --- |
| ✅ 两个源都正常，延迟和开发机一个量级 | 继续第 4 步，试跑完整套 |
| ⚠️ 能跑但慢很多 | 继续，但第 5 步必须把超时调到**实测最坏值的 2 倍** |
| ❌ 被拦（`BLOCKED`）或全是空列表 | **停下来，先别装任何东西。** 可选：换一台机器 / 加代理出口 / 把该源标成 `mode: proxy` 走流代理（阶段 9）。这时候换方案，比部署完再发现便宜得多 |

**把量到的秒数写下来**，第 7 步要填进表里。

---

## 4. Python 环境 + 跑一遍测试

```bash
apt install -y python3-venv python3-dev build-essential

cd /opt/plove/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

`[dev]` 里是 pytest / httpx / jsonschema。**在服务器上也要装它**：
"本地绿、线上炸"这类事故，只有真在这台机器上跑一次才排得掉，代价是几十 MB 磁盘。

```bash
cd /opt/plove/backend
.venv/bin/python -m pytest              # 期望 164 passed, 2 skipped
```

> 跳过的 2 个是可选的真 MySQL 测试（要 `PLOVE_TEST_DATABASE_URL` + `-m mysql`），
> 这里没装 MySQL，所以跳过是**正确**的。

契约生成物和模型一致吗（改过 schemas 没重新导出的话，这里会红）：

```bash
.venv/bin/python tools/export_contracts.py --check
```

---

## 5. 起服务 —— **不装 MySQL**

这是"试跑"和"上线"最大的区别：**默认配置就是 SQLite**，
所以这一步**一个配置文件都不用写**。没配 `PLOVE_DATABASE_URL` 时，
`backend/plove-dev.db` 会被自动创建，表结构只用了可移植类型，行为一致。

```bash
cd /opt/plove/backend
.venv/bin/python tools/init_db.py
```

预期输出里有 `建表完成，共 2 张: activation_codes, devices`，且会明确提示"这是本地 SQLite"。

**给后台接口配一个临时令牌**（顺便验一下后台那条链路）：

```bash
cat > /tmp/plove-env.sh <<EOF
export PLOVE_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
EOF
source /tmp/plove-env.sh
echo "$PLOVE_ADMIN_TOKEN"        # 后面每次新开一个 SSH 窗口，先 source /tmp/plove-env.sh
```

> 为什么不写进 `.env`：这只是**临时**的，写文件反而要记得清理。
> 但服务和你手动跑的 `check.sh` 必须在**同一个令牌**下 —— 所以存进一个小文件、
> 谁用谁 `source`，比"记下来再手敲"可靠。
>
> 反过来注意一件事：**环境变量优先级高于 `.env`**。这就是为什么
> [BT-PANEL.md](BT-PANEL.md) 里反复说"面板的环境变量那一栏留空，只用 `.env`" ——
> 两处都配就会出现"我明明改了 `.env` 怎么不生效"。

前台跑起来（**故意先前台**，报错直接打屏，不用学 `journalctl`）：

```bash
cd /opt/plove/backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**另开一个** SSH 窗口（第一个窗口在**前台**跑着服务，别关它）：

```bash
source /tmp/plove-env.sh
curl -s http://127.0.0.1:8000/api/v1/health; echo
```

看到 `{"ok":true,"data":{"status":"ok",...}}` 就成了。启动日志里应该能看到
`后台任务 缓存预热 已启动` —— 但按默认（`PLOVE_WARMUP_ENABLED=false`）**不会**有这行，
**那是正常的**。

> **8000 端口不要对外放行。** 它只给同机的 nginx 用；
> 你自己要看它，用第 6 步的 SSH 隧道，而不是开防火墙。

---

## 6. 用 SSH 隧道把 Swagger 拉到你自己浏览器（不用域名、不用证书）

**关键技巧：** `-L` 把远端端口映射到本机，你就能在**开发机的浏览器里**点 Swagger，
不需要域名、不需要 HTTPS、不需要动防火墙。

在**你的机器**上开一个新窗口：

```bash
ssh -N -L 18000:127.0.0.1:8000 root@你的VPS_IP
```

（用 18000 而不是 8000，避免和你本机可能在跑的那个撞上。保持这个窗口开着。）

本机浏览器打开 **http://127.0.0.1:18000/docs** —— 这就是 VPS 上的 Swagger。

走一遍完整业务链路（这就是"测试"最实际的形态）：

1. 在 **VPS 的 SSH 窗口**里发一个码：
   ```bash
   cd /opt/plove/backend
   .venv/bin/python tools/issue_code.py --days 30 --note "VPS 试跑"
   ```
2. 浏览器里 `POST /api/v1/activation/redeem`，body 填刚拿到的码：
   ```json
   {"code": "PLV-XXXX-XXXX-XXXX", "device_name": "VPS 试跑"}
   ```
   从响应里拿到 `device_token`。
3. 点右上角 **Authorize**，`X-Device-Token` 填进去（**不是** `X-Admin-Token`，这是两套凭证）。
4. 依次调 `GET /sites`、`GET /sites/ncat21/home`、`GET /sites/ncat21/detail`。
   **第一次会明显卡**（要等源站，`ncat21` 首页开发机上就是 8.9s）；
   **再点一次同一地址应该是瞬间** —— 这是缓存生效的证据。
5. 后台那两个接口要填 `X-Admin-Token`（就是第 5 步 `echo` 出来的那串）。

也可以全用命令行（不用浏览器）：

```bash
source /tmp/plove-env.sh         # 拿到 PLOVE_ADMIN_TOKEN

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/activation/redeem \
  -H 'Content-Type: application/json' \
  -d '{"code":"PLV-XXXX-XXXX-XXXX","device_name":"VPS 试跑"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['device_token'])")   # 这一行只有 ASCII，不用 -X utf8

curl -s -H "X-Device-Token: $TOKEN" http://127.0.0.1:8000/api/v1/sites; echo
time curl -s -H "X-Device-Token: $TOKEN" http://127.0.0.1:8000/api/v1/sites/ncat21/home > /dev/null
time curl -s -H "X-Device-Token: $TOKEN" http://127.0.0.1:8000/api/v1/sites/ncat21/home > /dev/null   # 第二次：应接近 0
```

> `device_name` 写中文没问题 —— 它在**请求体**里。
> 但**请求头必须纯 ASCII**：HTTP 头在协议层就是 Latin-1，中文写进去要么被静默改写、
> 要么直接 400。而这个坑开发时踩过两次（最典型的是把中文设备名当 URL 参数拼）——
> **要传的东西一律放 body**。

自动自检也跑一遍（它会把"源站认不认这台机器"再验一次，但这次是**通过应用**看的）：

```bash
source /tmp/plove-env.sh
cd /opt/plove
BASE_URL=http://127.0.0.1:8000 ADMIN_TOKEN="$PLOVE_ADMIN_TOKEN" bash deploy/check.sh
```

期望 **通过 8 项，失败 0 项**，退出码 0。里面第 5 节会直接跑爬虫本体，
耗时和你在第 3 步量到的应该对得上。

再把预热手动触发一次，确认**定时任务那条路也能在服务器上跑通**：

```bash
curl -s -X POST -H "X-Admin-Token: $PLOVE_ADMIN_TOKEN" \
  "http://127.0.0.1:8000/api/v1/admin/cache/refresh?wait=true" | head -c 400; echo
```

> 开发机上这一轮（2 个源 × 4 个页面）是 31.4 秒。在这台 VPS 上应该**明显更快**
> （它的单页耗时是开发机的 1/4~1/6）。早上好几分钟 = 这台机器到源站的路确实差，
> 那时才需要重新考虑超时和 TTL 的取值。

> **输出里那个 `BrokenPipeError` 是无害的。** 它是 `| head -c 300` 把管道早关了，
> 爬虫在退出时冲 stdout 触发的。它不会影响返回值（`ok: true` 已经在前面打出来了），
> 也不是爬虫的 bug —— 真正的问题只会体现为 `ok: false` 或退出码非 0。

---

## 7. 把数字填进这张表

**这才是这一步真正的产出。** 试跑结束时它应该是填满的：

| 项目 | 开发机实测 | 这台 VPS 实测 | 结论 |
| --- | --- | --- | --- |
| 出口 IP / 城市 | （家宽） | | 和源站是不是同一个大区 |
| `ai2048` home | ~2.0s | **0.59s** | 快 3 倍多 |
| `ncat21` home | 5.2~**8.9s** | **1.50s** | 快 4~6 倍 |
| `ncat21` detail | 2.9~**5.9s** | | |
| `ncat21` play（不带 play_id） | 4.1~**7.2s** | | |
| 首页第二次（缓存命中） | 0.000s | | 不是 0 = 缓存没生效 |
| 主动预热一轮 | 31.4s（2/2 成功） | | |
| `pytest` | 164 passed / 2 skipped | **通过** | 条数不一致 = 传上去的代码不对 |
| `check.sh` | 8/8 | | |
| 源站判定 | —— | **认**（闸门直接放行） | 不认就别继续了 |

### 已经量到的（2026-09-30，第一台 VPS）

```
[INFO] 闸门已通过: cdndefend_js_cookie=BB2A7A88D508…   # 一次就过，没有重试
ncat21 home    real 0m1.502s
ai2048 home    real 0m0.588s
分类: 电影 / 连续剧 / 动漫 / 综艺纪录 / 短剧     推荐: 年会不能停2 …   ← 数据是真的
pytest         通过
```

**结论：慢的是开发机那条家宽出口，不是源站。**
这条比单个数字重要 —— 它意味着：

* 开发机上那组 5~9s 应当被当成**最坏情况的上界**留着。超时按它配（现在的 20s / 25s）
  **只会偏安全，不会偏危险**，所以**这一项暂时不用调**；
* 反过来，如果哪次开发机上测得飞快，**不能**拿它去调小超时 ——
  那台机器量的不是用户的处境；
* 真正要警惕的是 VPS 换机房 / 换线路：那时这组数字才算作废，重新量一遍。

**以后真要调小，规则是这个**（别按“平均值 × 1.5”）：

```
PLOVE_CRAWLER_TIMEOUT=<实测最坏值的 2 倍>
PLOVE_CRAWLER_TIMEOUT_PLAY=<同上>
```

理由：TTL 之外的每一次慢请求，代价都是一个用户对着转圈。

---

## 8. 试完了：两条路

### 路 A：继续上线

这台机器通过了 → 接着走 **[CHECKLIST.md](CHECKLIST.md)**。
第 1、3、4 步（用户 / 环境 / MySQL）会重复一部分，那是正常的：
**试跑刻意没做"上线要有的规范"，就是为了它能快速失败。**

（如果你用的是**宝塔面板**，中间那几步换成 [BT-PANEL.md](BT-PANEL.md)。）

### 路 B：放弃这台机器

```bash
pkill -f "uvicorn app.main:app"      # 停服务
cd /tmp && rm -f plove.tgz
rm -rf /opt/plove                    # 试验目录整个删掉
swapoff /swapfile && rm -f /swapfile # 如果第 2 步加过 swap
sed -i '/\/swapfile/d' /etc/fstab
```

**没有任何东西被改动过。** 这就是为什么试跑不建用户、不动防火墙、不建 MySQL ——
试错的成本应该是"删一个目录"。

---

## 9. 这一步**故意没做**的（都不是遗漏）

| 没做 | 为什么 |
| --- | --- |
| 建专用用户 `plove` | 试跑不需要；上线才要（不拿 root 跑服务） |
| MySQL | SQLite 足以验全部业务逻辑，装 MySQL 要多花 15 分钟且没有任何新信息 |
| nginx / HTTPS / 域名 | 你测的是**后端**；SSH 隧道已经能让你点到 Swagger |
| systemd / 面板托管 | 前台跑能看到完整 traceback，托管会把错误吞掉 |
| ufw / 时区 / 日志轮转 | 上线的事 |
| 备份 | 还没有值得备份的数据 |

---

## 10. ⚠️ 一个踩过的坑，别重复踩

**`tar` 打包时一定排除 `.env`。**

本机的 `backend/.env` 指向 NAS 上的 MySQL（`192.168.31.5:33306`）。
它被带上服务器的话，服务会去连一个**只有你家里内网能到达**的地址，
报出来的是 `Can't connect to MySQL server on '192.168.31.5'`，
而你会以为"是 VPS 的数据库配错了" —— 实际上**那份文件本来就不该在服务器上**。

同理，别把本机那个 SQLite 开发库（`plove-dev.db`）带上去：
里面有测试码和测试设备，混进服务器的库里只会让人分不清哪条是真的。
