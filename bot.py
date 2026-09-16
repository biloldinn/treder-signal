import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import (
    Message, CallbackQuery, ChatMemberUpdated,
    InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
)

import db

SUPER_ADMINS = [6762465157, 6270526358]
log = logging.getLogger("vip_bot")

def is_super(uid): return uid in SUPER_ADMINS

def main_menu(uid):
    btns = [
        [InlineKeyboardButton(text="📡 Mening kanallarim", callback_data="my_channels")],
        [InlineKeyboardButton(text="📢 Reklama sozlash", callback_data="setup_ad")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="my_stats")],
    ]
    if is_super(uid):
        btns.append([InlineKeyboardButton(text="👑 Super admin", callback_data="super_panel")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")]])

router = Router()

@router.message(Command("start"))
async def cmd_start(msg: Message):
    await db.db_add_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    await db.db_clear_state(msg.from_user.id)
    
    if is_super(msg.from_user.id):
        await msg.answer(
            f"👋 Salom, <b>{msg.from_user.full_name}</b>!\n\n"
            f"📌 <b>Yangi tartib bo'yicha qanday ishlaydi:</b>\n"
            f"1️⃣ Botni kanalga <b>admin</b> qiling\n"
            f"2️⃣ Kanal sozlamasidan qo'shilishni <b>'Zayavka orqali'</b> qilib qo'ying\n"
            f"3️⃣ <b>📢 Reklama sozlash</b> orqali reklamangizni qo'shing\n"
            f"4️⃣ Kimdir zayavka tashlaganda bot (yoki o'zingiz) qabul qilgach, foydalanuvchiga reklama tashlanadi!\n\n"
            f"🆔 ID: <code>{msg.from_user.id}</code>",
            reply_markup=main_menu(msg.from_user.id)
        )
    else:
        await msg.answer(f"👋 Assalomu alaykum, <b>{msg.from_user.full_name}</b>!\n\nKanalimizga qo'shilish uchun zayavka tashlaganingizda, biz sizga sovg'a (reklama) yuboramiz. Botni bloklamang!")

@router.message(Command("id"))
async def cmd_id(msg: Message):
    await msg.answer(f"🆔 ID: <code>{msg.from_user.id}</code>\n💬 Chat: <code>{msg.chat.id}</code>")

@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot):
    chat = event.chat
    if chat.type not in (ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP): return
    new = event.new_chat_member.status
    old = event.old_chat_member.status
    if new in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER):
        owner = event.from_user.id if event.from_user else 0
        await db.db_add_channel(chat.id, chat.title or str(chat.id), owner)
        try:
            await bot.send_message(owner,
                f"✅ Bot <b>{chat.title}</b> kanaliga qo'shildi!\n\n"
                f"Endi <b>📢 Reklama sozlash</b> tugmasini bosing!",
                reply_markup=main_menu(owner))
        except Exception: pass
    elif old in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER) and new in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        await db.db_del_channel(chat.id)
        await db.db_delete_ad(chat.id)

