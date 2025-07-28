# bot.py

"""
Environment Variables (set these before running):

BOT_TOKEN=8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo
PIXABAY_API_KEY=51444506-bffefcaf12816bd85a20222d1
ADMIN_ID=7251748706
CHANNELS=@crazys7,@AWU87

Requirements (save as requirements.txt or install manually):

python-telegram-bot==13.15
requests
python-dotenv
"""

import os
from dotenv import load_dotenv
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext
)

# Load .env if present
load_dotenv()

# Environment variables
BOT_TOKEN       = os.getenv("BOT_TOKEN")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
ADMIN_ID        = int(os.getenv("ADMIN_ID", "0"))
CHANNELS        = os.getenv("CHANNELS", "").split(",")

# Pixabay endpoints
PIXABAY_IMG_URL   = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/videos/"

# Supported search types
SEARCH_TYPES = ["illustration", "photo", "vector", "video"]

# ----- Utilities: Pixabay API calls -----
def fetch_assets(query: str, media_type: str, page: int = 1):
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "page": page,
        "per_page": 100
    }
    if media_type == "video":
        resp = requests.get(PIXABAY_VIDEO_URL, params=params).json()
        return resp.get("hits", [])
    if media_type in ("vector", "illustration", "photo"):
        if media_type != "photo":
            params["image_type"] = media_type
        resp = requests.get(PIXABAY_IMG_URL, params=params).json()
        return resp.get("hits", [])
    return []

# ----- Subscription check -----
def check_subscription(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    bot = context.bot
    for ch in CHANNELS:
        member = bot.get_chat_member(chat_id=ch, user_id=user_id)
        if member.status in ("left", "kicked"):
            return False
    return True

def prompt_subscription():
    buttons = [
        [InlineKeyboardButton(ch, url=f"https://t.me/{ch.strip('@')}")]
        for ch in CHANNELS
    ]
    buttons.append([InlineKeyboardButton("تحقق | Check", callback_data="verify_subscription")])
    return InlineKeyboardMarkup(buttons)

def verify_subscription(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if check_subscription(update, context):
        query.message.delete()
        start(update, context)
    else:
        query.message.reply_text(
            "لا تزال غير مشترك. الرجاء الاشتراك أولاً:", 
            reply_markup=prompt_subscription()
        )

# ----- /start handler -----
def start(update: Update, context: CallbackContext):
    # if called via command
    if update.message:
        msg = update.message
    else:
        msg = update.callback_query.message

    if not check_subscription(update, context):
        msg.reply_text(
            "يرجى الاشتراك أولاً بالقنوات التالية:", 
            reply_markup=prompt_subscription()
        )
        return

    # reset context
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("بدء البحث 👁", callback_data="begin_search")],
        [InlineKeyboardButton("أنواع البحث 🧸", callback_data="choose_type")]
    ]
    msg.reply_text(
        "مرحباً! اختر خياراً للمتابعة:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----- Choose search type -----
def choose_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    current = context.user_data.get("search_type", SEARCH_TYPES[0])
    keyboard = []
    for t in SEARCH_TYPES:
        mark = "🧸" if t == current else ""
        keyboard.append([InlineKeyboardButton(f"{t} {mark}", callback_data=f"type_{t}")])
    query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

def set_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    selection = query.data.split("_", 1)[1]
    context.user_data["search_type"] = selection
    query.edit_message_text(f"تم اختيار نوع البحث: {selection}")

# ----- Begin and receive search -----
def begin_search(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.message.reply_text("أرسل كلمة البحث:")
    return

def receive_query(update: Update, context: CallbackContext):
    text = update.message.text
    mtype = context.user_data.get("search_type", "photo")
    results = fetch_assets(text, mtype)
    if not results:
        update.message.reply_text("لم يتم العثور على نتائج. حاول كلمة أخرى.")
        return
    context.user_data["results"] = results
    context.user_data["index"]   = 0
    send_result(update, context)

# ----- Pagination and selection -----
def send_result(update: Update, context: CallbackContext):
    idx = context.user_data["index"]
    item = context.user_data["results"][idx]
    if "videos" in item:
        media_url = item["videos"]["medium"]["url"]
        caption   = item.get("tags", "")
        send = context.bot.send_video
        kwargs = {"video": media_url, "caption": caption}
    else:
        media_url = item.get("webformatURL")
        caption   = item.get("tags", "")
        send = context.bot.send_photo
        kwargs = {"photo": media_url, "caption": caption}

    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data="prev"),
            InlineKeyboardButton("➡️", callback_data="next")
        ],
        [InlineKeyboardButton("اختيار🔒", callback_data="select")]
    ]
    send(
        chat_id=update.effective_chat.id,
        reply_markup=InlineKeyboardMarkup(keyboard),
        **kwargs
    )

def paginate(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "next":
        context.user_data["index"] = min(
            context.user_data["index"] + 1,
            len(context.user_data["results"]) - 1
        )
    else:
        context.user_data["index"] = max(context.user_data["index"] - 1, 0)
    query.message.delete()
    send_result(update, context)

def select_item(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer("تم الاختيار!")
    item = context.user_data["results"][context.user_data["index"]]
    url  = (
        item["videos"]["medium"]["url"]
        if "videos" in item
        else item.get("webformatURL")
    )
    # remove buttons
    context.bot.edit_message_reply_markup(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        reply_markup=None
    )
    context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"هذا هو الرابط: {url}"
    )

# ----- Main -----
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Commands
    dp.add_handler(CommandHandler("start", start))

    # Subscription
    dp.add_handler(CallbackQueryHandler(verify_subscription, pattern="^verify_subscription$"))

    # Search flow
    dp.add_handler(CallbackQueryHandler(choose_type, pattern="^choose_type$"))
    dp.add_handler(CallbackQueryHandler(set_type,    pattern="^type_"))
    dp.add_handler(CallbackQueryHandler(begin_search, pattern="^begin_search$"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_query))

    # Pagination & select
    dp.add_handler(CallbackQueryHandler(paginate,    pattern="^(next|prev)$"))
    dp.add_handler(CallbackQueryHandler(select_item, pattern="^select$"))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
