import html
import random
import string
from typing import Union
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, BaseFilter

import database as db
import keyboards as kb

admin_router = Router()

class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return await db.is_admin_user(user_id)

def generate_random_code(prefix: str = "") -> str:
    """6 xonali tasodifiy kod yaratish"""
    digits = "".join(random.choices(string.digits, k=6))
    if prefix:
        return f"{prefix}{digits}"
    return digits

START_COMMANDS = {"/start", "#start", r"\start", "start", "/admin"}

@admin_router.message(IsAdminFilter(), Command("admin"))
@admin_router.message(IsAdminFilter(), Command("start"), F.text.func(lambda text: len(text.split()) <= 1))
@admin_router.message(IsAdminFilter(), F.text.lower().in_(START_COMMANDS))
async def cmd_admin_start(message: Message):
    first_name = message.from_user.first_name if message.from_user else "Admin"
    full_name = message.from_user.full_name if message.from_user else first_name

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {html.escape(full_name)}!</b>\n\n"
        f"🤖 <b>Mockgift Business Monitoring</b> boshqaruv paneliga xush kelibsiz.\n\n"
        f"Quyidagi tugmalar orqali kod yaratishingiz va ulangan foydalanuvchilarni kuzatishingiz mumkin:"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb.get_admin_main_kb())

# ➕ Oddiy Kod Yaratish
@admin_router.message(IsAdminFilter(), F.text == "➕ Kod yaratish")
async def handle_create_normal_code(message: Message):
    code = generate_random_code()
    success = await db.create_code(code, "normal", message.from_user.id)

    if success:
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username or "Mockgiftbot"
        link = f"https://t.me/{bot_username}?start={code}"

        text = (
            f"✅ <b>Yangi ulanish kodi yaratildi!</b>\n\n"
            f"🔑 <b>Kod:</b> <code>{code}</code>\n"
            f"🔹 <b>Turi:</b> Oddiy kuzatuv\n"
            f"🔗 <b>To'g'ridan-to'g'ri havola:</b> {link}\n\n"
            f"📌 <i>Foydalanuvchiga ushbu kodni yoki havolani yuboring. U botga kirib Telegram Business orqali botni ulaydi.</i>"
        )
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Kod yaratishda xatolik yuz berdi. Qayta urinib ko'ring.")

# ➕ Maxsus Kod Yaratish (Kuzatuv)
@admin_router.message(IsAdminFilter(), F.text == "➕ Maxsus kod (Kuzatuv)")
async def handle_create_special_code(message: Message):
    code = generate_random_code()
    success = await db.create_code(code, "special", message.from_user.id)

    if success:
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username or "Mockgiftbot"
        link = f"https://t.me/{bot_username}?start={code}"

        text = (
            f"🚨 <b>Yangi MAXSUS KUZATUV kodi yaratildi!</b>\n\n"
            f"🔑 <b>Kod:</b> <code>{code}</code>\n"
            f"🚨 <b>Turi:</b> Maxsus kuzatuv\n"
            f"🔗 <b>Havola:</b> {link}\n\n"
            f"📌 <i>Ushbu kod orqali ulangan foydalanuvchining barcha xabarlari «🚨 MAXSUS KUZATUV:» belgisi bilan adminga keladi.</i>"
        )
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Kod yaratishda xatolik yuz berdi. Qayta urinib ko'ring.")

# 👥 Foydalanuvchilar ro'yxati
@admin_router.message(IsAdminFilter(), F.text == "👥 Foydalanuvchilar")
async def handle_users_list(message: Message):
    users = await db.get_all_users()
    if not users:
        await message.answer("ℹ️ Hozircha ulangan foydalanuvchilar mavjud emas.")
        return

    active_count = sum(1 for u in users if u.get("is_active"))
    inactive_count = len(users) - active_count

    header = (
        f"👥 <b>Ulangan foydalanuvchilar:</b>\n"
        f"📊 Jami: <b>{len(users)}</b> | 🟢 Faol: <b>{active_count}</b> | 🔴 Nofaol: <b>{inactive_count}</b>\n\n"
        f"<i>Batafsil ma'lumot va boshqarish uchun foydalanuvchini tanlang:</i>"
    )

    await message.answer(header, parse_mode="HTML", reply_markup=kb.get_users_list_ikb(users))

