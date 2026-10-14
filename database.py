import os
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
                tracking_type TEXT DEFAULT 'special', -- 'normal' or 'special'
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
                local_file_path TEXT,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migratsiyalar - mavjud bazaga yangi ustunlarni xavfsiz qo'shish
        try:
            await db.execute("ALTER TABLE cached_messages ADD COLUMN local_file_path TEXT;")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE cached_messages ADD COLUMN is_deleted INTEGER DEFAULT 0;")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                cached_id INTEGER,
                original_chat_id INTEGER,
                original_message_id INTEGER,
                media_type TEXT,
                file_id TEXT,
                local_file_path TEXT,
                text TEXT,
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

        # Indekslar - tezkor qidiruv uchun
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cached_msgs ON cached_messages (business_connection_id, chat_id, message_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_conn ON users (business_connection_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_codes_active ON codes (is_used, code_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sent_notif ON sent_notifications (user_id, bot_message_id);")

        # Barcha foydalanuvchilar maxsus kuzatuv rejimida bo'lishini ta'minlash (agar avval normal bo'lib qolgan bo'lsa)
        try:
            await db.execute("UPDATE users SET tracking_type = 'special' WHERE tracking_type = 'normal' OR tracking_type IS NULL;")
        except Exception:
            pass

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
    tracking_type: Optional[str] = None,
    is_active: Optional[int] = None
):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, is_active, tracking_type FROM users WHERE user_id = ?", (user_id,)) as cursor:
            existing = await cursor.fetchone()
        if existing:
            actual_active = existing[1] if is_active is None else is_active
            actual_tracking = tracking_type if tracking_type is not None else (existing[2] or "special")
            await db.execute("""
                UPDATE users SET
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    username = COALESCE(?, username),
                    business_connection_id = COALESCE(?, business_connection_id),
                    code_used = COALESCE(?, code_used),
                    tracking_type = ?,
                    is_active = ?,
                    last_activity = ?
                WHERE user_id = ?
            """, (
                first_name, last_name, username, business_connection_id,
                code_used, actual_tracking, actual_active, now, user_id
            ))
        else:
            actual_active = 0 if is_active is None else is_active
            actual_tracking = tracking_type
            if not actual_tracking and code_used:
                async with db.execute("SELECT code_type FROM codes WHERE code = ?", (code_used,)) as c:
                    crow = await c.fetchone()
                    if crow:
                        actual_tracking = crow[0]
            if not actual_tracking:
                async with db.execute("SELECT code_type FROM codes WHERE used_by = ? ORDER BY used_at DESC LIMIT 1", (user_id,)) as c:
                    crow = await c.fetchone()
                    if crow:
                        actual_tracking = crow[0]
            if not actual_tracking:
                actual_tracking = "special"

            await db.execute("""
                INSERT INTO users (
                    user_id, first_name, last_name, username,
                    business_connection_id, code_used, tracking_type,
                    is_active, connected_at, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, first_name, last_name, username,
                business_connection_id, code_used, actual_tracking,
                actual_active, now, now
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

async def set_user_tracking_type(user_id: int, tracking_type: str):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET tracking_type = ?, last_activity = ? WHERE user_id = ?",
            (tracking_type, now, user_id)
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
    caption: Optional[str] = None,
    local_file_path: Optional[str] = None
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO cached_messages (
                business_connection_id, chat_id, message_id,
                sender_id, sender_name, sender_username,
                text, media_type, file_id, caption, local_file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_connection_id, chat_id, message_id,
            sender_id, sender_name, sender_username,
            text, media_type, file_id, caption, local_file_path
        ))
        await db.commit()
        return cursor.lastrowid

async def update_cached_message_file(chat_id: int, message_id: int, local_file_path: str):
    """Media yuklab olingach, keshdagi xabar fayl yo'lini yangilash"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE cached_messages SET local_file_path = ?
                WHERE chat_id = ? AND message_id = ?
            """, (local_file_path, chat_id, message_id))
            await db.commit()
    except Exception as e:
        print(f"Error updating cached message file: {e}")

async def mark_cached_message_deleted(chat_id: int, message_id: int):
    """Xabar o'chirilganini belgilash (darhol o'chirib yubormasdan, replay qilganda yuklab olish uchun saqlab turamiz)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE cached_messages SET is_deleted = 1
                WHERE chat_id = ? AND message_id = ?
            """, (chat_id, message_id))
            await db.commit()
    except Exception as e:
        print(f"Error marking message deleted: {e}")

async def get_cached_message(
    business_connection_id: str,
    chat_id: int,
    message_id: int
) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # 1. Avval aniq connection_id bilan qidiramiz
        async with db.execute("""
            SELECT * FROM cached_messages
            WHERE business_connection_id = ? AND chat_id = ? AND message_id = ?
            ORDER BY id DESC LIMIT 1
        """, (business_connection_id, chat_id, message_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        # 2. Agar connection_id o'zgargan bo'lsa, chat_id va message_id bo'yicha qidiramiz
        async with db.execute("""
            SELECT * FROM cached_messages
            WHERE chat_id = ? AND message_id = ?
            ORDER BY id DESC LIMIT 1
        """, (chat_id, message_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def get_cached_message_by_id(cached_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM cached_messages WHERE id = ?", (cached_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def delete_cached_message(chat_id: int, message_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM cached_messages WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id)
            )
            await db.commit()
    except Exception as e:
        print(f"Error deleting cached message: {e}")

async def update_cached_message_text(
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    new_text: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE cached_messages SET text = ?
            WHERE (business_connection_id = ? OR chat_id = ?) AND message_id = ?
        """, (new_text, business_connection_id, chat_id, message_id))
        await db.commit()

# --- Sent Notifications for Reply tracking ---

async def save_sent_notification(
    bot_message_id: int,
    user_id: int,
    cached_id: Optional[int] = None,
    original_chat_id: Optional[int] = None,
    original_message_id: Optional[int] = None,
    media_type: Optional[str] = None,
    file_id: Optional[str] = None,
    local_file_path: Optional[str] = None,
    text: Optional[str] = None,
    caption: Optional[str] = None
):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO sent_notifications (
                    bot_message_id, user_id, cached_id, original_chat_id,
                    original_message_id, media_type, file_id, local_file_path,
                    text, caption
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_message_id, user_id, cached_id, original_chat_id,
                original_message_id, media_type, file_id, local_file_path,
                text, caption
            ))
            await db.commit()
    except Exception as e:
        print(f"Error saving sent notification: {e}")

