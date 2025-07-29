import os
import requests
from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
)
from dotenv import load_dotenv

# 1. تحميل الإعدادات من .env
load_dotenv()
BOT_TOKEN       = os.getenv("8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo ")
ADMIN_ID        = int(os.getenv("7251748706", 0))
PIXABAY_API_KEY = os.getenv("51444506-bffefcaf12816bd85a20222d1 ")
CHANNELS        = ["@crazys7", "@AWU87"]

if not BOT_TOKEN or not PIXABAY_API_KEY:
    raise RuntimeError("BOT_TOKEN أو PIXABAY_API_KEY مفقود في المتغيرات البيئية")

# 2. تهيئة البوت والـ Dispatcher
updater    = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# 3. بناء لوحات الأزرار
def build_channels_keyboard():
    btns = [
        InlineKeyboardButton(text=ch, url=f"https://t.me/{ch.lstrip('@')}")
        for ch in CHANNELS
    ]
    btns.append(InlineKeyboardButton(text="تحقق | Check", callback_data="check_sub"))
    return InlineKeyboardMarkup([btns[:2], btns[2:]])

def build_main_keyboard(search_type=None):
    type_label = f" انواع البحث 🧸 ({search_type})" if search_type else " انواع البحث 🧸"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="بدء البحث 👁", callback_data="start_search"),
            InlineKeyboardButton(text=type_label, callback_data="choose_type"),
        ]
    ])

def build_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="photos 🖼️",      callback_data="type:photos"),
            InlineKeyboardButton(text="illustration 🎨", callback_data="type:illustration"),
        ],
        [
            InlineKeyboardButton(text="vector 📐",       callback_data="type:vector"),
            InlineKeyboardButton(text="video 🎬",        callback_data="type:video"),
        ],
    ])

def build_nav_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️", callback_data="nav:prev"),
            InlineKeyboardButton("➡️", callback_data="nav:next"),
        ],
        [InlineKeyboardButton("اختيار🔒", callback_data="select")],
    ])

# 4. /start — عرض القنوات مع زر “تحقق”
def start(update: Update, context):
    context.user_data.clear()
    update.message.reply_text(
        text="📌 للاشتراك الإجباري في القنوات التالية ثم اضغط تحقق:",
        reply_markup=build_channels_keyboard()
    )
dispatcher.add_handler(CommandHandler("start", start))


# 5. التحقق من اشتراك المستخدم
def check_subscription(user_id):
    for ch in CHANNELS:
        try:
            member = updater.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ("member", "creator", "administrator"):
                return False
        except:
            return False
    return True

def check_sub_callback(update: Update, context):
    query = update.callback_query
    user  = query.from_user
    if check_subscription(user.id):
        context.user_data["verified"]    = True
        context.user_data["search_type"] = "photos"
        query.answer("تم التحقق ✅")
        query.edit_message_text(
            text="تم التحقق! يمكنك الآن البدء بالبحث أو اختيار النوع:",
            reply_markup=build_main_keyboard("photos")
        )
    else:
        query.answer("يرجى الاشتراك في جميع القنوات أولاً 🔔", show_alert=True)
dispatcher.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))


# 6. اختيار نوع البحث
def choose_type_callback(update: Update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_reply_markup(reply_markup=build_type_keyboard())
dispatcher.add_handler(CallbackQueryHandler(choose_type_callback, pattern="^choose_type$"))

def set_type_callback(update: Update, context):
    query = update.callback_query
    _, t = query.data.split(":")
    context.user_data["search_type"] = t
    query.answer(f"تم اختيار النوع: {t}")
    query.edit_message_text(
        text=f"نوع البحث الحالي: {t}\nيمكنك البدء بالبحث أو تغيير النوع:",
        reply_markup=build_main_keyboard(t)
    )
dispatcher.add_handler(CallbackQueryHandler(set_type_callback, pattern="^type:"))


# 7. بدء استقبال كلمة البحث
def start_search_callback(update: Update, context):
    query = update.callback_query
    if not context.user_data.get("verified"):
        return query.answer("يرجى التحقق أولاً", show_alert=True)
    context.user_data["awaiting_query"] = True
    query.answer()
    query.edit_message_text(text="أرسل كلمة البحث الآن:")
dispatcher.add_handler(CallbackQueryHandler(start_search_callback, pattern="^start_search$"))


# 8. التعامل مع كلمة البحث وإرسال النتائج
def search_pixabay(q, search_type):
    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": q,
        "image_type": "all" if search_type == "photos" else search_type,
        "per_page": 10,
    }
    data = requests.get(url, params=params).json()
    return data.get("hits", [])

def handle_message(update: Update, context):
    if not context.user_data.get("awaiting_query"):
        return
    query_text = update.message.text
    hits = search_pixabay(query_text, context.user_data["search_type"])
    if not hits:
        return update.message.reply_text("لا توجد نتائج، حاول كلمة أخرى.")
    context.user_data["results"] = hits
    context.user_data["index"]   = 0
    context.user_data["awaiting_query"] = False
    send_result(update, context, edit=False)
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))


# 9. عرض نتيجة واحدة مع أزرار التنقل والاختيار
def send_result(update_or_query, context, edit=False):
    idx     = context.user_data["index"]
    item    = context.user_data["results"][idx]
    chat_id = update_or_query.effective_chat.id
    kb      = build_nav_keyboard()

    if context.user_data["search_type"] == "video":
        media_url = item["videos"]["medium"]["url"]
        if edit:
            context.bot.edit_message_media(
                media=InputMediaVideo(media_url),
                chat_id=chat_id,
                message_id=update_or_query.callback_query.message.message_id,
                reply_markup=kb,
            )
        else:
            context.bot.send_video(chat_id=chat_id, video=media_url, reply_markup=kb)

    else:
        media_url = item.get("webformatURL") or item.get("previewURL")
        if edit:
            context.bot.edit_message_media(
                media=InputMediaPhoto(media_url),
                chat_id=chat_id,
                message_id=update_or_query.callback_query.message.message_id,
                reply_markup=kb,
            )
        else:
            context.bot.send_photo(chat_id=chat_id, photo=media_url, reply_markup=kb)


# 10. التنقل بين النتائج
def nav_callback(update: Update, context):
    query     = update.callback_query
    _, action = query.data.split(":")
    idx       = context.user_data["index"]
    max_idx   = len(context.user_data["results"]) - 1

    if action == "next":
        idx = min(idx + 1, max_idx)
    else:
        idx = max(idx - 1, 0)

    context.user_data["index"] = idx
    query.answer()
    send_result(query, context, edit=True)
dispatcher.add_handler(CallbackQueryHandler(nav_callback, pattern="^nav:"))


# 11. اختيار النتيجة والإغلاق
def select_callback(update: Update, context):
    query = update.callback_query
    query.answer("تم الإختيار 🔒")
    query.edit_message_reply_markup(reply_markup=None)
    context.user_data.clear()
dispatcher.add_handler(CallbackQueryHandler(select_callback, pattern="^select$"))


# 12. تشغيل البوت
if __name__ == "__main__":
    updater.start_polling()
    updater.idle()
