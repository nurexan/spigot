from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

import database as db
import keyboards as kb

user_router = Router()

async def is_admin_user(user_id: int) -> bool:
    admin_ids = await db.get_all_admin_ids()
    return user_id in admin_ids

@user_router.message(CommandStart())
async def handle_user_start(message: Message):
    if await is_admin_user(message.from_user.id):
        # Admin /start handled in admin_router
        return

    # Check if there is a start parameter (code deep-link)
    args = message.text.split()
    if len(args) > 1:
        code = args[1].strip()
        await process_user_code(message, code)
        return

    # Check if user already exists
    existing = await db.get_user(message.from_user.id)
    if existing and existing.get("is_active"):
        text = (
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "🛡 <b>Anti-Delete & Spy Himoya xizmati faol ishlamoqda.</b>\n\n"
            "Suhbatdoshlaringiz o'chirib yuborgan xabarlari, tahrirlangan matnlari va barcha "
            "o'chib ketuvchi (view-once) fayllar avtomatik saqlanib, shu yerga yuboriladi."
        )
        await message.answer(text, parse_mode="HTML")
        return

    welcome_text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🛡 <b>Telegram Business Anti-Delete & Media Saver</b> botiga xush kelibsiz.\n\n"
        "Ushbu bot yordamida shaxsiy chatlaringizda suhbatdoshingiz o'chirib yuborgan xabarlari, "
        "tahrirlangan yozishmalar va o'chib ketuvchi (taymerli) video/rasmlarni saqlab olishingiz mumkin.\n\n"
        "Xizmatni faollashtirish uchun sizga berilgan <b>Ulanish kodi</b>ni yuboring:"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@user_router.message(F.text.func(lambda text: not text.startswith("/") and len(text.strip()) >= 4))
async def handle_user_text_code(message: Message):
    if await is_admin_user(message.from_user.id):
        return

    code = message.text.strip()
    await process_user_code(message, code)

async def process_user_code(message: Message, code: str):
    code_data = await db.get_code(code)
    if not code_data:
        await message.answer(
            "❌ <b>Noto'g'ri kod!</b>\n\n"
            "Kiritilgan kod topilmadi. Iltimos, kodni to'g'ri kiritganingizni tekshiring.",
            parse_mode="HTML"
        )
        return

    if code_data.get("is_used") and code_data.get("used_by") != message.from_user.id:
        await message.answer(
            "⚠️ <b>Ushbu kod allaqachon ishlatilgan!</b>\n\n"
            "Iltimos, yangi ulanish kodini oling.",
            parse_mode="HTML"
        )
        return

    # Mark code as used
    await db.use_code(code, message.from_user.id)

    # Register/update user in DB
    await db.register_or_update_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        username=message.from_user.username,
        code_used=code,
        tracking_type=code_data.get("code_type", "normal"),
        is_active=0 # Will become 1 once Telegram business connects
    )

    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or "Mockgiftbot"

    instructions = (
        "✅ <b>Kod qabul qilindi!</b>\n\n"
        "Xizmatni Telegram hisobingizga ulash uchun quyidagi oddiy amallarni bajaring:\n\n"
        "1️⃣ Telegram <b>Sozlamalar (Settings)</b> bo'limiga kiring.\n"
        "2️⃣ <b>Telegram Business</b> ➡️ <b>Chatbotlar (Chatbots)</b> bo'limini oching.\n"
        f"3️⃣ Qidiruvga <code>@{bot_username}</code> deb yozing va botni tanlang.\n"
        "4️⃣ Botga barcha ruxsatlarni yoqing va <b>Tayyor (Done)</b> tugmasini bosing.\n\n"
        "⚡️ <i>Ulanishingiz bilanoq o'chirilgan xabarlar va o'chib ketuvchi rasmlarni ushlab berish xizmati ishga tushadi!</i>"
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
        await call.answer("✅ Bot Telegram Business hisobingizga muvaffaqiyatli ulangan va faol!", show_alert=True)
    else:
        await call.answer("⚠️ Bot hali ulanmagan. Iltimos, Telegram Sozlamalar -> Telegram Business -> Chatbots bo'limidan botni ulang.", show_alert=True)
