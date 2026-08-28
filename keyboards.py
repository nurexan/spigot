from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from typing import List, Dict, Any

def get_admin_main_kb() -> ReplyKeyboardMarkup:
    """Admin asosiy klaviaturasi (Skrinshotdagi kabi)"""
    kb = [
        [
            KeyboardButton(text="➕ Kod yaratish"),
            KeyboardButton(text="➕ Maxsus kod (Kuzatuv)")
        ],
        [
            KeyboardButton(text="👥 Foydalanuvchilar"),
            KeyboardButton(text="💳 Faol kodlar")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        is_persistent=True
    )

def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Bekor qilish klaviaturasi"""
    kb = [[KeyboardButton(text="❌ Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_users_list_ikb(users: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Foydalanuvchilar ro'yxati inline klaviaturasi"""
    buttons = []
    for u in users:
        status_emoji = "🟢" if u.get("is_active") else "🔴"
        name = u.get("first_name") or u.get("username") or f"ID: {u.get('user_id')}"
        mode_emoji = "🚨" if u.get("tracking_type") == "special" else "👤"
        text = f"{status_emoji} {mode_emoji} {name} (ID: {u.get('user_id')})"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"user_view_{u.get('user_id')}")])

    buttons.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_users")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_detail_ikb(user_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Foydalanuvchi boshqaruv paneli"""
    status_btn = (
        InlineKeyboardButton(text="🔴 O'chirish (Nofaol qilish)", callback_data=f"toggle_user_{user_id}_0")
        if is_active else
        InlineKeyboardButton(text="🟢 Faollashtirish", callback_data=f"toggle_user_{user_id}_1")
    )
    buttons = [
        [status_btn],
        [InlineKeyboardButton(text="🗑 Foydalanuvchini bazadan o'chirish", callback_data=f"delete_user_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_users")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_codes_list_ikb(codes: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Faol kodlar ro'yxati inline klaviaturasi"""
    buttons = []
    for c in codes[:10]:
        t_icon = "🚨 Maxsus" if c.get("code_type") == "special" else "🔹 Oddiy"
        text = f"{t_icon}: {c.get('code')}"
        buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"code_view_{c.get('code')}"),
            InlineKeyboardButton(text="🗑", callback_data=f"code_del_{c.get('code')}")
        ])

    bottom_row = []
    if codes:
        bottom_row.append(InlineKeyboardButton(text="🧹 Barchasini tozalash", callback_data="clear_unused_codes"))
    bottom_row.append(InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_codes"))
    buttons.append(bottom_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_connect_help_ikb(bot_username: str) -> InlineKeyboardMarkup:
    """Foydalanuvchiga Telegram Business orqali ulanish tugmasi"""
    buttons = [
        [InlineKeyboardButton(text="💼 Telegram Business Sozlamalari", url="tg://settings/business")],
        [InlineKeyboardButton(text="🔄 Ulanishni tekshirish", callback_data="check_my_connection")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