# 💳 Faol kodlar
@admin_router.message(IsAdminFilter(), F.text == "💳 Faol kodlar")
async def handle_active_codes(message: Message):
    codes = await db.get_active_codes(limit=20)
    all_codes = await db.get_all_codes(limit=50)

    used_count = sum(1 for c in all_codes if c.get("is_used"))
    unused_count = len(codes)

    text = (
        f"💳 <b>Kodlar statistikasi:</b>\n"
        f"🟢 Faol (ishlatilmagan): <b>{unused_count}</b> ta\n"
        f"⚪️ Ishlatilgan: <b>{used_count}</b> ta\n\n"
    )

    if codes:
        text += "<b>Mavjud faol kodlar:</b>\n"
        for c in codes[:10]:
            t_icon = "🚨 Maxsus" if c.get("code_type") == "special" else "🔹 Oddiy"
            text += f"• <code>{c.get('code')}</code> — {t_icon}\n"
    else:
        text += "<i>Hozirda yangi faol kodlar mavjud emas. Yangi kod yaratishingiz mumkin.</i>"

    await message.answer(text, parse_mode="HTML", reply_markup=kb.get_codes_list_ikb(codes))

# Foydalanuvchini ko'rish (Callback)
@admin_router.callback_query(IsAdminFilter(), F.data.startswith("user_view_"))
async def cb_user_view(call: CallbackQuery):
    user_id = int(call.data.replace("user_view_", ""))
    user = await db.get_user(user_id)
    if not user:
        await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    status_str = "🟢 Faol (Telegram Business ulangan)" if user.get("is_active") else "🔴 Nofaol (Bot uzilgan/o'chirilgan)"
    mode_str = "🚨 Maxsus Kuzatuv" if user.get("tracking_type") == "special" else "🔹 Oddiy Kuzatuv"

    code_used = user.get("code_used") or "Nomalum"
    conn_time = user.get("connected_at") or "Nomalum"
    last_act = user.get("last_activity") or "Nomalum"
    first_name = html.escape(user.get("first_name") or "")
    last_name = html.escape(user.get("last_name") or "")

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"• <b>Ism:</b> {first_name} {last_name}\n"
        f"• <b>Username:</b> @{html.escape(user.get('username') or 'mavjud_emas')}\n"
        f"• <b>ID:</b> <code>{user.get('user_id')}</code>\n"
        f"• <b>Holat:</b> {status_str}\n"
        f"• <b>Rejim:</b> {mode_str}\n"
        f"• <b>Ishlatgan kodi:</b> <code>{html.escape(code_used)}</code>\n"
        f"• <b>Ulanish vaqti:</b> {conn_time}\n"
        f"• <b>Oxirgi faollik:</b> {last_act}\n"
        f"• <b>Uzatilgan xabarlar soni:</b> {user.get('total_messages', 0)} ta\n"
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.get_user_detail_ikb(user_id, bool(user.get("is_active")))
    )
    await call.answer()

