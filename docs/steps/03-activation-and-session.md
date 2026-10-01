# 步骤 3 · 数据层 + 激活码 + 单会话

> 完成：2026-09-30 ｜ 代码：[backend/app/models/](../../backend/app/models/) ·
> [backend/app/services/activation_service.py](../../backend/app/services/activation_service.py) ·
> [backend/app/api/v1/activation.py](../../backend/app/api/v1/activation.py)
> 验证：`99 passed / 2 skipped`（本地 SQLite）· `101 passed`（连真 MySQL）·
> 契约 16 个一致 · 真实端到端全通

---

## 一、这一步干了什么

给后端装上了**数据**和**门**：

| 交付物 | 位置 | 作用 |
| --- | --- | --- |
| 数据库层 | [app/db/](../../backend/app/db/) | 引擎 / 会话 / 建表；（MySQL 与 SQLite 都能跑） |
| 两张表 | [app/models/](../../backend/app/models/) | `activation_codes`、`devices` |
| 激活与会话 | [activation_service.py](../../backend/app/services/activation_service.py) | 激活、心跳、抢活跃位 |
| 会话守卫 | [api/deps.py](../../backend/app/api/deps.py) | 所有内容接口都必须"当前活跃设备"才放行 |
| 命令行工具 | [tools/](../../backend/tools/) | `init_db.py` 建表 · `issue_code.py` 发码 |

---

## 二、新增接口

| 方法 | 路径 | 要守卫吗 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/activation/redeem` | ❌ | 激活，或"在此设备继续"（抢回活跃位） |
| POST | `/api/v1/activation/heartbeat` | ❌ | 心跳，顺带汇报 `is_active` |
| GET | `/api/v1/sites…` 全部 | ✅ | 现在都要带 `X-Device-Token` |
| GET | `/api/v1/sites/{key}/…` 全部 | ✅ | 同上 |

**激活接口刻意不设守卫** —— 一个还没激活的客户端当然调不了需要守卫的接口，
否则它永远激活不了。

守卫是**挂在 router 上**的（`dependencies=[Depends(require_device)]`），
不是塞进每个路由。理由是：加新接口时忘记加鉴权，是这类系统最常见的事故。

---

## 三、单会话怎么工作

```
设备A 激活 ──► 活跃位 = A ──► A 随便看
设备B 激活 ──► 活跃位 = B ──► A 下次心跳收到 is_active:false
                                └─► 前端停播 + 提示"已在其他设备登录"
                                    （**不自动抢回**，等用户手动点"在此设备继续"）
