import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs list
admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
if admin_ids_raw:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
else:
    ADMIN_IDS = []

CACHE_RETENTION_DAYS = int(os.getenv("CACHE_RETENTION_DAYS", 7))
DB_PATH = BASE_DIR / "spy_bot.db"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
