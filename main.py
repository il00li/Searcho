#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Searo Telegram Bot
==================
بوت بحث/موارد مخصَّص للمصممين، يعتمد على Pixabay API ويشترط الاشتراك
في قناتي @crazys7 و @AWU87 قبل الاستخدام.

آخر تعديل: 2025-08-02
"""

import asyncio
import logging
import os
from functools import wraps

import aiohttp
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ────────────────────────────────
# 🎛️ الضبط
# ────────────────────────────────
TOKEN: str = os.getenv("BOT_TOKEN", "8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo")
PIXABAY_KEY: str = os.getenv("PIXABAY_KEY", "51444506-bffefcaf12816bd85a20222d1")
SUB_CHANNELS: list[str] = ["@crazys7", "@AWU87"]

# (اختياري) أرقام معرفات المشرفين لإتاحة أوامر خاصة
ADMINS: set[int] = {123456789}

# ────────────────────────────────
# 📝 إعداد السجلّات
# ────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ────────────────────────────────
# 🔒 أدوات الحماية والمساعدات
# ────────────────────────────────
async def is_user_subscribed(bot, user_id: int, channels: list[str]) -> bool:
    """
    يتحقق من أن المستخدم مشترك في جميع القنوات المطلوبة.

    Returns True إذا كان مشتركًا، وإلا False.
    """
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                return False
        except Exception as e:  # القناة قد تكون خاصة، أو تمت إزالة البوت منها
            logger.warning("تعذر التحقق من %s: %s", channel, e)
            return False
    return True


def admin_only(func):
    """
    ديكوريتر لتقييد تنفيذ الدوال على المشرفين فقط.
    """

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id in ADMINS:
            return await func(update, context, *args, **kwargs)
        await update.message.reply_text("🚫 هذا الأمر للمشرفين فقط.")
        return

    return wrapped


def build_main_keyboard() -> InlineKeyboardMarkup:
    """
    لوحة التحكُّم الرئيسية.
    يمكنك تغيير الأزرار بما يناسبك.
    """
    buttons = [
        [
            InlineKeyboardButton("🔍 بحث عن صور", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📈 إحصائياتي", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("ℹ️ مساعدة", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ────────────────────────────────
# 🚀 الأوامر والمعالجات
# ────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subscribed = await is_user_subscribed(context.bot, user_id, SUB_CHANNELS)

    if not subscribed:
        buttons = [
            [InlineKeyboardButton("🔗 اشترك في @crazys7", url="https://t.me/crazys7")],
            [InlineKeyboardButton("🔗 اشترك في @AWU87", url="https://t.me/AWU87")],
            [InlineKeyboardButton("✅ تحقّق مجددًا", callback_data="check_sub")],
        ]
        await update.message.reply_text(
            "⚠️ لا يمكنك استخدام البوت قبل الاشتراك في القنوات التالية:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await update.message.reply_text(
        "🎉 أهلاً بك في Searo Bot!\nاختر ما تحتاجه من القائمة 👇",
        reply_markup=build_main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Searo Bot – دليل الاستخدام*\n\n"
        "1. ابحث عن صور بكتابة أي كلمة بعد الأمر /search.\n"
        "2. البوت يستخدم Pixabay، وبالتالي الصور خاضعة لرخصتها.\n"
        "3. للإبلاغ عن مشكلة، راسل @crazys7.\n",
        parse_mode=ParseMode.MARKDOWN,
    )


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بحث عن صور عبر Pixabay وإرجاع النتائج بصورة مصغَّرة وروابط تحميل.
    """
    if not context.args:
        await update.message.reply_text("❔ مثال: `/search sunset`", parse_mode=ParseMode.MARKDOWN)
        return

    query = " ".join(context.args).strip()
    await update.message.reply_text(f"🔎 جاري البحث عن: *{query}* ...", parse_mode=ParseMode.MARKDOWN)

    url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={query}&image_type=photo&per_page=6"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بـ Pixabay.")
                return
            data = await resp.json()

    hits = data.get("hits", [])
    if not hits:
        await update.message.reply_text("🙁 لم أجد نتائج. جرّب كلمة أخرى.")
        return

    for hit in hits:
        caption = f"👤 {hit['user']} | 👍 {hit['likes']} | 📂 {hit['tags']}"
        await update.message.reply_photo(
            photo=hit["webformatURL"],
            caption=caption,
        )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    user_id = update.effective_user.id

    if data == "check_sub":
        subscribed = await is_user_subscribed(context.bot, user_id, SUB_CHANNELS)
        if subscribed:
            await query.edit_message_text("✅ تم التحقق من الاشتراك! مرحباً بك.")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="اختر ما تبحث عنه:",
                reply_markup=build_main_keyboard(),
            )
        else:
            await query.edit_message_text(
                "❌ لم يتم الاشتراك بعد.\nيرجى الاشتراك ثم الضغط على ✅ تحقّق مجددًا."
            )

    elif data == "stats":
        # مثال إحصائي بسيط
        await query.edit_message_text(
            f"📊 عدد الطلبات التي أرسلتها: *{context.user_data.get('requests', 0)}*",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "help":
        await help_command(update, context)

    else:
        await query.edit_message_text("🤔 خيار غير معروف.")


# ────────────────────────────────
# 👑 أوامر المشرفين
# ────────────────────────────────
@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    إرسال رسالة لجميع المستخدمين (يتطلب نظام قاعدة بيانات حقيقية).
    للاختصار، سنطبع فقط في السجل.
    """
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("✍️ اكتب الرسالة بعد الأمر.")
        return
    logger.info("Broadcast: %s", text)
    await update.message.reply_text("✅ تم إرسال البرودكاست (وهميًا).")


# ────────────────────────────────
# 🏁 التشغيل
# ────────────────────────────────
async def main():
    if TOKEN.startswith("YOUR_"):
        raise RuntimeError("❌ ضع قيمة TOKEN في متغير BOT_TOKEN قبل التشغيل.")

    app = ApplicationBuilder().token(TOKEN).build()

    # أوامر عامة
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_cmd))

    # أوامر المشرف
    app.add_handler(CommandHandler("broadcast", broadcast))

    # استجابات الأزرار
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # عداد بسيط لطلبات المستخدم
    async def count_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["requests"] = context.user_data.get("requests", 0) + 1

    app.add_handler(MessageHandler(filters.ALL, count_requests), group=1)

    logger.info("🤖 Searo Bot is running ...")
    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
