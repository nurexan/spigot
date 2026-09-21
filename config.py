import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip() or "8751576357:AAHVuGYC8Ua3WnSKeRKI64oXRe7o6mM0_Ck"

# Admin IDs list
admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
if admin_ids_raw:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
else:
    ADMIN_IDS = [7832781255]

CACHE_RETENTION_DAYS = int(os.getenv("CACHE_RETENTION_DAYS", 7))

db_path_env = os.getenv("DB_PATH", "").strip()
if db_path_env:
    DB_PATH = Path(db_path_env)
else:
    DB_PATH = BASE_DIR / "spy_bot.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
