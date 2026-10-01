"""测试包。

从 ``crawler/`` 目录运行::

    python -m unittest discover -s tests -t . -v

放在包初始化里而不是各个测试文件里，是因为 ``crawler_kit.log`` 的级别在
**import 时**读取环境变量 —— 谁先 import 谁说了算。
"""

import os

# 测试期间只保留错误日志，避免闸门/重试的 INFO 刷屏
os.environ.setdefault("CRAWLER_LOG", "error")
