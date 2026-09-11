import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from xianyu.app import create_app
from xianyu.im_client import GoofishIMClient
from xianyu.im_service import im_service
from xianyu.mtop import apply_cookies, logout
from tests.test_im_api import FakeIM


OLD_SCHEMA = """
CREATE TABLE im_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    sender_id VARCHAR(64) NOT NULL,
    sender_name VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    direction VARCHAR(16) NOT NULL,
    replied INT NOT NULL,
    reply_text TEXT,
    raw_json TEXT,
    created_at TIMESTAMP NOT NULL
)
"""


def test_old_im_messages_table_migrates_and_stores(tmp_path: Path, monkeypatch):
    db = tmp_path / "old.sqlite3"
    con = sqlite3.connect(db)
    con.execute(OLD_SCHEMA)
    con.execute(
        "INSERT INTO im_messages "
        "(conversation_id, sender_id, sender_name, content, direction, replied, created_at) "
        "VALUES ('1', '2', '买家', '旧消息', 'in', 0, '2026-01-01 00:00:00')"
    )
    con.commit()
    con.close()

    async def fake_login():
        return {"logged_in": True, "user_id": "1"}

    fake = FakeIM()
    monkeypatch.setattr("xianyu.routers.im.require_login", fake_login)
    im_service.client_factory = lambda: fake
    logout()
    apply_cookies("unb=1; cookie2=abc")
    app = create_app(connect_xianyu=False, db_url=f"sqlite://{db}")
    try:
        with TestClient(app) as client:
            old = client.get("/im/messages", params={"conversation_id": "1"})
            assert old.status_code == 200
            assert any(item["text"] == "旧消息" for item in old.json())

            started = client.post("/im/start")
            assert started.status_code == 200
            fake._queue.put_nowait(
                {
                    "conversation_id": "99",
                    "sender_id": "99",
                    "sender_name": "买家",
                    "text": "还在吗",
                }
            )
            messages = None
            for _ in range(30):
                messages = client.get("/im/messages", params={"conversation_id": "99"})
                if any(item["text"] == "还在吗" for item in messages.json()):
                    break
                import time

                time.sleep(0.05)
            assert messages is not None
            assert any(item["text"] == "还在吗" for item in messages.json())
    finally:
        im_service.client_factory = GoofishIMClient
        logout()
