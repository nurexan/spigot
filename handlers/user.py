import html
import os
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import database as db
import keyboards as kb

user_router = Router()

USER_START_COMMANDS = {"/start", "#start", r"\start", "start"}

@user_router.message(CommandStart())
@user_router.message(F.text.lower().in_(USER_START_COMMANDS))
async def handle_user_start(message: Message):
    user_id = message.from_user.id if message.from_user else 0

    # 1. Agar admin bo'lsa, adminga panelni ochamiz
    if await db.is_admin_user(user_id):
        from handlers.admin import cmd_admin_start
        await cmd_admin_start(message)
        return

    # 2. Start parametri (deep-link kod) mavjudligini tekshiramiz: masalan "/start 123456"
    args = message.text.split() if message.text else []
    if len(args) > 1:
        code = args[1].strip()
        await process_user_code(message, code)
        return

    # 3. Foydalanuvchi allaqachon ulanganmi?
    existing = await db.get_user(user_id)
    if existing and existing.get("is_active"):
        text = (
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "🛡 <b>Anti-Delete & Himoya xizmati faol ishlamoqda.</b>\n\n"
            "Suhbatdoshlaringiz o'chirib yuborgan xabarlari, tahrirlangan matnlari avtomatik saqlanib, "
            "shu bot orqali sizga yuboriladi."
        )
        await message.answer(text, parse_mode="HTML")
        return

    # 4. Yangi foydalanuvchiga xush kelibsiz matni
    welcome_text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🛡 <b>Telegram Business Anti-Delete & Media Saver</b> botiga xush kelibsiz.\n\n"
        "Ushbu bot yordamida shaxsiy chatlaringizda suhbatdoshingiz o'chirib yuborgan xabarlari "
        "va tahrirlangan yozishmalarini saqlab olishingiz mumkin.\n\n"
        "Xizmatni faollashtirish uchun sizga berilgan <b>Ulanish kodi</b>ni yuboring:"
    )
    await message.answer(welcome_text, parse_mode="HTML")

ADMIN_BUTTON_TEXTS = {
    "➕ Kod yaratish",
    "➕ Maxsus kod (Kuzatuv)",
    "👥 Foydalanuvchilar",
    "💳 Faol kodlar",
    "❌ Bekor qilish"
}

# ==========================================
# O'chirilgan xabarlarga reply qilib yuklab olish va Callback
# ==========================================

async def deliver_download_media(
    bot: Bot,
    chat_id: int,
    media_type: Optional[str],
    file_id: Optional[str],
    local_file_path: Optional[str],
    text: Optional[str] = None
):
    """
    O'chirilgan yoki saqlangan xabarni foydalanuvchiga to'liq yuklab berish.
    Ham ko'rish uchun native media, ham xotiraga/galereyaga saqlash uchun asl fayl (document) formatida beradi.
    """
    from handlers.business import send_saved_media

    has_file = bool(local_file_path and os.path.exists(local_file_path)) or bool(file_id)

    if not has_file and not text:
        await bot.send_message(chat_id, "ℹ️ Ushbu xabar uchun yuklab olishga media ma'lumot topilmadi.", parse_mode="HTML")
        return

    # Agar oddiy matn bo'lsa
    if not media_type or media_type == "text":
        await bot.send_message(
            chat_id,
            f"💬 <b>O'chirilgan xabar to'liq matni:</b>\n\n<code>{html.escape(text or '')}</code>",
            parse_mode="HTML"
        )
        return

    caption = f"📥 <b>Yuklab olingan {media_type.upper()}:</b>"
    if text and text != f"[{media_type.upper()}]":
        caption += f"\n\n💬 <code>{html.escape(text[:500])}</code>"

    # 1. Ko'rish / eshitish uchun native media formatida yuboramiz
    await send_saved_media(
        bot=bot,
        chat_id=chat_id,
        media_type=media_type,
        file_id=file_id,
        local_file_path=local_file_path,
        caption=caption
    )

    # 2. Xotiraga to'liq saqlab olish uchun asl fayl (document) formatida ham yuboramiz
    if media_type in {"photo", "video", "voice", "video_note"}:
        await send_saved_media(
            bot=bot,
            chat_id=chat_id,
            media_type=media_type,
            file_id=file_id,
            local_file_path=local_file_path,
            caption=f"📁 <b>{media_type.upper()} fayli (Xotiraga/Galereyaga yuklab olish uchun):</b>",
            as_document=True
        )


@user_router.message(F.reply_to_message)
async def handle_user_reply_to_notification(message: Message, bot: Bot):
    """
    Foydalanuvchi bot chatida o'chirilgan xabar bildirishnomasiga reply qilib HAR QANDAY xabar yozsa,
    fayl darhol to'liq yuklab beriladi.
    """
    replied = message.reply_to_message
    if not replied:
        return

    # Agar bot buyrug'i bo'lsa (masalan /start), o'z navbatiga qo'yamiz
    if message.text and message.text.startswith("/"):
        return

    user_id = message.from_user.id if message.from_user else 0

    # 1. sent_notifications jadvalidan qidiramiz
    notif = await db.get_sent_notification(user_id, replied.message_id)
    if notif:
        await deliver_download_media(
            bot=bot,
            chat_id=message.chat.id,
            media_type=notif.get("media_type"),
            file_id=notif.get("file_id"),
            local_file_path=notif.get("local_file_path"),
            text=notif.get("text")
        )
        return

    # 2. Agar notification topilmasa, replied.message_id bo'yicha cached_messages dan qidirib ko'ramiz
    cached = await db.get_cached_message_by_id(replied.message_id)
    if cached:
        await deliver_download_media(
            bot=bot,
            chat_id=message.chat.id,
            media_type=cached.get("media_type"),
            file_id=cached.get("file_id"),
            local_file_path=cached.get("local_file_path"),
            text=cached.get("text")
        )
        return


