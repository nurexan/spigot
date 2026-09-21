from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import database as db
import keyboards as kb

user_router = Router()

USER_START_COMMANDS = {"/start", "#start", r"\start", "start"}

@user_router.message(CommandStart())
@user_router.message(F.text.lower().in_(USER_START_COMMANDS))
async def handle_user_start(message: Message):
    # 1. Start parametri (deep-link kod) mavjudligini tekshiramiz: masalan "/start 123456"
    args = message.text.split() if message.text else []
    if len(args) > 1:
        code = args[1].strip()
        await process_user_code(message, code)
        return

    # 2. Agar admin adashib user_router ga tushib qolsa, unga admin panelni ko'rsatamiz
    user_id = message.from_user.id if message.from_user else 0
    if await db.is_admin_user(user_id):
        from handlers.admin import cmd_admin_start
        await cmd_admin_start(message)
        return

    # 3. Foydalanuvchi allaqachon ulanganmi?
    existing = await db.get_user(user_id)
    if existing and existing.get("is_active"):
        text = (
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "🛡 <b>Anti-Delete & Spy Himoya xizmati faol ishlamoqda.</b>\n\n"
            "Suhbatdoshlaringiz o'chirib yuborgan xabarlari, tahrirlangan matnlari va barcha "
            "o'chib ketuvchi (view-once) fayllar avtomatik saqlanib, shu yerga yuboriladi."
        )
        await message.answer(text, parse_mode="HTML")
        return

    # 4. Yangi foydalanuvchiga xush kelibsiz matni
    welcome_text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🛡 <b>Telegram Business Anti-Delete & Media Saver</b> botiga xush kelibsiz.\n\n"
        "Ushbu bot yordamida shaxsiy chatlaringizda suhbatdoshingiz o'chirib yuborgan xabarlari, "
        "tahrirlangan yozishmalar va o'chib ketuvchi (taymerli) video/rasmlarni saqlab olishingiz mumkin.\n\n"
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

@user_router.message(F.text.func(lambda text: (
    not text.startswith("/") and
    not text.startswith("#") and
    not text.startswith("\\") and
    text.strip() not in ADMIN_BUTTON_TEXTS and
    len(text.strip()) >= 4
)))
async def handle_user_text_code(message: Message):
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

    # Foydalanuvchini bazaga qo'shamiz
    await db.register_or_update_user(
        user_id=user_id,
        first_name=message.from_user.first_name if message.from_user else None,
        last_name=message.from_user.last_name if message.from_user else None,
        username=message.from_user.username if message.from_user else None,
        code_used=code,
        tracking_type=code_data.get("code_type", "normal"),
        is_active=0 # Telegram Business ulanishi bilan 1 bo'ladi
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
