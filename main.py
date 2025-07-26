import os
import json
import io
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo
)
from telegram.ext import (
    Updater,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)

CONFIG_PATH = 'config.json'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = {
            "banned": {},                # محظورون: {user_id: username}
            "channels": ["@crazys7"],
            "users": [],                 # كافة المستخدمين
            "searches": 0                # عدد عمليات البحث
        }
        save_config(cfg)
    else:
        with open(CONFIG_PATH, 'r') as f:
            cfg = json.load(f)
    return cfg

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, ensure_ascii=False)

config = load_config()

BOT_TOKEN       = '8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo'
PIXABAY_API_KEY = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_ID        = 7251748706

SUBSCRIBE_ART = (
    "(•_•)\n"
    "<)   )╯\n"
    " /   \\\n"
    "🎧 | اشترك في القنوات أولاً:"
)
READY_ART = (
    "(⊙_☉)\n"
    " /|\\\n"
    " / \\\n"
    "هل تريد بدء بحث؟!"
)

SEARCH_TYPES = [
    ('illustration', 'Illustration'),
    ('photo',        'Photos'),
    ('video',        'Video'),
    ('gif',          'GIF')
]

# Helpers

def is_banned(user_id):
    return str(user_id) in config['banned']

def add_user(user_id):
    if user_id not in config['users']:
        config['users'].append(user_id)
        save_config(config)

def is_subscribed(user_id, bot):
    for ch in config['channels']:
        try:
            status = bot.get_chat_member(chat_id=ch, user_id=user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def download_file(url):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        bio = io.BytesIO(r.content)
        bio.name = url.split("/")[-1]
        return bio
    return None

# -- Inline Menus --

def show_main_menu(chat_id, bot, is_admin=False):
    btns = [
        [InlineKeyboardButton("بدء البحث 🎧", callback_data='start_search')],
        [InlineKeyboardButton("نوع البحث 💐", callback_data='search_type')]
    ]
    if is_admin:
        btns.append([InlineKeyboardButton("لوحة التحكم 🛠️", callback_data='admin_panel')])
    bot.send_message(chat_id, READY_ART, reply_markup=InlineKeyboardMarkup(btns))

def show_search_types(query):
    sel = query._bot_data.setdefault(query.from_user.id, {}).get('search_type', '')
    btns = []
    for dtype, label in SEARCH_TYPES:
        mark = '👻' if sel == dtype else ''
        btns.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"type_{dtype}")])
    btns.append([InlineKeyboardButton("رجوع 🏠", callback_data='main_menu')])
    query.edit_message_text("💐 اختر نوع البحث:", reply_markup=InlineKeyboardMarkup(btns))

def show_admin_panel(query):
    btns = [
        [InlineKeyboardButton("حظر مستخدم 🚫",    callback_data='admin_ban')],
        [InlineKeyboardButton("رفع حظر ✅",       callback_data='admin_unban')],
        [InlineKeyboardButton("تعيين قناة 📢",   callback_data='admin_set_channel')],
        [InlineKeyboardButton("إلغاء قناة ❎",    callback_data='admin_unset_channel')],
        [InlineKeyboardButton("إحصائيات 📊",      callback_data='admin_stats')],
        [InlineKeyboardButton("إرسال إشعار 📣",   callback_data='admin_notify')],
        [InlineKeyboardButton("رجوع 🏠",          callback_data='main_menu')]
    ]
    query.edit_message_text("🛠️ لوحة التحكم:", reply_markup=InlineKeyboardMarkup(btns))

# -- Handlers --

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if is_banned(user_id):
        update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
        return

    add_user(user_id)
    bot = context.bot

    if not is_subscribed(user_id, bot):
        btns = [[InlineKeyboardButton(ch, url=f"https://t.me/{ch.strip('@')}")]
                for ch in config['channels']]
        btns.append([InlineKeyboardButton("تحقق | Verify", callback_data='verify')])
        update.message.reply_text(SUBSCRIBE_ART, reply_markup=InlineKeyboardMarkup(btns))
    else:
        show_main_menu(update.message.chat_id, bot, is_admin=(user_id==ADMIN_ID))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    query.answer()

    if is_banned(user_id):
        query.edit_message_text("🚫 أنت محظور.")
        return

    # Verify subscription
    if data == 'verify':
        if is_subscribed(user_id, context.bot):
            start(update, context)
        else:
            query.edit_message_text("⚠️ لم تشترك بعد.")
        return

    # Main menu
    if data == 'main_menu':
        show_main_menu(query.message.chat_id, context.bot, is_admin=(user_id==ADMIN_ID))
        return

    # Search flow
    if data == 'start_search':
        context.user_data['awaiting'] = True
        query.edit_message_text("✏️ أرسل كلمات البحث:")
        return

    if data == 'search_type':
        show_search_types(query)
        return

    if data.startswith('type_'):
        dtype = data.split('_',1)[1]
        context.user_data['search_type'] = dtype
        show_search_types(query)
        return

    # Navigation in results
    if data in ['next','prev','select']:
        handle_navigation(query, context, data)
        return

    # Admin panel
    if user_id == ADMIN_ID and data == 'admin_panel':
        show_admin_panel(query)
        return

    # Admin actions
    if user_id == ADMIN_ID and data.startswith('admin_'):
        action = data.split('_',1)[1]
        context.user_data['admin_action'] = action
        prompts = {
            'ban':        "✏️ أرسل: user_id username",
            'unban':      "✏️ أرسل: user_id",
            'set_channel':   "✏️ أرسل: @channel_username",
            'unset_channel': "✏️ أرسل: @channel_username",
            'notify':     "✏️ أرسل نص الإشعار:"
        }
        query.edit_message_text(prompts[action])
        return

