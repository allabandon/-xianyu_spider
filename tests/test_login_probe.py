import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from xianyu.mtop import (
    LOGIN_REQUIRED_HINT,
    LoginRequired,
    apply_cookies,
    login_snapshot,
    logout,
    probe_login,
    require_login,
    _cookie_value,
)


def test_probe_login_skips_network_when_logged_out():
    logout()

    async def run():
        with patch("xianyu.mtop.fetch_login_user", AsyncMock(side_effect=AssertionError("should not fetch"))):
            return await probe_login()

    snap = asyncio.run(run())
    assert snap["logged_in"] is False
    assert not snap.get("login_expired")


def test_probe_login_keeps_session_when_goofish_ok():
    logout()
    apply_cookies("unb=9; cookie2=abc; _m_h5_tk=tok_1")

    async def run():
        with patch("xianyu.mtop.fetch_login_user", AsyncMock(return_value={"userId": "9"})):
            return await probe_login()

    snap = asyncio.run(run())
    assert snap["logged_in"] is True
    assert snap["user_id"] == "9"
    assert snap["user"]["userId"] == "9"
    logout()


def test_probe_login_downgrades_expired_cookies():
    logout()
    apply_cookies("unb=9; cookie2=abc; _m_h5_tk=tok_1; _m_h5_tk_enc=enc; cna=cna1")

    async def run():
        with patch("xianyu.mtop.fetch_login_user", AsyncMock(side_effect=RuntimeError("expired"))):
            return await probe_login()

    snap = asyncio.run(run())
    assert snap["logged_in"] is False
    assert snap["login_expired"] is True
    assert "spider.py login" in snap["hint"]
    assert login_snapshot()["logged_in"] is False
    assert _cookie_value("_m_h5_tk") == "tok_1"
    assert _cookie_value("_m_h5_tk_enc") == "enc"
    assert _cookie_value("cna") == "cna1"
    assert not _cookie_value("unb")
    logout()


def test_require_login_raises_when_missing_or_expired():
    logout()

    async def missing():
        with pytest.raises(LoginRequired) as exc:
            await require_login()
        assert LOGIN_REQUIRED_HINT in str(exc.value)

    asyncio.run(missing())

    apply_cookies("unb=9; cookie2=abc; _m_h5_tk=tok_1")

    async def expired():
        with patch("xianyu.mtop.fetch_login_user", AsyncMock(side_effect=RuntimeError("expired"))):
            with pytest.raises(LoginRequired):
                await require_login()

    asyncio.run(expired())
    logout()