# Foydalanuvchi holatini o'zgartirish (Faol/Nofaol)
@admin_router.callback_query(IsAdminFilter(), F.data.startswith("toggle_user_"))
async def cb_toggle_user(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    new_state = bool(int(parts[3]))

    await db.set_user_status(user_id, new_state)
    await call.answer("Holat o'zgartirildi!")

    user = await db.get_user(user_id)
    if user:
        status_str = "🟢 Faol (Telegram Business ulangan)" if user.get("is_active") else "🔴 Nofaol (O'chirilgan)"
        mode_str = "🚨 Maxsus Kuzatuv" if user.get("tracking_type") == "special" else "🔹 Oddiy Kuzatuv"
        code_used = user.get("code_used") or "Nomalum"
        conn_time = user.get("connected_at") or "Nomalum"
        last_act = user.get("last_activity") or "Nomalum"
        first_name = html.escape(user.get("first_name") or "")
        last_name = html.escape(user.get("last_name") or "")

        text = (
            f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
            f"• <b>Ism:</b> {first_name} {last_name}\n"
            f"• <b>Username:</b> @{html.escape(user.get('username') or 'mavjud_emas')}\n"
            f"• <b>ID:</b> <code>{user.get('user_id')}</code>\n"
            f"• <b>Holat:</b> {status_str}\n"
            f"• <b>Rejim:</b> {mode_str}\n"
            f"• <b>Ishlatgan kodi:</b> <code>{html.escape(code_used)}</code>\n"
            f"• <b>Ulanish vaqti:</b> {conn_time}\n"
            f"• <b>Oxirgi faollik:</b> {last_act}\n"
            f"• <b>Uzatilgan xabarlar soni:</b> {user.get('total_messages', 0)} ta\n"
        )
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=kb.get_user_detail_ikb(user_id, bool(user.get("is_active")))
        )

# Foydalanuvchini o'chirish
@admin_router.callback_query(IsAdminFilter(), F.data.startswith("delete_user_"))
async def cb_delete_user(call: CallbackQuery):
    user_id = int(call.data.replace("delete_user_", ""))
    await db.delete_user(user_id)
    await call.answer("Foydalanuvchi bazadan o'chirildi!", show_alert=True)

    users = await db.get_all_users()
    if users:
        await call.message.edit_text(
            "👥 <b>Ulangan foydalanuvchilar:</b>",
            parse_mode="HTML",
            reply_markup=kb.get_users_list_ikb(users)
        )
    else:
        await call.message.edit_text("ℹ️ Hozircha ulangan foydalanuvchilar mavjud emas.")

# Foydalanuvchilar ro'yxatiga qaytish
@admin_router.callback_query(IsAdminFilter(), F.data.in_({"back_to_users", "refresh_users"}))
async def cb_refresh_users(call: CallbackQuery):
    users = await db.get_all_users()
    if not users:
        await call.message.edit_text("ℹ️ Hozircha ulangan foydalanuvchilar mavjud emas.")
        await call.answer()
        return

    active_count = sum(1 for u in users if u.get("is_active"))
    inactive_count = len(users) - active_count

    header = (
        f"👥 <b>Ulangan foydalanuvchilar:</b>\n"
        f"📊 Jami: <b>{len(users)}</b> | 🟢 Faol: <b>{active_count}</b> | 🔴 Nofaol: <b>{inactive_count}</b>\n\n"
        f"<i>Batafsil ma'lumot va boshqarish uchun foydalanuvchini tanlang:</i>"
    )

    await call.message.edit_text(header, parse_mode="HTML", reply_markup=kb.get_users_list_ikb(users))
    await call.answer()