```

### 一个关键设计：**没有"离线超时释放"**

我一开始也以为需要"心跳超时就把活跃位释放掉"。想清楚后发现**不需要**：

活跃位**只在有人主动抢的时候才变**。所以：

* 切后台、锁屏、网络抖动、甚至关掉浏览器 —— 都**不会**让你掉线（活跃位根本没被释放）；
* 没有阈值要调，也就不存在"阈值设大了误踢 / 设小了漏踢"这种两头不讨好的问题；
* 心跳间隔只决定**"多久发现自己被踢"**，不影响正确性，30 秒足够。

### 四种拒绝必须分开报

前端要靠错误码决定该显示什么，所以不能笼统地报 401：

| 情况 | 错误码 | HTTP | 前端该做什么 |
| --- | --- | --- | --- |
| 没带令牌 / 令牌不认识 | `UNAUTHORIZED` | 401 | 引导输入激活码 |
| 激活码被停用 | `FORBIDDEN` | 403 | 提示联系管理员 |
| 激活码到期 | `ACTIVATION_EXPIRED` | 403 | 提示续期 |
| 活跃位在别的设备上 | `SESSION_KICKED` | 409 | 提示"已在其他设备登录"，给一个"在此设备继续"按钮 |

---

## 四、四条业务规则怎么落到代码

| 规则 | 落点 |
| --- | --- |
| **时长从首次激活起算** | `activated_at` 只在第一次写，之后永不改；`expires_at = activated_at + duration_hours` 算一次就存下来 |
| **一码多设备** | `devices` 表对激活码是**多对一**，不限制设备数量 |
| **但同时只能一台在线** | `activation_codes.active_device_id` 单列赋值 —— 切换活跃位**没有中间态**，不存在"两台都算活跃"的瞬间 |
| **被踢后不自动重抢** | 服务端只如实汇报 `is_active`；"抢回"是一个显式动作（再调一次 `redeem`），由用户点按钮触发 |

---

## 五、数据库设计

两张表：

```
activation_codes                    devices
├── id                              ├── id
├── code            唯一索引         ├── activation_id  外键 → activation_codes.id
├── duration_hours                  ├── token          唯一索引（后端签发）
├── note                            ├── name           客户端自报，仅供展示
├── created_at                      ├── created_at
├── activated_at    首次激活时间     └── last_seen_at   最后心跳
├── expires_at
├── disabled_at
└── active_device_id  ← 当前活跃设备
```

### 两个刻意的决定

**1. `active_device_id` 不建外键。**

`devices` 反过来要引用 `activation_codes`，两个方向互相外键会形成环，
SQLite 建表时会很难受。改成普通整数列，写入方只有 `activation_service` 一处。

**2. 表结构只用可移植类型。**

`String` / `Integer` / `Boolean` / `DateTime` / `Text`，**不用任何 MySQL 专有特性**
（JSON 列、排序规则、生成列、前缀索引）。

因为本地与测试跑 SQLite、线上跑 MySQL，一旦用了专有特性，
就会出现最经典的"本地绿、线上炸"。这条规矩的代价是多写几行序列化代码，
换来的是两种库行为一致。

### 时间：一条全项目统一的规矩

* **存库一律 naive UTC**（MySQL 的 `DATETIME` 不带时区，存 aware 会丢信息）
* **出接口一律 aware UTC**（客户端才知道那是 UTC）

边界只有两个函数：[`utcnow()`](../../backend/app/core/clock.py) 写库前用，
[`as_aware()`](../../backend/app/core/clock.py) 出接口前用。

---

## 六、怎么连你的 MySQL（宝塔 / NAS）

在 `backend/.env` 里写：

```ini
PLOVE_DATABASE_URL=mysql+pymysql://plove:你的密码@192.168.1.10:3306/plove?charset=utf8mb4
```

然后在宝塔的数据库面板里建一个库（和上面的库名一致），再跑：

```powershell
cd E:\Pychon-code\NY\Plove1.0\backend
.\.venv\Scripts\python.exe tools\init_db.py            # 建表
.\.venv\Scripts\python.exe tools\init_db.py --check    # 只查连通性
```

输出里的密码会**自动打码**（`plove:***@…`），所以日志可以放心贴出来。

### 建议再做一步：拿真库验一遍

本地的表是建在 SQLite 上的，线上是 MySQL。两者"大部分时候"一致，
而"大部分时候"正是事故来源。所以留了一个开关：

```powershell
$env:PLOVE_TEST_DATABASE_URL="mysql+pymysql://plove:密码@192.168.1.10:3306/plove_test?charset=utf8mb4"
.\.venv\Scripts\python.exe -m pytest -m mysql -v
```

它会在真库上建表 + 跑一遍完整激活流程，最后清掉自己写的数据。
**建议指向一个单独的 `plove_test` 库，别指生产库。**

### 本项目的实际环境（2026-09-30 实测已连通）

| 项 | 值 |
| --- | --- |
| NAS / MySQL 主机 | `192.168.31.5` |
| 宝塔面板 | `https://192.168.31.5:38888` |
| **MySQL 对外端口** | **`33306`**（不是 3306） |
| MySQL 版本 | 5.7.44 |
| 库 / 用户 | `plove_test` / `plove_test`（权限已设为「所有人」） |

连接串：

```ini
PLOVE_DATABASE_URL=mysql+pymysql://plove_test:***@192.168.31.5:33306/plove_test?charset=utf8mb4
```

### 两个踩过的坑