async def get_sent_notification(user_id: int, bot_message_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM sent_notifications
            WHERE user_id = ? AND bot_message_id = ?
            ORDER BY id DESC LIMIT 1
        """, (user_id, bot_message_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        async with db.execute("""
            SELECT * FROM sent_notifications
            WHERE bot_message_id = ?
            ORDER BY id DESC LIMIT 1
        """, (bot_message_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def clean_old_messages(hours: int = 24):
    """24 soatdan oshgan eski xabarlarni va diskdagi kesh fayllarini tozalash"""
    try:
        threshold = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # 1. Diskdagi yuklab olingan fayllarni o'chirish
            try:
                async with db.execute(
                    "SELECT local_file_path FROM cached_messages WHERE created_at < ? AND local_file_path IS NOT NULL",
                    (threshold,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    for r in rows:
                        p = r["local_file_path"]
                        if p and os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
            except Exception as e_file:
                print(f"Error removing cached files: {e_file}")

            # 2. Bazadagi eski yozuvlarni tozalash
            await db.execute("DELETE FROM cached_messages WHERE created_at < ?", (threshold,))
            await db.execute("DELETE FROM sent_notifications WHERE created_at < ?", (threshold,))
            await db.commit()
    except Exception as e:
        print(f"Error cleaning old messages: {e}")

async def vacuum_db():
    """Bo'shatilgan joyni operatsion tizimga qaytarish uchun bazani optimallashtirish"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("VACUUM;")
    except Exception as e:
        print(f"Error running VACUUM: {e}")

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

async def remove_admin(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
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