# Kodni batafsil ko'rish (Callback)
@admin_router.callback_query(IsAdminFilter(), F.data.startswith("code_view_"))
async def cb_code_view(call: CallbackQuery):
    code_str = call.data.replace("code_view_", "")
    code_data = await db.get_code(code_str)
    if not code_data:
        await call.answer("Kod topilmadi!", show_alert=True)
        return

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username or "Mockgiftbot"
    link = f"https://t.me/{bot_username}?start={code_str}"

    c_type = "🚨 Maxsus Kuzatuv" if code_data.get("code_type") == "special" else "🔹 Oddiy Kuzatuv"
    status = "⚪️ Ishlatilgan" if code_data.get("is_used") else "🟢 Faol (ishlatilmagan)"
    used_by = code_data.get("used_by") or "Hech kim"
    used_at = code_data.get("used_at") or "-"
    created_at = code_data.get("created_at") or "-"

    text = (
        f"🔑 <b>Kod ma'lumotlari:</b>\n\n"
        f"• <b>Kod:</b> <code>{code_str}</code>\n"
        f"• <b>Turi:</b> {c_type}\n"
        f"• <b>Holati:</b> {status}\n"
        f"• <b>Ishlatgan ID:</b> <code>{used_by}</code>\n"
        f"• <b>Yaratilgan:</b> {created_at}\n"
        f"• <b>Ishlatilgan:</b> {used_at}\n"
        f"• <b>To'g'ridan-to'g'ri havola:</b>\n{link}"
    )

    kb_buttons = [
        [InlineKeyboardButton(text="🗑 Kodni o'chirish", callback_data=f"code_del_{code_str}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="refresh_codes")]
    ]
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await call.answer()

# Kodni o'chirish
@admin_router.callback_query(IsAdminFilter(), F.data.startswith("code_del_"))
async def cb_delete_code(call: CallbackQuery):
    code = call.data.replace("code_del_", "")
    await db.delete_code(code)
    await call.answer(f"Kod {code} o'chirildi!")

    codes = await db.get_active_codes(limit=20)
    all_codes = await db.get_all_codes(limit=50)

    used_count = sum(1 for c in all_codes if c.get("is_used"))
    unused_count = len(codes)

    text = (
        f"💳 <b>Kodlar statistikasi:</b>\n"
        f"🟢 Faol (ishlatilmagan): <b>{unused_count}</b> ta\n"
        f"⚪️ Ishlatilgan: <b>{used_count}</b> ta\n\n"
    )

    if codes:
        text += "<b>Mavjud faol kodlar:</b>\n"
        for c in codes[:10]:
            t_icon = "🚨 Maxsus" if c.get("code_type") == "special" else "🔹 Oddiy"
            text += f"• <code>{c.get('code')}</code> — {t_icon}\n"
    else:
        text += "<i>Hozirda yangi faol kodlar mavjud emas.</i>"

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.get_codes_list_ikb(codes))

# Barcha ishlatilmagan kodlarni tozalash
@admin_router.callback_query(IsAdminFilter(), F.data == "clear_unused_codes")
async def cb_clear_unused_codes(call: CallbackQuery):
    count = await db.clear_unused_codes()
    await call.answer(f"{count} ta ishlatilmagan kod o'chirildi!", show_alert=True)

    text = (
        f"💳 <b>Kodlar statistikasi:</b>\n"
        f"🟢 Faol: <b>0</b> ta\n\n"
        f"<i>Barcha ishlatilmagan kodlar muvaffaqiyatli tozalandi.</i>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.get_codes_list_ikb([]))

# Kodlarni yangilash
@admin_router.callback_query(IsAdminFilter(), F.data == "refresh_codes")
async def cb_refresh_codes(call: CallbackQuery):
    codes = await db.get_active_codes(limit=20)
    all_codes = await db.get_all_codes(limit=50)

    used_count = sum(1 for c in all_codes if c.get("is_used"))
    unused_count = len(codes)

    text = (
        f"💳 <b>Kodlar statistikasi:</b>\n"
        f"🟢 Faol (ishlatilmagan): <b>{unused_count}</b> ta\n"
        f"⚪️ Ishlatilgan: <b>{used_count}</b> ta\n\n"
    )

    if codes:
        text += "<b>Mavjud faol kodlar:</b>\n"
        for c in codes[:10]:
            t_icon = "🚨 Maxsus" if c.get("code_type") == "special" else "🔹 Oddiy"
            text += f"• <code>{c.get('code')}</code> — {t_icon}\n"
    else:
        text += "<i>Hozirda yangi faol kodlar mavjud emas.</i>"

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.get_codes_list_ikb(codes))
    await call.answer()

# Yangi admin qo'shish buyrug'i: /addadmin <user_id>
@admin_router.message(IsAdminFilter(), Command("addadmin"))
async def cmd_add_admin(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Foydalanish: <code>/addadmin &lt;Telegram_ID&gt;</code>", parse_mode="HTML")
        return

    new_admin_id = int(args[1])
    await db.add_admin(new_admin_id)
    await message.answer(f"✅ Yangi admin qo'shildi: <code>{new_admin_id}</code>", parse_mode="HTML")