def text_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Admin text actions
    action = context.user_data.get('admin_action')
    if user_id == ADMIN_ID and action:
        cfg = config
        if action == 'ban':
            parts = text.split(None, 1)
            if len(parts) == 2:
                uid, uname = parts
                cfg['banned'][uid] = uname
                save_config(cfg)
                update.message.reply_text(f"🚫 تم حظر {uname}")
        elif action == 'unban':
            uid = text
            if uid in cfg['banned']:
                name = cfg['banned'].pop(uid)
                save_config(cfg)
                update.message.reply_text(f"✅ تم رفع الحظر عن {name}")
        elif action == 'set_channel':
            ch = text
            if ch not in cfg['channels']:
                cfg['channels'].append(ch)
                save_config(cfg)
                update.message.reply_text(f"✅ تمت إضافة القناة {ch}")
        elif action == 'unset_channel':
            ch = text
            if ch in cfg['channels']:
                cfg['channels'].remove(ch)
                save_config(cfg)
                update.message.reply_text(f"❎ تمت إزالة القناة {ch}")
        elif action == 'notify':
            sent = 0
            for uid in cfg['users']:
                if str(uid) not in cfg['banned']:
                    try:
                        context.bot.send_message(chat_id=uid, text=text)
                        sent += 1
                    except:
                        pass
            update.message.reply_text(f"📨 تم الإرسال إلى {sent} مستخدم")
        context.user_data.pop('admin_action', None)
        # العودة للوحة التحكم
        show_main_menu(update.message.chat_id, context.bot, is_admin=True)
        return

    # User search
    if not context.user_data.get('awaiting'):
        return

    context.user_data['awaiting'] = False
    query_text = text
    hits_all = []
    page = 1

    # جلب حتى 100 نتيجة
    while len(hits_all) < 100:
        params = {
            'key': PIXABAY_API_KEY,
            'q': query_text,
            'image_type': context.user_data.get('search_type', 'photo'),
            'per_page': 100,
            'page': page
        }
        resp = requests.get('https://pixabay.com/api/', params=params).json()
        hits = resp.get('hits', [])
        if not hits:
            break
        hits_all.extend(hits)
        if len(hits) < 100:
            break
        page += 1

    results = hits_all[:100]
    if not results:
        update.message.reply_text("¯\\_(ツ)_/¯\nكلماتك غريبة يا غلام")
        return

    context.user_data['results'] = results
    context.user_data['idx']     = 0
    config['searches'] += 1
    save_config(config)

    send_media(update, context, first=True)

def send_media(update_or_query, context, first=False):
    chat_id = update_or_query.message.chat.id
    idx     = context.user_data['idx']
    item    = context.user_data['results'][idx]

    # Video or photo
    if 'videos' in item:
        url = item['videos']['medium']['url']
        bio = download_file(url)
        media = InputMediaVideo(media=bio, caption=f"🎬 بواسطة {item['user']}")
    else:
        url = item.get('largeImageURL') or item.get('webformatURL')
        bio = download_file(url)
        media = InputMediaPhoto(media=bio, caption=f"📷 بواسطة {item['user']}")

    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("« السابق", callback_data='prev'))
    if idx < len(context.user_data['results']) - 1:
        nav.append(InlineKeyboardButton("التالي »", callback_data='next'))
    keyboard = [nav, [InlineKeyboardButton("اختيار🥇", callback_data='select')], 
                [InlineKeyboardButton("رجوع 🏠", callback_data='main_menu')]]
    markup = InlineKeyboardMarkup(keyboard)

    bot = context.bot
    if first:
        if isinstance(media, InputMediaPhoto):
            msg = bot.send_photo(chat_id, photo=bio, caption=media.caption, reply_markup=markup)
        else:
            msg = bot.send_video(chat_id, video=bio, caption=media.caption, reply_markup=markup)
        context.user_data['msg_id'] = msg.message_id
    else:
        bot.edit_message_media(
            chat_id=chat_id,
            message_id=context.user_data['msg_id'],
            media=media,
            reply_markup=markup
        )

def handle_navigation(query, context, action):
    if action == 'next':
        context.user_data['idx'] += 1
    elif action == 'prev':
        context.user_data['idx'] -= 1
    elif action == 'select':
        query.edit_message_reply_markup(reply_markup=None)
        return
    send_media(query, context, first=False)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    # يبدأ بوت التليجرام تلقائياً
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
