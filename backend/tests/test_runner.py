"""爬虫子进程执行器。

这里测的全部是**真实行为**：假爬虫真的被当子进程跑起来，
所以超时、脏输出、错误码翻译走的都是线上同一段代码。
"""

from __future__ import annotations

import time

import pytest

from app.core.errors import AppError, ErrorCode


def test_meta_roundtrip(fake_runner):
    data = fake_runner.run("fake", "meta")
    assert data["key"] == "fake"
    assert "home" in data["capabilities"]


def test_options_are_passed_through(fake_runner):
    assert fake_runner.run("fake", "category", page=3)["page"] == 3


def test_unknown_site_is_not_found(fake_runner):
    with pytest.raises(AppError) as exc:
        fake_runner.run("nope", "meta")
    assert exc.value.code is ErrorCode.NOT_FOUND


@pytest.mark.parametrize("key", ["../crawler_kit/errors", "Fake", "a b", "", "x"])
def test_illegal_key_is_rejected(fake_runner, key):
    """key 就是文件名，不校验的话 ``../`` 就能变成路径穿越。"""
    with pytest.raises(AppError) as exc:
        fake_runner.run(key, "meta")
    assert exc.value.code is ErrorCode.BAD_REQUEST


def test_crawler_error_is_translated(fake_runner, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "error")
    with pytest.raises(AppError) as exc:
        fake_runner.run("fake", "home")
    assert exc.value.code is ErrorCode.UPSTREAM_BLOCKED
    assert "拦住" in exc.value.message


def test_garbage_stdout_is_a_parse_error(fake_runner, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "garbage")
    with pytest.raises(AppError) as exc:
        fake_runner.run("fake", "home")
    assert exc.value.code is ErrorCode.UPSTREAM_PARSE_ERROR


def test_hung_crawler_hits_the_hard_timeout(fake_runner, monkeypatch):
    """爬虫卡死时，负责 kill 的是**我们** —— 不许把在线请求一起拖死。"""
    monkeypatch.setenv("FAKE_MODE", "timeout")
    started = time.monotonic()
    with pytest.raises(AppError) as exc:
        fake_runner.run("fake", "home")
    elapsed = time.monotonic() - started

    assert exc.value.code is ErrorCode.UPSTREAM_TIMEOUT
    assert elapsed < 6, f"硬超时没生效，等了 {elapsed:.1f}s"


def test_play_uses_its_own_timeout(fake_settings, fake_runner):
    """播放类命令超时另算：它要多抓一个播放页。"""
    assert fake_runner.timeout_for("play") == fake_settings.crawler_timeout_play
    assert fake_runner.timeout_for("home") == fake_settings.crawler_timeout
