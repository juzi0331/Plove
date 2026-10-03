"""一条容易被忽略、但**一定会**被用户碰到的规矩：写操作要在响应之前落库。

:func:`app.api.deps.get_db` 的提交跑在依赖清理阶段，也就是响应送出**之后**。
对大多数接口这无所谓：客户端不会拿到响应就立刻去读同一行。
但激活接口不是，它的时序是本项目里唯一"必然"踩到的地方：

    客户端收到 ``redeem`` 的 200 → 立刻重新拉内容（被踢的错误态要靠它自己恢复）
    → 中间只隔一个响应往返

那一次写如果还躺在未提交的事务里，紧接着的请求就会读到旧状态、回 ``SESSION_KICKED``，
界面于是又弹一次"已在别的设备上使用"。用户看到的是**点了「在此设备继续」但没反应**。

这个时间差在真机上只有毫秒级，靠手点可能十次才中一次（排查时抓它得靠运气）。
所以这里把 ``get_db`` 换成一个**不提交**的版本，把"偶尔"变成"必然"：
只有路由自己显式提交了，下面的断言才会通过。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import DEVICE_TOKEN_HEADER, get_db
from app.models.device import Device
from app.services import admin_service

SITES = "/api/v1/sites"
REDEEM = "/api/v1/activation/redeem"


def _client_without_commit(app, db_factory, token: str) -> TestClient:
    """请求结束就关会话、**不提交** —— 正是"响应已送出、事务还没落库"那一刻。"""

    def _get_db():
        session = db_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app, headers={DEVICE_TOKEN_HEADER: token})


def test_resume_is_already_durable_for_the_very_next_request(
    fake_app, db_factory, db_session, activation
):
    device = db_session.scalar(select(Device).where(Device.token == activation["token"]))
    assert device is not None

    # 走真实的那条路径把活跃位清掉（后台的"踢下线"就是这么做的）
    admin_service.kick_device(db_session, device.id)
    db_session.commit()

    with _client_without_commit(fake_app, db_factory, activation["token"]) as client:
        # 被踢的这台现在进不来 —— 先确认前面的铺垫生效了
        assert client.get(SITES).status_code == 409

        resumed = client.post(
            REDEEM,
            json={"device_token": activation["token"], "device_name": "测试机"},
        )
        assert resumed.status_code == 200, resumed.text

        # 抢回之后**紧接着**的那一个请求，就是界面上"点完继续、页面自己恢复"走的路。
        # 它必须一次就过：这里没有重试，也没有第二次机会。
        again = client.get(SITES)
        assert again.status_code == 200, again.text
