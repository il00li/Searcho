import os
import logging
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables (set these on Render)
TOKEN               = os.environ["8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo "]
ADMIN_ID            = int(os.environ["7251748706"])
PIXABAY_API_KEY     = os.environ["51444506-bffefcaf12816bd85a20222d1"]
REQUIRED_CHANNELS   = os.environ.get("REQUIRED_CHANNELS", "@crazys7,@AWU87").split(",")
WEBHOOK_URL         = os.environ.get("https://searcho-1.onrender.com")  # e.g. https://<your-render-app>.onrender.com
PORT                = int(os.environ.get("PORT", "8443"))


async def check_subscription(user_id: int, bot) -> bool:
    """
    تأكد أن المستخدم مشترك في جميع القنوات المطلوبة
    """
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start handler: 
    - يمسح بيانات الجلسة السابقة
    - يتحقق من الاشتراك ويدعو للتحقق إذا لزم الأمر
    """
    context.user_data.clear()
    user_id = update.effective_user.id

    if not await check_subscription(user_id, context.bot):
        text = "للوصول للبوت يجب الاشتراك في القنوات التالية:\n" + "\n".join(
            f"- {ch}" for ch in REQUIRED_CHANNELS
        )
        keyboard = []
        for ch in REQUIRED_CHANNELS:
            keyboard.append(
                [InlineKeyboardButton(ch, url=f"https://t.me/{ch.lstrip('@')}")]
            )
        keyboard.append([InlineKeyboardButton("تحقق | Check", callback_data="verify")])

        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # مشترك فعلاً → أظهر القائمة الرئيسية
        await show_main_menu(update.effective_chat.id, context.bot)


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data="verify": إعادة التحقق من الاشتراك
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if await check_subscription(user_id, context.bot):
        # تحويل الرسالة الحالية ثم إظهار القائمة الرئيسية
        await query.edit_message_text("تم التحقق! اختر خياراً:")
        await show_main_menu(query.message.chat.id, context.bot)
    else:
        await query.answer("لا زلت غير مشترك في جميع القنوات.", show_alert=True)


async def show_main_menu(chat_id: int, bot):
    """
    يعرض زري 'بدء البحث' و 'انواع البحث'
    """
    keyboard = [
        [InlineKeyboardButton("بدء البحث 👁", callback_data="start_search")],
        [InlineKeyboardButton("انواع البحث🧸", callback_data="choose_type")],
    ]
    await bot.send_message(
        chat_id=chat_id,
        text="اختر خياراً:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def choose_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data="choose_type": عرض أنواع البحث وتظليل المحدد حالياً
    """
    query = update.callback_query
    await query.answer()

    current = context.user_data.get("search_type")
    types = {
        "illustration": "Illustration",
        "photo": "photos",
        "vector": "vector",
        "video": "video",
    }

    keyboard = []
    for key, name in types.items():
        label = f"{name} {'🧸' if current == key else ''}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"set_type_{key}")])

    await query.edit_message_text(
        "اختر نوع البحث:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data="set_type_{type}": حفظ نوع البحث وإرجاع القائمة الرئيسية
    """
    query = update.callback_query
    await query.answer()

    chosen = query.data.split("_")[-1]
    context.user_data["search_type"] = chosen

    await query.edit_message_text(f"تم اختيار نوع البحث: {chosen}")
    await show_main_menu(query.message.chat.id, context.bot)


async def start_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data="start_search": بدء جلسة البحث (يطلب كلمة البحث)
    """
    query = update.callback_query
    await query.answer()

    if "search_type" not in context.user_data:
        context.user_data["search_type"] = "photo"  # افتراضي

    context.user_data["awaiting_query"] = True
    await query.edit_message_text("أرسل كلمة البحث:")


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بعد إرسال كلمة البحث: استدعاء Pixabay API وعرض أول نتيجة مع أزرار التنقل
    """
    if not context.user_data.get("awaiting_query"):
        return

    query_text = update.message.text.strip()
    context.user_data["awaiting_query"] = False

    stype = context.user_data.get("search_type", "photo")
    if stype == "video":
        url = (
            f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}"
            f"&q={query_text}"
        )
    else:
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_API_KEY}"
            f"&q={query_text}&image_type={stype}"
        )

    resp = requests.get(url)
    data = resp.json()
    hits = data.get("hits", [])

    if not hits:
        await update.message.reply_text("لم يتم العثور على نتائج.")
        return

    context.user_data["results"] = hits
    context.user_data["index"] = 0

    await send_result(update.message.chat.id, context)


async def send_result(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    يعرض النتيجة الحالية (صورة أو رابط فيديو) مع أزرار Prev/Next و Choose
    """
    ud = context.user_data
    idx = ud["index"]
    hits = ud["results"]
    result = hits[idx]

    # حذف الرسائل القديمة إن وجدت
    for key in ("result_message_id", "nav_message_id"):
        if key in ud:
            try:
                await context.bot.delete_message(chat_id, ud[key])
            except:
                pass

    # عرض الوسيط
    if ud["search_type"] == "video":
        video_url = result["videos"]["medium"]["url"]
        msg = await context.bot.send_message(chat_id, text=video_url)
    else:
        img_url = result.get("largeImageURL")
        msg = await context.bot.send_photo(chat_id, photo=img_url)

    ud["result_message_id"] = msg.message_id

    # أزرار التنقل والاختيار
    kb_nav = []
    if idx > 0:
        kb_nav.append(InlineKeyboardButton("⬅️", callback_data="nav_prev"))
    if idx < len(hits) - 1:
        kb_nav.append(InlineKeyboardButton("➡️", callback_data="nav_next"))

    keyboard = [
        kb_nav,
        [InlineKeyboardButton("اختيار🔒", callback_data="choose")],
    ]

    nav_msg = await context.bot.send_message(
        chat_id,
        text=f"نتيجة {idx + 1} من {len(hits)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    ud["nav_message_id"] = nav_msg.message_id


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data in [nav_prev, nav_next]: تحديث الفهرس وإعادة العرض
    """
    query = update.callback_query
    await query.answer()

    if "index" not in context.user_data:
        return

    if query.data == "nav_prev":
        context.user_data["index"] = max(0, context.user_data["index"] - 1)
    else:
        context.user_data["index"] = min(
            len(context.user_data["results"]) - 1, context.user_data["index"] + 1
        )

    await send_result(query.message.chat.id, context)


async def choose_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    callback_data="choose": المستخدم يختار النتيجة الحالية نهائياً
    """
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    idx = ud["index"]
    result = ud["results"][idx]

    # حذف الرسائل المؤقتة
    for key in ("result_message_id", "nav_message_id"):
        if key in ud:
            try:
                await context.bot.delete_message(query.message.chat.id, ud[key])
            except:
                pass

    # إرسال النتيجة النهائية
    if ud["search_type"] == "video":
        url = result["videos"]["medium"]["url"]
        await context.bot.send_message(query.message.chat.id, text=f"تم اختيار الفيديو:\n{url}")
    else:
        img_url = result.get("largeImageURL")
        await context.bot.send_photo(
            query.message.chat.id, photo=img_url, caption="تم اختيار الصورة"
        )

    # مسح حالة البحث للسماح ببدء جديد عبر /start
    for key in ("results", "index", "result_message_id", "nav_message_id", "awaiting_query"):
        ud.pop(key, None)


def main():
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()

    # تسجيل ال handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(choose_type_callback, pattern="^choose_type$"))
    app.add_handler(CallbackQueryHandler(set_type_callback, pattern="^set_type_"))
    app.add_handler(CallbackQueryHandler(start_search_callback, pattern="^start_search$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query))
    app.add_handler(CallbackQueryHandler(nav_callback, pattern="^nav_"))
    app.add_handler(CallbackQueryHandler(choose_callback, pattern="^choose$"))

    # إعداد Webhook أو Polling بناءً على وجود WEBHOOK_URL
    if WEBHOOK_URL:
        # يضبط Webhook تلقائياً عند الانطلاق
        app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
        app.run_webhook(
            listen="0.0.0.0", port=PORT, webhook_path=TOKEN
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
