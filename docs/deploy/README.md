# deploy/ —— 部署到 VPS

目标形态：**一台机器、一个进程、一个数据库**。

```
        公网
         │  :443 (HTTPS)
    ┌────▼─────┐
    │  nginx   │  终止 TLS · 转发 /api/* · （日后）直接托管前端静态文件
    └────┬─────┘
         │  127.0.0.1:8000
    ┌────▼──────────┐
    │ uvicorn        │  一个进程（**必须是 1 个 worker**，见下）
    │ FastAPI        │  └─ 需要时 fork 爬虫子进程
    └────┬───────────┘
         │  127.0.0.1:3306
    ┌────▼─────┐
    │  MySQL   │  **只监听回环**，对外不可见
    └──────────┘
```

## 这个目录里有什么

| 文件 | 干什么 |
| --- | --- |
| [VPS-SMOKE-TEST.md](VPS-SMOKE-TEST.md) | **上线之前先跑这个**：20 分钟、**不碰 MySQL / nginx / 域名 / 证书**，只回答一个问题 —— 这台机器能不能用 |
| [CHECKLIST.md](CHECKLIST.md) | **主要产物**：从一台空 VPS 到能访问，按顺序的每一步 + 每步怎么验证 + 失败怎么办 |
| [BT-PANEL.md](BT-PANEL.md) | **如果你用宝塔面板**：哪些步骤交给界面、哪些文件别用、以及几个宝塔特有的坑 |
| [systemd/plove-backend.service](systemd/plove-backend.service) | 让后端开机自启、崩了自动重拉 |
| [nginx/plove.conf](nginx/plove.conf) | 反向代理 + HTTPS |
| [.env.prod.example](.env.prod.example) | 生产配置模板（**真实密码只写在 `.env`，不进仓库**） |
| [check.sh](check.sh) | 部署后跑一遍自检：接口活着吗、鉴权对吗、源站认不认这台机器 |

## 一条硬规矩：worker 必须是 1

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000          # 就这样，别加 --workers
```

理由很实际：**缓存、防击穿、熔断计数、预热执行器全都是进程内状态**。

* 开 4 个 worker → 缓存命中率掉到 1/4、四个进程各自熔断、**预热会跑四遍**（等于把源站请求量乘四）；
* 用户量（< 30 人）根本不缺并发，缺的是"别把源站打爆"。

真要横向扩展，第一步是把缓存换成 Redis、把"预热"交给单独的任务，而不是先加 worker。

## 只部署**一次**环境，之后都是"换代码重启"

第一次上线的成本最高（所有环境问题都在那一次爆发）。所以建议分两次走：

```
第一次（现在就做）：先只让 /api/v1/health 跑通
                    → 打通 nginx + systemd + HTTPS + 域名 + 数据库
                    → 之后每次部署都只是"拉代码 + 重启"

之后：功能一个个上，每次都是重复动作
```

好处是出问题时你面对的是**环境问题**，而不是"环境问题 + 新功能到底对不对"混在一起。

> **如果你的服务器上装了宝塔面板**，先看 [BT-PANEL.md](BT-PANEL.md)：
> 它把下面的 systemd/nginx 换成面板里的操作，并标出哪几个文件**不该用**
> （宝塔自己管进程和 nginx，两套一起上只会互相打架）。

另外：**第一次上线之前，先单独做一次"试跑"** —— 见 [VPS-SMOKE-TEST.md](VPS-SMOKE-TEST.md)。
20 分钟、不装 MySQL、不配 nginx、不要域名，全程只在 `127.0.0.1` 上，
试完可以整目录删掉。它要回答的是唯一一件"本地怎么测都测不出来"的事：
**源站认不认这台机器的 IP**（这类站对机房网段很敏感），以及从这台机器过去到底有多慢。

那件事一旦是坏消息，整个方案的取值得重来（换机器 / 加代理出口 / 该源走流代理），
**在装任何东西之前知道，比部署完再发现便宜得多。**

（如果服务器上装了宝塔，试跑照做 —— 它本来就只在终端里，不依赖面板。）

## 部署什么（不要只传 backend）

```
/opt/plove/
├── backend/      ✅ 要
├── crawler/      ✅ 要（后端按相对路径找它）
├── contracts/    ✅ 要（导出脚本与测试用；服务本身只读 schemas）
├── frontend/     日后（nginx 直接托管 dist）
└── docs/         可不要
```

`backend/app/core/config.py` 里 `PLOVE_CRAWLER_DIR` 的默认值是
"`backend/` 的上一层的 `crawler/`"，所以**保持这个相对位置**最省事。

## 更新一次代码是什么样

```bash
cd /opt/plove
sudo -u plove git pull                     # 或用你自己的同步方式
sudo -u plove backend/.venv/bin/python backend/tools/export_contracts.py --check
sudo systemctl restart plove-backend
curl -fsS https://你的域名/api/v1/health    # 看到 ok:true 就完事
```

`--check` 那一步是故意的：**契约过期会让测试红**，部署前顺手确认一下生成物和模型一致，
比上线后前端拿到对不上的字段要好。

> 注意：**重启会清空内存缓存**。下一次访问那几个源会回到"第一次"的耗时
> （`ncat21` 首页约 9 秒）。所以要么避开高峰期重启，要么重启后顺手
> `POST /admin/cache/refresh?wait=true` 把缓存填回来。
