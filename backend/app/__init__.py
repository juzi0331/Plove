"""Plove 后端网关。

分层与依赖方向（只允许向下依赖，禁止反向）::

    api  →  services  →  crawler / db  →  models
                          ↘  schemas  ↗
            core（最内层，谁都能用）

* ``api/``       薄路由：只声明参数与转发，不写业务
* ``services/``  业务编排：**不 import fastapi**，可脱离 HTTP 单测
* ``crawler/``  子进程调度：唯一接触爬虫的地方
                （注意区分：顶层 ``crawler/`` 是爬虫**本体**，这里的 ``app/crawler/``
                是后端**调度**爬虫的代码）
* ``models/``    ORM（数据库形状），不要泄漏到 API
* ``schemas/``   Pydantic（接口形状），契约的唯一来源
* ``core/``      config · logging · errors · 中间件 · 异常处理
"""

from __future__ import annotations

__version__ = "0.1.0"
