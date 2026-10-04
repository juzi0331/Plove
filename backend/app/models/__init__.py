"""ORM 模型（**数据库形状**，不是接口形状）。

接口形状在 ``app/schemas``。两者刻意分开：数据库加一列不该自动泄漏到 API。

**这里两个模型都必须被导入**，否则 ``Base.metadata`` 里没有它们的表，
``create_all`` 会静默地什么都不建 —— 那是很难查的一类 bug。
"""

from __future__ import annotations

from app.models.activation import ActivationCode
from app.models.device import Device
from app.models.experience import ExperienceActivePointer, ExperienceDraft, ExperienceRelease
from app.models.playback import PlaybackRecord
from app.models.site_setting import SiteSetting
from app.models.system_setting import SystemSetting

__all__ = [
    "ActivationCode",
    "Device",
    "ExperienceActivePointer",
    "ExperienceDraft",
    "ExperienceRelease",
    "PlaybackRecord",
    "SiteSetting",
    "SystemSetting",
]