@user_router.callback_query(F.data.startswith("dl_msg_"))
async def cb_download_deleted_media(call: CallbackQuery, bot: Bot):
    """
    Inline tugma bosilganda faylni to'liq yuklab berish
    """
    cached_id_str = call.data.replace("dl_msg_", "")
    if not cached_id_str.isdigit():
        await call.answer("Xatolik yuz berdi!", show_alert=True)
        return

    cached_id = int(cached_id_str)
    cached = await db.get_cached_message_by_id(cached_id)
    if not cached:
        await call.answer("⚠️ Fayl keshdan topilmadi yoki muddati o'tgan.", show_alert=True)
        return

    await call.answer("📥 Fayl yuklab berilmoqda...")
    await deliver_download_media(
        bot=bot,
        chat_id=call.from_user.id,
        media_type=cached.get("media_type"),
        file_id=cached.get("file_id"),
        local_file_path=cached.get("local_file_path"),
        text=cached.get("text")
    )

@user_router.message(F.text.func(lambda text: (
    not text.startswith("/") and
    not text.startswith("#") and
    not text.startswith("\\") and
    text.strip() not in ADMIN_BUTTON_TEXTS and
    len(text.strip()) >= 4
)))
async def handle_user_text_code(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if await db.is_admin_user(user_id):
        return
    code = message.text.strip()
    await process_user_code(message, code)

async def process_user_code(message: Message, code: str):
    user_id = message.from_user.id if message.from_user else 0
    code_data = await db.get_code(code)
    if not code_data:
        await message.answer(
            "❌ <b>Noto'g'ri kod!</b>\n\n"
            "Kiritilgan kod topilmadi. Iltimos, kodni to'g'ri kiritganingizni tekshiring.",
            parse_mode="HTML"
        )
        return

    if code_data.get("is_used") and code_data.get("used_by") != user_id:
        await message.answer(
            "⚠️ <b>Ushbu kod allaqachon ishlatilgan!</b>\n\n"
            "Iltimos, yangi ulanish kodini oling.",
            parse_mode="HTML"
        )
        return

    # Kodni ishlatilgan deb belgilaymiz
    await db.use_code(code, user_id)

    # Foydalanuvchi avval ulangan bo'lsa, uning aktivlik holatini saqlab qolamiz
    existing = await db.get_user(user_id)
    keep_active = existing.get("is_active") if existing else 0

    await db.register_or_update_user(
        user_id=user_id,
        first_name=message.from_user.first_name if message.from_user else None,
        last_name=message.from_user.last_name if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
        code_used=code,
        tracking_type=code_data.get("code_type", "normal"),
        is_active=keep_active
    )

    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or "Mockgiftbot"

    instructions = (
        "✅ <b>Ulanish kodi qabul qilindi!</b>\n\n"
        "Xizmatni Telegram hisobingizga to'g'ri ulash uchun quyidagi amallarni bajaring:\n\n"
        "1️⃣ Telegram <b>Sozlamalar (Settings)</b> bo'limiga kiring.\n"
        "2️⃣ <b>Telegram Business</b> ➡️ <b>Chatbotlar (Chatbots)</b> bo'limini oching.\n"
        f"3️⃣ Qidiruv maydoniga <code>@{bot_username}</code> deb yozing va botni tanlang.\n"
        "4️⃣ ⚠️ <b>MUHIM QADAM:</b>\n"
        "   • <b>«Chatlar» (Чаты / Chats)</b> bo'limiga kiring va <b>«Barcha chatlar» (Все чаты / All chats)</b> ni belgilang!\n"
        "   • <i>(Agar buni qilmasangiz, faqat bitta chat yoki faqat yangi suhbatlar ko'rinadi)</i>.\n"
        "5️⃣ Botga barcha ruxsatlarni yoqing va <b>Tayyor (Done)</b> tugmasini bosing.\n\n"
        "⚡️ <i>Ulanishingiz bilanoq barcha suhbatlaringizdagi o'chirilgan xabarlarni saqlash xizmati to'liq ishga tushadi!</i>"
    )

    await message.answer(
        instructions,
        parse_mode="HTML",
        reply_markup=kb.get_connect_help_ikb(bot_username)
    )

@user_router.callback_query(F.data == "check_my_connection")
async def cb_check_my_connection(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if user and user.get("is_active"):
        await call.answer("✅ Bot Telegram Business hisobingizga muvaffaqiyatli ulangan va barcha chatlarda faol!", show_alert=True)
    else:
        await call.answer("⚠️ Bot hali to'liq ulanmagan. Iltimos, Telegram Sozlamalar -> Telegram Business -> Chatbots bo'limidan 'Barcha chatlar'ni tanlab botni ulang.", show_alert=True)