async def send_ad(bot: Bot, user, chat):
    await db.db_add_user(user.id, user.username, user.full_name)
    ad = await db.db_get_ad(chat.id)
    if not ad or not ad["is_active"]: return
    
    # Faqat oxirgi 1 daqiqa ichida jo'natilmagan bo'lsa jo'natamiz (ikkita ketib qolishini oldini olish uchun)
    already_sent = await db.fetchval(
        "SELECT 1 FROM stats WHERE user_id=$1 AND channel_id=$2 AND CAST(created_at AS timestamp) > NOW() - INTERVAL '1 minute'", 
        user.id, chat.id
    )
    if already_sent: return

    mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
    txt = ad["text"].replace("{name}", mention).replace("{channel}", f"<b>{chat.title}</b>")
    btn_text = ad["button_text"] or "🎁 Bonusni olish"
    caption = f"🎉 {mention}, tabriklaymiz!\n\n{txt}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_text, url=ad["link"])]])

    # Faqat lichkaga yuborish (Kanalga tashlamaydi)
    try:
        if ad["photo_id"]:
            await bot.send_photo(user.id, ad["photo_id"], caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await bot.send_message(user.id, caption, reply_markup=kb, disable_web_page_preview=False)
        await db.db_log_stat(user.id, chat.id, "message_sent")
    except Exception: pass



@router.chat_join_request()
async def on_join_request(update: ChatJoinRequest, bot: Bot):
    ch = await db.db_get_channel(update.chat.id)
    # Avval reklamani tashlaymiz (zayavka tushgan zahoti!)
    await send_ad(bot, update.from_user, update.chat)
    
    # Keyin agar avto-qabul yoqilgan bo'lsa, qabul qilamiz
    if ch and ch.get("auto_approve"):
        try: await update.approve()
        except Exception: pass

@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    if event.new_chat_member.user.is_bot: return
    await send_ad(bot, event.new_chat_member.user, event.chat)

@router.callback_query(F.data == "back")
async def cb_back(cb: CallbackQuery):
    await db.db_clear_state(cb.from_user.id)
    await cb.message.edit_text("🏠 <b>Bosh menyu</b>", reply_markup=main_menu(cb.from_user.id))
    await cb.answer()

@router.callback_query(F.data == "my_channels")
async def cb_my_channels(cb: CallbackQuery):
    chs = await db.db_get_channels_by_owner(cb.from_user.id)
    if not chs:
        await cb.message.edit_text("📡 <b>Sizda hali kanallar yo'q.</b>", reply_markup=back_kb())
        return await cb.answer()
    text = "📡 <b>Sizning kanallaringiz:</b>\n\n"
    for ch in chs:
        ad = await db.db_get_ad(ch["channel_id"])
        st = "✅ Faol" if (ad and ad["is_active"]) else ("⛔ O'chirilgan" if ad else "⚠️ Sozlanmagan")
        sent = await db.db_stats_by_channel(ch["channel_id"])
        text += f"• <b>{ch['title']}</b>\n  🆔 <code>{ch['channel_id']}</code>\n  {st} | 📨 {sent} ta\n\n"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()

@router.callback_query(F.data == "setup_ad")
async def cb_setup_ad(cb: CallbackQuery):
    chs = await db.db_get_channels_by_owner(cb.from_user.id)
    if not chs:
        await cb.message.edit_text("⚠️ <b>Avval botni kanalga admin qiling!</b>", reply_markup=back_kb())
        return await cb.answer()
    rows = []
    for ch in chs:
        ad = await db.db_get_ad(ch["channel_id"])
        icon = "✅" if (ad and ad["is_active"]) else ("⛔" if ad else "⚠️")
        rows.append([InlineKeyboardButton(text=f"{icon} {ch['title'][:35]}", callback_data=f"manage_{ch['channel_id']}")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")])
    await cb.message.edit_text("📢 <b>Qaysi kanalni boshqarmoqchisiz?</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()

async def channel_manage_kb(ch_id):
    ad = await db.db_get_ad(ch_id)
    ch = await db.db_get_channel(ch_id)
    rows = []
    
    # Har doim chiqadigan tugma
    auto_text = "⛔ Zayavkani O'CHIRISH (Qo'lda)" if ch.get("auto_approve") else "✅ Zayavkani AVTO-QABUL QILISH"
    rows.append([InlineKeyboardButton(text=auto_text, callback_data=f"toggleauto_{ch_id}")])

    if ad:
        toggle_text = "⛔ Reklamani O'CHIRISH (OFF)" if ad["is_active"] else "✅ Reklamani YOQISH (ON)"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_{ch_id}")])
        rows.append([InlineKeyboardButton(text="👁 Reklamani ko'rish (Preview)", callback_data=f"preview_{ch_id}")])
        rows.append([InlineKeyboardButton(text="✏️ Tahrirlash (qayta sozlash)", callback_data=f"edit_{ch_id}")])
        rows.append([InlineKeyboardButton(text="🗑 Reklamani o'chirish", callback_data=f"deladq_{ch_id}")])
    else:
        rows.append([InlineKeyboardButton(text="➕ Yangi reklama yaratish", callback_data=f"edit_{ch_id}")])
    
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="setup_ad")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data.startswith("manage_"))
async def cb_manage_channel(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    ch = await db.db_get_channel(ch_id)
    if not ch: return await cb.answer("Kanal topilmadi", show_alert=True)
    if ch["owner_id"] != cb.from_user.id and not is_super(cb.from_user.id): return await cb.answer("Ruxsat yoq", show_alert=True)

    ad = await db.db_get_ad(ch_id)
    auto_appr = "✅ <b>Yoqilgan (Bot qabul qiladi)</b>" if ch.get("auto_approve") else "⛔ <b>O'chirilgan (Qo'lda)</b>"
    
    if ad:
        status = "✅ <b>Faol</b>" if ad["is_active"] else "⛔ <b>O'chirilgan</b>"
        has_photo = "🖼 Rasm bor" if ad["photo_id"] else "📝 Rasmsiz"
        sent = await db.db_stats_by_channel(ch_id)
        text = (
            f"📡 <b>{ch['title']}</b>\n"
            f"🤖 Avto-qabul: {auto_appr}\n"
            f"📋 <b>Reklama:</b>\n"
            f"📌 {status} | {has_photo}\n"
            f"📝 <i>{ad['text'][:120]}...</i>\n"
            f"🔘 Tugma: <b>{ad['button_text']}</b>\n"
            f"📨 Yuborilgan: {sent} ta"
        )
    else:
        text = f"📡 <b>{ch['title']}</b>\n🤖 Avto-qabul: {auto_appr}\n\n⚠️ <i>Reklama hali sozlanmagan.</i>"

    await cb.message.edit_text(text, reply_markup=await channel_manage_kb(ch_id))
    await cb.answer()

@router.callback_query(F.data.startswith("toggle_"))
async def cb_toggle(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    ad = await db.db_get_ad(ch_id)
    if not ad: return await cb.answer("Reklama topilmadi", show_alert=True)
    await db.db_toggle_ad(ch_id, not ad["is_active"])
    await cb.answer("Holat o'zgardi!", show_alert=True)
    cb.data = f"manage_{ch_id}"
    await cb_manage_channel(cb)

@router.callback_query(F.data.startswith("toggleauto_"))
async def cb_toggleauto(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    ch = await db.db_get_channel(ch_id)
    if not ch: return await cb.answer("Kanal topilmadi", show_alert=True)
    await db.db_toggle_auto_approve(ch_id, not ch.get("auto_approve"))
    await cb.answer("Avto-qabul qilish o'zgardi!", show_alert=True)
    cb.data = f"manage_{ch_id}"
    await cb_manage_channel(cb)

@router.callback_query(F.data.startswith("preview_"))
async def cb_preview(cb: CallbackQuery, bot: Bot):
    ch_id = int(cb.data.split("_", 1)[1])
    ad = await db.db_get_ad(ch_id)
    ch = await db.db_get_channel(ch_id)
    if not ad: return await cb.answer("Xato", show_alert=True)
    
    mention = f'<a href="tg://user?id={cb.from_user.id}">{cb.from_user.full_name}</a>'
    txt = ad["text"].replace("{name}", mention).replace("{channel}", f"<b>{ch['title']}</b>")
    caption = f"🎉 {mention}, tabriklaymiz!\n\n{txt}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=ad["button_text"], url=ad["link"])]])

    await cb.answer()
    if ad["photo_id"]: await bot.send_photo(cb.from_user.id, ad["photo_id"], caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
    else: await bot.send_message(cb.from_user.id, caption, reply_markup=kb)

@router.callback_query(F.data.startswith("deladq_"))
async def cb_delete_confirm(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data=f"delyes_{ch_id}"), InlineKeyboardButton(text="❌ Yo'q", callback_data=f"manage_{ch_id}")]])
    await cb.message.edit_text("O'chirishni tasdiqlaysizmi?", reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data.startswith("delyes_"))
async def cb_delete_yes(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    await db.db_delete_ad(ch_id)
    await cb.answer("O'chirildi!", show_alert=True)
    cb.data = f"manage_{ch_id}"
    await cb_manage_channel(cb)

@router.callback_query(F.data.startswith("edit_"))
async def cb_edit_ad(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    await db.db_set_state(cb.from_user.id, "wait_photo_text", ch_id)
    await cb.message.edit_text("1️⃣ Rasm va matn yuboring (caption)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"manage_{ch_id}")]]))
    await cb.answer()

@router.callback_query(F.data == "my_stats")
async def cb_my_stats(cb: CallbackQuery):
    chs = await db.db_get_channels_by_owner(cb.from_user.id)
    if not chs: return await cb.message.edit_text("📊 <i>Kanallar yoq.</i>", reply_markup=back_kb())
    text = "📊 <b>Statistika</b>\n\n"
    total = 0
    for ch in chs:
        s = await db.db_stats_by_channel(ch["channel_id"]); total += s
        text += f"📡 <b>{ch['title']}</b> — <b>{s}</b> ta\n"
    text += f"\n📨 Jami: <b>{total}</b> ta"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()

@router.callback_query(F.data == "super_panel")
async def cb_super(cb: CallbackQuery):
    if not is_super(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    users = await db.db_users_count(); chs = await db.db_get_all_channels(); total = await db.db_total_sent()
    text = f"👑 <b>Super Admin</b>\n\n👥 {users} | 📡 {len(chs)} | 📨 {total}\n\n"
    for ch in chs:
        ad = await db.db_get_ad(ch["channel_id"])
        ic = "✅" if (ad and ad["is_active"]) else "❌"
        text += f"• {ic} <b>{ch['title']}</b> | 👤 <code>{ch['owner_id']}</code>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📣 Hammaga xabar", callback_data="broadcast")], [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data == "broadcast")
async def cb_broadcast(cb: CallbackQuery):
    if not is_super(cb.from_user.id): return await cb.answer("⛔", show_alert=True)
    await db.db_set_state(cb.from_user.id, "broadcast", 0)
    await cb.message.edit_text("✍️ Xabar kiriting:", reply_markup=back_kb())
    await cb.answer()

@router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm(cb: CallbackQuery, bot: Bot):
    ch_id = int(cb.data.split("_", 1)[1])
    st = await db.db_get_state(cb.from_user.id)
    if not st or st.get("step") != "waiting_confirm": return await cb.answer("Vaqt tugadi", show_alert=True)
    await db.db_set_ad(ch_id, st["text"], st["link"], st["button_text"], st.get("photo_id"))
    await db.db_clear_state(cb.from_user.id)
    await bot.send_message(cb.from_user.id, "✅ Reklama saqlandi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ Boshqaruv", callback_data=f"manage_{ch_id}")], [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back")]]))
    await cb.answer()

@router.callback_query(F.data.startswith("cancel_"))
async def cb_cancel(cb: CallbackQuery):
    ch_id = int(cb.data.split("_", 1)[1])
    await db.db_clear_state(cb.from_user.id)
    cb.data = f"manage_{ch_id}"
    await cb_manage_channel(cb)

@router.message(F.photo | (F.text & ~F.text.startswith("/")))
async def handle_input(msg: Message, bot: Bot):
    st = await db.db_get_state(msg.from_user.id)
    if not st: return
    step = st["step"]

    if step == "wait_photo_text":
        photo_id = None; text = ""
        if msg.photo: photo_id = msg.photo[-1].file_id; text = msg.caption or ""
        elif msg.text: photo_id = None; text = msg.text
        else: return
        await db.db_set_state(msg.from_user.id, "wait_button_text", st["channel_id"], photo_id, text)
        await msg.answer("2️⃣ Tugma nomini yozing")
        return

    if step == "wait_button_text":
        button_text = msg.text.strip()
        await db.db_set_state(msg.from_user.id, "wait_link", st["channel_id"], st.get("photo_id"), st.get("text"), button_text)
        await msg.answer("3️⃣ Reklama ssilkasini yuboring (Masalan: https://t.me/...)")
        return

    if step == "wait_link":
        if not msg.text.startswith("http"): return await msg.answer("Link https:// bilan boshlanishi kerak!")
        link = msg.text.strip()
        await db.db_set_state(msg.from_user.id, "waiting_confirm", st["channel_id"], st.get("photo_id"), st.get("text"), st.get("button_text"), link)
        st = await db.db_get_state(msg.from_user.id)
        ch_id = st["channel_id"]
        ch = await db.db_get_channel(ch_id)
        title = ch["title"] if ch else str(ch_id)
        mention = f'<a href="tg://user?id={msg.from_user.id}">{msg.from_user.full_name}</a>'
        txt = st["text"].replace("{name}", mention).replace("{channel}", f"<b>{title}</b>")
        caption = f"🎉 {mention}, tabriklaymiz!\n\n{txt}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=st["button_text"], url=st["link"])]])
        
        if st.get("photo_id"): await msg.answer_photo(st["photo_id"], caption=caption, reply_markup=kb)
        else: await msg.answer(caption, reply_markup=kb)
        await msg.answer("Tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{ch_id}"), InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{ch_id}")]]))
        return

    if step == "broadcast":
        if not is_super(msg.from_user.id) or not msg.text: return
        users = await db.db_all_users()
        sent = 0
        for uid in users:
            try: await bot.send_message(uid, msg.text); sent += 1
            except: pass
            await asyncio.sleep(0.05)
        await db.db_clear_state(msg.from_user.id)
        await msg.answer(f"✅ Yuborildi: {sent}", reply_markup=main_menu(msg.from_user.id))
