import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
import database as db
from handlers import admin_router, user_router, business_router

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def background_cache_cleaner():
    """Eski kesh xabarlarini har 24 soatda tozalash"""
    while True:
        try:
            await asyncio.sleep(86400) # 24 soat
            await db.clean_old_messages(days=7)
            logger.info("Message cache cleanup completed.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cache cleaner: {e}")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Iltimos, .env faylini to'ldiring.")
        return

    # Ma'lumotlar bazasini ishga tushirish
    await db.init_db()
    logger.info("Database muvaffaqiyatli ishga tushirildi.")

    # Bot va Dispatcher yaratish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(business_router)

    # Bot ma'lumotlarini olish
    bot_info = await bot.get_me()
    logger.info(f"Bot ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")

    # Orqa fonda keshni tozalash jarayonini boshlash
    cleaner_task = asyncio.create_task(background_cache_cleaner())

    try:
        # Pollingni barcha kerakli Telegram Business update turlari bilan boshlash
        allowed_updates = [
            "message",
            "edited_message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages"
        ]
        # drop_pending_updates=False qilib bot o'chiq bo'lganda kelgan /start larni qabul qilamiz
        await dp.start_polling(bot, allowed_updates=allowed_updates, drop_pending_updates=False)
    finally:
        cleaner_task.cancel()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
