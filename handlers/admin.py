import random
import string
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from datetime import datetime

import database as db
import keyboards as kb
from config import BOT_TOKEN

admin_router = Router()

async def check_admin_access(user_id: int) -> bool:
    admin_ids = await db.get_all_admin_ids()
    return user_id in admin_ids

def generate_random_code(prefix: str = "") -> str:
    """6 xonali tasodifiy kod yaratish"""
    digits = "".join(random.choices(string.digits, k=6))
    if prefix:
        return f"{prefix}{digits}"
    return digits

@admin_router.message(Command("admin"))
@admin_router.message(Command("start"), F.text.func(lambda text: not text.startswith("/start ") or len(text.split()) == 1))
async def cmd_admin_start(message: Message):
    is_adm = await check_admin_access(message.from_user.id)
    if not is_adm:
        # If user is not admin, pass through to user handler or register
        return

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {message.from_user.full_name}!</b>\n\n"
        f"🤖 <b>Mockgift Business Monitoring</b> boshqaruv paneliga xush kelibsiz.\n\n"
        f"Quyidagi tugmalar orqali kod yaratishingiz va ulangan foydalanuvchilarni kuzatishingiz mumkin:"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb.get_admin_main_kb())

# ➕ Oddiy Kod Yaratish
@admin_router.message(F.text == "➕ Kod yaratish")
async def handle_create_normal_code(message: Message):
    if not await check_admin_access(message.from_user.id):
        return

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
@admin_router.message(F.text == "➕ Maxsus kod (Kuzatuv)")
async def handle_create_special_code(message: Message):
    if not await check_admin_access(message.from_user.id):
        return

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
@admin_router.message(F.text == "👥 Foydalanuvchilar")
async def handle_users_list(message: Message):
    if not await check_admin_access(message.from_user.id):
        return

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
@admin_router.message(F.text == "💳 Faol kodlar")
async def handle_active_codes(message: Message):
    if not await check_admin_access(message.from_user.id):
        return

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
@admin_router.callback_query(F.data.startswith("user_view_"))
async def cb_user_view(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"• <b>Ism:</b> {user.get('first_name', '')} {user.get('last_name', '') or ''}\n"
        f"• <b>Username:</b> @{user.get('username') or 'mavjud_emas'}\n"
        f"• <b>ID:</b> <code>{user.get('user_id')}</code>\n"
        f"• <b>Holat:</b> {status_str}\n"
        f"• <b>Rejim:</b> {mode_str}\n"
        f"• <b>Ishlatgan kodi:</b> <code>{code_used}</code>\n"
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
@admin_router.callback_query(F.data.startswith("toggle_user_"))
async def cb_toggle_user(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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

        text = (
            f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
            f"• <b>Ism:</b> {user.get('first_name', '')} {user.get('last_name', '') or ''}\n"
            f"• <b>Username:</b> @{user.get('username') or 'mavjud_emas'}\n"
            f"• <b>ID:</b> <code>{user.get('user_id')}</code>\n"
            f"• <b>Holat:</b> {status_str}\n"
            f"• <b>Rejim:</b> {mode_str}\n"
            f"• <b>Ishlatgan kodi:</b> <code>{code_used}</code>\n"
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
@admin_router.callback_query(F.data.startswith("delete_user_"))
async def cb_delete_user(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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
@admin_router.callback_query(F.data == "back_to_users")
@admin_router.callback_query(F.data == "refresh_users")
async def cb_refresh_users(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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

# Kodni o'chirish
@admin_router.callback_query(F.data.startswith("code_del_"))
async def cb_delete_code(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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
@admin_router.callback_query(F.data == "clear_unused_codes")
async def cb_clear_unused_codes(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    count = await db.clear_unused_codes()
    await call.answer(f"{count} ta ishlatilmagan kod o'chirildi!", show_alert=True)

    text = (
        f"💳 <b>Kodlar statistikasi:</b>\n"
        f"🟢 Faol: <b>0</b> ta\n\n"
        f"<i>Barcha ishlatilmagan kodlar muvaffaqiyatli tozalandi.</i>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.get_codes_list_ikb([]))

# Kodlarni yangilash
@admin_router.callback_query(F.data == "refresh_codes")
async def cb_refresh_codes(call: CallbackQuery):
    if not await check_admin_access(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

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
@admin_router.message(Command("addadmin"))
async def cmd_add_admin(message: Message):
    if not await check_admin_access(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Foydalanish: <code>/addadmin &lt;Telegram_ID&gt;</code>", parse_mode="HTML")
        return

    new_admin_id = int(args[1])
    await db.add_admin(new_admin_id)
    await message.answer(f"✅ Yangi admin qo'shildi: <code>{new_admin_id}</code>", parse_mode="HTML")
