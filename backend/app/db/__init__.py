"""数据库层。

    base.py      SQLAlchemy 的 ``Base`` 与通用列类型
    session.py   引擎 / 会话工厂 / ``session_scope()``

**这一层不 import fastapi** —— FastAPI 的依赖（``get_db``）放在 ``app/api/deps.py``，
这样 services 能脱离 HTTP 直接用会话单测。

## 可移植性规矩（很重要）

表结构**只用通用类型**（``String`` / ``Integer`` / ``Boolean`` / ``DateTime`` / ``Text``），
不使用任何 MySQL 专有特性（``JSON`` 列、``utf8mb4_bin`` 排序规则、生成列、前缀索引）。

原因：本地与测试跑内存 SQLite，线上跑 MySQL。一旦用了专有特性，
就会出现最经典的"本地绿、线上炸"。这条规矩换来的代价是多写几行序列化代码，
但它换来的是**两种数据库行为一致**。
"""
