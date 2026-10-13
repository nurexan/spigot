import html
import logging
from typing import Optional
from aiogram import Router, Bot
from aiogram.types import (
    BusinessConnection,
    Message,
    BusinessMessagesDeleted
)

import database as db

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

    # Foydalanuvchini bazadan connection_id bo'yicha aniqlaymiz
    user = await db.get_user_by_connection(conn_id)
    if not user and sender_id:
        user = await db.get_user(sender_id)

    user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
    is_special = user and user.get("tracking_type") == "special"
    tracked_user_id = user.get("user_id") if user else None

    # Agar foydalanuvchi adminga bog'langan bo'lsa va admin paneldan nofaol qilingan bo'lsa, o'tkazib yuboramiz
    if user and user.get("is_active") == 0:
        return

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

    # Xabarning matni yoki media tavsifi
    msg_text = message.text or message.caption or ""
    media_type = None
    file_id = None

    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
    elif message.animation:
        media_type = "animation"
        file_id = message.animation.file_id
    elif message.video_note:
        media_type = "video_note"
        file_id = message.video_note.file_id
    elif message.voice:
        media_type = "voice"
        file_id = message.voice.file_id
    elif message.audio:
        media_type = "audio"
        file_id = message.audio.file_id
    elif message.document:
        media_type = "document"
        file_id = message.document.file_id
    elif message.sticker:
        media_type = "sticker"
        file_id = message.sticker.file_id
    elif message.contact:
        msg_text = f"👤 Kontakt: {message.contact.first_name} ({message.contact.phone_number})"
    elif message.location:
        msg_text = f"📍 Joylashuv: {message.location.latitude}, {message.location.longitude}"
    elif message.poll:
        msg_text = f"📊 So'rovnoma: {message.poll.question}"

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
        caption=message.caption
    )

    if tracked_user_id:
        await db.increment_user_messages(tracked_user_id)

    # DIQQAT: Oddiy kiruvchi xabarlar paytida kuzatilayotgan foydalanuvchiga xabar qaytarilmaydi!
    # Bu spy bot fosh bo'lishini va loop/spam paydo bo'lishini oldini oladi.
    # Foydalanuvchiga faqat xabar o'chirilganda yoki tahrirlanganda yuboriladi.

    # ADMINGA KUZATUV XABARINI YUBORISH
    mode_tag = "🚨 <b>MAXSUS KUZATUV:</b>" if is_special else "🔹 <b>KUZATUV:</b>"
    user_header_info = f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}"
    chat_info = f"💬 <b>Chat:</b> {html.escape(chat_partner)}"
    action_info = f"📍 <b>Harakat:</b> {html.escape(action_text)}"
    admin_header = f"{mode_tag}\n\n{user_header_info}\n{chat_info}\n{action_info}"

    admin_ids = await db.get_all_admin_ids()
    for admin_id in admin_ids:
        try:
            if media_type == "photo":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_video(chat_id=admin_id, video=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "animation":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_animation(chat_id=admin_id, animation=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video_note":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n⭕️ <b>Dumaloq video (Video Note):</b>", parse_mode="HTML")
                await bot.send_video_note(chat_id=admin_id, video_note=file_id)
            elif media_type == "voice":
                caption = safe_format_caption(admin_header, "🎤 Ovozli xabar")
                await bot.send_voice(chat_id=admin_id, voice=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "document":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_document(chat_id=admin_id, document=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "sticker":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n🎭 <b>Stiker:</b>", parse_mode="HTML")
                await bot.send_sticker(chat_id=admin_id, sticker=file_id)
            elif media_type == "audio":
                caption = safe_format_caption(admin_header, msg_text)
                await bot.send_audio(chat_id=admin_id, audio=file_id, caption=caption, parse_mode="HTML")
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

    # Foydalanuvchini bazadan olamiz
    user = await db.get_user_by_connection(conn_id)
    if not user and sender_id:
        user = await db.get_user(sender_id)

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
    user = await db.get_user_by_connection(conn_id)
    tracked_user_id = user.get("user_id") if user else None

    admin_ids = await db.get_all_admin_ids()
    is_admin_chat = event.chat.id in admin_ids

    for msg_id in event.message_ids:
        cached = await db.get_cached_message(conn_id, event.chat.id, msg_id)

        # Agar conn_id bo'yicha user topilmagan bo'lsa, keshdagi connection_id dan tekshirib ko'ramiz
        if not user and cached and cached.get("business_connection_id"):
            user = await db.get_user_by_connection(cached.get("business_connection_id"))
            if user:
                tracked_user_id = user.get("user_id")

        user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
        is_special = user and user.get("tracking_type") == "special"

        if cached:
            cached_sender = cached.get("sender_id")
            media_type = cached.get("media_type")
            fallback_media = media_type or "media"
            cached_text = cached.get("text") or cached.get("caption") or f"[{fallback_media.upper()}]"
            sender_name = cached.get("sender_username")
            sender_str = f"@{sender_name}" if sender_name else (cached.get("sender_name") or "Noma'lum")
            file_id = cached.get("file_id")
            is_from_user = (cached_sender == tracked_user_id) if tracked_user_id else False

            # 1) FOYDALANUVCHIGA YUBORISH (Agar suhbatdoshi o'chirgan bo'lsa yoki view-once media bo'lsa)
            if tracked_user_id and not is_from_user:
                media_info = f" ({fallback_media.upper()})" if media_type else ""
                user_del_msg = (
                    f"🗑 <b>Suhbatdoshingiz o'chirib yuborgan xabar saqlandi!</b>{media_info}\n\n"
                    f"👤 <b>Kimdan:</b> {html.escape(sender_str)}\n"
                    f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
                    f"▫️ <b>O'chirilgan ma'lumot:</b>\n"
                    f"<code>{html.escape(cached_text[:1500])}</code>"
                )
                try:
                    if media_type == "photo" and file_id:
                        await bot.send_photo(chat_id=tracked_user_id, photo=file_id, caption=safe_format_caption(user_del_msg), parse_mode="HTML")
                    elif media_type == "video" and file_id:
                        await bot.send_video(chat_id=tracked_user_id, video=file_id, caption=safe_format_caption(user_del_msg), parse_mode="HTML")
                    elif media_type == "animation" and file_id:
                        await bot.send_animation(chat_id=tracked_user_id, animation=file_id, caption=safe_format_caption(user_del_msg), parse_mode="HTML")
                    elif media_type == "voice" and file_id:
                        await bot.send_voice(chat_id=tracked_user_id, voice=file_id, caption=safe_format_caption(user_del_msg), parse_mode="HTML")
                    elif media_type == "video_note" and file_id:
                        await bot.send_message(chat_id=tracked_user_id, text=user_del_msg[:4096], parse_mode="HTML")
                        await bot.send_video_note(chat_id=tracked_user_id, video_note=file_id)
                    else:
                        await bot.send_message(chat_id=tracked_user_id, text=user_del_msg[:4096], parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Media yetkazib berishda xatolik, matn ko'rinishida yuborildi ({tracked_user_id}): {e}")
                    try:
                        await bot.send_message(chat_id=tracked_user_id, text=user_del_msg[:4096], parse_mode="HTML")
                    except Exception as e2:
                        logger.error(f"Foydalanuvchiga o'chirilgan xabarni yuborib bo'lmadi: {e2}")

            # 2) ADMINGA YUBORISH (Faqat chat adminning o'zi bilan bo'lmasa yoki test qilinayotgan bo'lsa)
            if not is_admin_chat or (cached_sender not in admin_ids):
                mode_tag = "🚨 <b>MAXSUS KUZATUV (O'CHIRILDI):</b>" if is_special else "🗑 <b>XABAR O'CHIRILDI:</b>"
                admin_header = (
                    f"{mode_tag}\n\n"
                    f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}\n"
                    f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
                    f"👤 <b>Kim o'chirdi:</b> {html.escape(sender_str)}"
                )

                for admin_id in admin_ids:
                    try:
                        if media_type == "photo" and file_id:
                            cap = safe_format_caption(admin_header, f"[O'chirilgan rasm]\n{cached_text}")
                            await bot.send_photo(chat_id=admin_id, photo=file_id, caption=cap, parse_mode="HTML")
                        elif media_type == "video" and file_id:
                            cap = safe_format_caption(admin_header, f"[O'chirilgan video]\n{cached_text}")
                            await bot.send_video(chat_id=admin_id, video=file_id, caption=cap, parse_mode="HTML")
                        elif media_type == "animation" and file_id:
                            cap = safe_format_caption(admin_header, f"[O'chirilgan GIF]\n{cached_text}")
                            await bot.send_animation(chat_id=admin_id, animation=file_id, caption=cap, parse_mode="HTML")
                        elif media_type == "voice" and file_id:
                            cap = safe_format_caption(admin_header, "🎤 O'chirilgan ovozli xabar")
                            await bot.send_voice(chat_id=admin_id, voice=file_id, caption=cap, parse_mode="HTML")
                        elif media_type == "video_note" and file_id:
                            await send_to_admin_safely(bot, admin_id, f"{admin_header}\n⭕️ <b>O'chirilgan dumaloq video:</b>")
                            await bot.send_video_note(chat_id=admin_id, video_note=file_id)
                        else:
                            full_admin_text = (
                                f"{admin_header}\n\n"
                                f"▫️ <b>O'chirilgan xabar:</b>\n"
                                f"<code>{html.escape(cached_text[:1500])}</code>"
                            )
                            await send_to_admin_safely(bot, admin_id, full_admin_text)
                    except Exception as e:
                        logger.error(f"Error forwarding deleted message to admin {admin_id}: {e}")

            # 3) SERVER XOTIRASINI TEJASH: Xabar Telegramga uzatilgach, keshdan o'chirib tashlaymiz!
            await db.delete_cached_message(event.chat.id, msg_id)

        else:
            # Keshda saqlanmagan xabar o'chirilganda
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