**一、MySQL 跑在 Docker 容器里，端口映射到了宿主 `33306`。**
容器内 `ss -tlnp` 显示 `*:3306` 看着一切正常，但从外面连是**主动拒绝**。
"主动拒绝（RST）"和"超时"要分清：超时是防火墙 DROP，主动拒绝是
**那个地址端口上根本没有监听** —— 也就是映射没出来。
用端口扫描在 `3306 / 13306 / 33306 …` 里找出真正映射的那个即可，不用重建容器。

**二、宝塔建库默认授权是 `库名@localhost`。**
端口通了之后会换成 `Access denied for user 'plove_test'@'192.168.31.69'`。
要在宝塔 → 数据库 → 权限里把「本地服务器」改成「所有人」（或指定 `192.168.31.%`）。
这两件事**要一起做**，否则会来回跑两趟。

### MySQL 5.7 的前置检查（本项目已核过，全部合格）

| 项 | 值 | 为什么重要 |
| --- | --- | --- |
| 库字符集 | `utf8mb4` / `utf8mb4_general_ci` | 中文 / emoji |
| 行格式 | `dynamic` | 索引前缀能到 3072 字节（老格式 767，varchar(255) 索引就会爆）|
| `sql_mode` | 含 `STRICT_TRANS_TABLES` | 超长/脏数据直接报错，不静默截断 |
| `innodb_large_prefix` | `ON` | 同上 |

---

## 七、发码

```powershell
.\.venv\Scripts\python.exe tools\issue_code.py --days 30
.\.venv\Scripts\python.exe tools\issue_code.py --hours 24 --count 5 --note "第一批试用"
```

输出形如：

```
已签发 2 个码，时长 720 小时（30 天）
  PLV-9Z95-KBF3-2ZDT
  PLV-YYLY-6B3V-X4AJ
```

码的字符集**去掉了 `I` `O` `0` `1`** —— 人要在纸上或聊天里转抄，这四个字符最容易看错。
客户端输入时大小写、空格、全角横线都会自动消化。

---

## 八、实测结果（不是推测）

```
未激活访问内容  -> 401 UNAUTHORIZED
激活            -> 200  剩余 86400 秒（正好 24h）, 心跳间隔 30 秒
站点列表        -> 200  ['ai2048', 'ncat21']
首页（真实抓取）-> 200  22 条推荐
播放（真实抓取）-> 200  m3u8
心跳            -> 200  is_active = True
第二台激活      -> 200
第一台心跳      -> is_active = False       ← 被顶掉第一台再访问内容-> 409 SESSION_KICKED
```

以上流程后来又**对着 NAS 上的真 MySQL 重跑了一遍**，结果一致，
并且回读数据库确认了中文没乱码（`note` 和 `device_name` 原样取回）：

```
签发            -> PLV-MP7B-VGD9-42LJ
激活            -> 200  剩余 86399 秒
站点列表        -> 200
心跳 is_active  -> True
第一台心跳      -> False
第一台访问内容  -> SESSION_KICKED
库里码数 / 设备数 -> 1 / 2
中文备注 / 设备名 -> 原样取回，未乱码
```

---

## 九、踩的一个坑

**HTTP 头里不能放非 ASCII 字符。** 我在测试里拿中文当伪造令牌，
结果 httpx 在**发请求之前**就编码失败了（头字段按 ascii/latin-1 编码）。
教训：设备令牌、错误注入这类东西一律用 ASCII。

---

## 十、这一步**没有**做什么

| 没做 | 为什么 |
| --- | --- |
| 远程配置 / kill switch | 属于阶段 5，跟部署一起做 |
| 后台管理面板 | 阶段 7；现在发码/封码靠命令行工具 |
| 审计日志表 | 等管理操作真的多起来再加 |
| 缓存与熔断 | 阶段 4 |
| 数据库迁移（Alembic） | 现在两张表、结构还在动。等结构稳定再引入 |
| 刷新令牌 / 令牌轮换 | 激活码量级小，先不做 |

---

## 十一、下一步

**阶段 4：缓存与稳定性** —— 列表/详情两级缓存 + singleflight 防击穿、
每站并发上限、连续失败熔断、把爬虫的 `selftest` 接进来做结构指纹告警。
