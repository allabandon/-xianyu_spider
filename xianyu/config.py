import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite://{DATA_DIR / 'xianyu.sqlite3'}"
SESSION_PATH = DATA_DIR / "session.json"
QR_SESSIONS_PATH = DATA_DIR / "qr_sessions.json"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def init_database() -> None:
    from tortoise import Tortoise

    await Tortoise.init(db_url=DATABASE_URL, modules={"models": ["xianyu.models"]})
    await Tortoise.generate_schemas()


init_database = init_database
QR_SESSIONS_PATH = QR_SESSIONS_PATH
