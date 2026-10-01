"""业务编排层。

**硬规矩：不 import fastapi。** 这一层只吃普通 Python 对象、只抛 :class:`AppError`，
所以能脱离 HTTP 直接单测 —— 路由薄、业务厚，测试才好写。

依赖方向：``services`` 可以 import ``crawler`` / ``schemas`` / ``core``，
但反过来不行。
"""
