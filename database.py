import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import DB_PATH, ADMIN_IDS

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=5000;")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS codes (
                code TEXT PRIMARY KEY,
                code_type TEXT NOT NULL DEFAULT 'normal', -- 'normal' or 'special'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                is_used INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT NULL,
                used_at TIMESTAMP DEFAULT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                business_connection_id TEXT,
                code_used TEXT,
                tracking_type TEXT DEFAULT 'normal', -- 'normal' or 'special'
                is_active INTEGER DEFAULT 1,
                connected_at TIMESTAMP,
                last_activity TIMESTAMP,
                total_messages INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cached_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                chat_id INTEGER,
                message_id INTEGER,
                sender_id INTEGER,
                sender_name TEXT,
                sender_username TEXT,
                text TEXT,
                media_type TEXT,
                file_id TEXT,
                caption TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add initial config admins if not already present
        for admin_id in ADMIN_IDS:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (admin_id,)
            )

        await db.commit()

# --- Code Operations ---

async def create_code(code: str, code_type: str, created_by: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO codes (code, code_type, created_by, is_used) VALUES (?, ?, ?, 0)",
                (code, code_type, created_by)
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"Error creating code: {e}")
        return False

async def get_code(code: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM codes WHERE code = ?", (code,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def use_code(code: str, user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "UPDATE codes SET is_used = 1, used_by = ?, used_at = ? WHERE code = ?",
                (user_id, now, code)
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"Error using code: {e}")
        return False

async def get_active_codes(limit: int = 50) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM codes WHERE is_used = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_all_codes(limit: int = 100) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM codes ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def delete_code(code: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM codes WHERE code = ?", (code,))
            await db.commit()
            return True
    except Exception:
        return False

async def clear_unused_codes() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM codes WHERE is_used = 0")
        count = cursor.rowcount
        await db.commit()
        return count

# --- User Operations ---

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def get_user_by_connection(connection_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE business_connection_id = ?",
            (connection_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def register_or_update_user(
    user_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    username: Optional[str] = None,
    business_connection_id: Optional[str] = None,
    code_used: Optional[str] = None,
    tracking_type: str = "normal",
    is_active: int = 1
):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            existing = await cursor.fetchone()
        if existing:
            await db.execute("""
                UPDATE users SET
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    username = COALESCE(?, username),
                    business_connection_id = COALESCE(?, business_connection_id),
                    code_used = COALESCE(?, code_used),
                    tracking_type = COALESCE(?, tracking_type),
                    is_active = ?,
                    last_activity = ?
                WHERE user_id = ?
            """, (
                first_name, last_name, username, business_connection_id,
                code_used, tracking_type, is_active, now, user_id
            ))
        else:
            await db.execute("""
                INSERT INTO users (
                    user_id, first_name, last_name, username,
                    business_connection_id, code_used, tracking_type,
                    is_active, connected_at, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, first_name, last_name, username,
                business_connection_id, code_used, tracking_type,
                is_active, now, now
            ))
        await db.commit()

async def set_user_connection(user_id: int, connection_id: str, is_active: bool):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET
                business_connection_id = ?,
                is_active = ?,
                last_activity = ?
            WHERE user_id = ?
        """, (connection_id, 1 if is_active else 0, now, user_id))
        await db.commit()

async def set_user_status(user_id: int, is_active: bool):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_active = ?, last_activity = ? WHERE user_id = ?",
            (1 if is_active else 0, now, user_id)
        )
        await db.commit()

async def get_all_users() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY connected_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def increment_user_messages(user_id: int):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET
                total_messages = total_messages + 1,
                last_activity = ?
            WHERE user_id = ?
        """, (now, user_id))
        await db.commit()

async def delete_user(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()
            return True
    except Exception:
        return False

# --- Cached Messages for Edit/Delete tracking ---

async def save_cached_message(
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    sender_id: Optional[int] = None,
    sender_name: Optional[str] = None,
    sender_username: Optional[str] = None,
    text: Optional[str] = None,
    media_type: Optional[str] = None,
    file_id: Optional[str] = None,
    caption: Optional[str] = None
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cached_messages (
                business_connection_id, chat_id, message_id,
                sender_id, sender_name, sender_username,
                text, media_type, file_id, caption
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_connection_id, chat_id, message_id,
            sender_id, sender_name, sender_username,
            text, media_type, file_id, caption
        ))
        await db.commit()

async def get_cached_message(
    business_connection_id: str,
    chat_id: int,
    message_id: int
) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM cached_messages
            WHERE business_connection_id = ? AND chat_id = ? AND message_id = ?
            ORDER BY id DESC LIMIT 1
        """, (business_connection_id, chat_id, message_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def update_cached_message_text(
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    new_text: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE cached_messages SET text = ?
            WHERE business_connection_id = ? AND chat_id = ? AND message_id = ?
        """, (new_text, business_connection_id, chat_id, message_id))
        await db.commit()

async def clean_old_messages(days: int = 7):
    async with aiosqlite.connect(DB_PATH) as db:
        threshold = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("DELETE FROM cached_messages WHERE created_at < ?", (threshold,))
        await db.commit()

# --- Admin Operations ---

async def get_all_admin_ids() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            rows = await cursor.fetchall()
            db_admins = [r[0] for r in rows]
            # Merge with config admins
            all_admins = set(db_admins + ADMIN_IDS)
            return list(all_admins)

async def add_admin(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return True
    except Exception:
        return False

async def is_admin_user(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

