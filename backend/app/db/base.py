"""SQLAlchemy 的 ``Base``。

所有模型都从这里继承。**不要在这里塞业务方法** —— 它只管"表长什么样"。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明式基类。

    注意：这里刻意**不**开启任何 MySQL 专有选项，
    保证同一套模型在 SQLite（本地/测试）与 MySQL（线上）上行为一致。
    """
