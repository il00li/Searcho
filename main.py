import os
import io
import json
import logging
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
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)

# ------------[ config + constants ]------------

CONFIG_PATH      = 'config.json'
BOT_TOKEN        = '8496475334:AAFVBYMsb_d_K80YkD06V3ZlcASS2jzV0uQ'
PIXABAY_API_KEY  = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_ID         = 7251748706

SEARCH_TYPES = [
    ('vector',       'Vectors'),
    ('illustration', 'Illustrations'),
    ('video',        'Video'),
    ('photo',        'Photos'),
    ('music',        'Music'),
    ('gif',          'GIF'),
]

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

# default structure for persistence
DEFAULT_CFG = {
    "banned":   {},           # { user_id: username }
    "channels": ["@crazys7"],
    "users":    [],           # كل مستخدم مر عليه البوت
    "searches": 0             # عدّاد عمليات البحث
}

# -------------[ load / save config ]-------------

def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = DEFAULT_CFG.copy()
        save_config(cfg)
        return cfg
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config = load_config()

# ---------------[ helpers ]---------------

def is_banned(user_id):
    return str(user_id) in config['banned']

def add_user(user_id):
    if user_id not in config['users']:
        config['users'].append(user_id)
        save_config(config)

def is_subscribed(user_id, bot):
    for ch in config['channels']:
        try:
            st = bot.get_chat_member(chat_id=ch, user_id=user_id).status
            if st not in ['member', 'creator', 'administrator']:
                return False
        except:
            return False
    return True

def download_file(url):
    resp = requests.get(url, stream=True)
    if resp.status_code == 200:
        bio = io.BytesIO(resp.content)
        bio.name = url.split("/")[-1]
        return bio
    return None

# --------------[ command handlers ]--------------

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if is_banned(user_id):
        update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
        return

    add_user(user_id)
    bot = context.bot

    if not is_subscribed(user_id, bot):
        # menu اشتراك
        buttons = [
            [InlineKeyboardButton(ch, url=f"https://t.me/{ch.strip('@')}")]
            for ch in config['channels']
        ]
        buttons.append([InlineKeyboardButton("تحقق | Verify", callback_data='verify')])
        update.message.reply_text(
            SUBSCRIBE_ART,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        send_ready_menu(update.message.chat.id, user_id, bot)

def send_ready_menu(chat_id, user_id, bot):
    buttons = [
        [InlineKeyboardButton("بدء البحث 🎧", callback_data='start_search')],
        [InlineKeyboardButton("نوع البحث 💐", callback_data='search_type')]
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("لوحة التحكم 🛠️", callback_data='admin_panel')])
    bot.send_message(
        chat_id,
        READY_ART,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ------------[ inline callback handler ]------------

def on_callback(update: Update, context: CallbackContext):
    query   = update.callback_query
    data    = query.data
    uid     = query.from_user.id
    bot     = context.bot
    query.answer()

    if is_banned(uid):
        query.edit_message_text("🚫 أنت محظور.")
        return

    # تحقق من اشتراك القنوات
    if data == 'verify':
        if is_subscribed(uid, bot):
            send_ready_menu(query.message.chat.id, uid, bot)
        else:
            query.edit_message_text("⚠️ لم تشترك بعد.")
        return

    # القائمة الرئيسية
    if data == 'main_menu':
        send_ready_menu(query.message.chat.id, uid, bot)
        return

    # بدء إدخال نص البحث
    if data == 'start_search':
        context.user_data.clear()
        context.user_data['awaiting'] = True
        query.edit_message_text("✏️ أرسل كلمات البحث:")
        return

    # اختر نوع البحث
    if data == 'search_type':
        show_type_menu(query, context)
        return

    # ضبط النوع المختار
    if data.startswith('type_'):
        _, t = data.split('_', 1)
        context.user_data['search_type'] = t
        show_type_menu(query, context)
        return

    # لوحة التحكم (للمدير)
    if uid == ADMIN_ID and data == 'admin_panel':
        show_admin_menu(query)
        return

    # إجراءات admin
    if uid == ADMIN_ID and data.startswith('admin_'):
        act = data.split('_', 1)[1]
        context.user_data['admin_action'] = act
        if act == 'stats':
            show_stats(query)
        else:
            prompts = {
                'ban':  "✏️ أرسل: user_id username",
                'unban':"✏️ أرسل: user_id",
                'setchn': "✏️ أرسل: @channel",
                'unsetchn':"✏️ أرسل: @channel",
                'notify': "✏️ أرسل نص الإشعار:"
            }
            query.edit_message_text(prompts[act])
        return

    # تنقل أو اختيار وسط النتائج
    if data in ['next', 'prev', 'select']:
        navigate_results(query, context, data)
        return

# -------------[ show menus ]-------------

def show_type_menu(query, context):
    chosen = context.user_data.get('search_type','')
    buttons = []
    for value, label in SEARCH_TYPES:
        mark = '👻' if chosen == value else ''
        buttons.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"type_{value}")])
    buttons.append([InlineKeyboardButton("بدء البحث 🎧", callback_data='start_search')])
    buttons.append([InlineKeyboardButton("رجوع 🏠", callback_data='main_menu')])
    query.edit_message_text("💐 اختر نوع البحث:", reply_markup=InlineKeyboardMarkup(buttons))

def show_admin_menu(query):
    btns = [
        [InlineKeyboardButton("حظر مستخدم 🚫",    callback_data='admin_ban')],
        [InlineKeyboardButton("رفع حظر ✅",       callback_data='admin_unban')],
        [InlineKeyboardButton("تعيين قناة 📢",   callback_data='admin_setchn')],
        [InlineKeyboardButton("إلغاء قناة ❎",    callback_data='admin_unsetchn')],
        [InlineKeyboardButton("إحصائيات 📊",      callback_data='admin_stats')],
        [InlineKeyboardButton("إرسال إشعار 📣",   callback_data='admin_notify')],
        [InlineKeyboardButton("رجوع 🏠",          callback_data='main_menu')]
    ]
    query.edit_message_text("🛠️ لوحة التحكم:", reply_markup=InlineKeyboardMarkup(btns))

def show_stats(query):
    u = len(config['users'])
    s = config['searches']
    c = len(config['channels'])
    text = f"🧍 المستخدمين: {u}\n🔍 طلبات البحث: {s}\n📢 قنوات الإشتراك: {c}"
    query.edit_message_text(text)

# ------------[ text handler ]------------

def on_text(update: Update, context: CallbackContext):
    uid  = update.effective_user.id
    text = update.message.text.strip()

    # admin actions via text
    action = context.user_data.get('admin_action')
    if uid == ADMIN_ID and action:
        if action == 'ban':
            parts = text.split(None,1)
            if len(parts)==2:
                config['banned'][parts[0]] = parts[1]
                save_config(config)
                update.message.reply_text(f"🚫 تم حظر {parts[1]}")
        if action == 'unban':
            if text in config['banned']:
                name = config['banned'].pop(text)
                save_config(config)
                update.message.reply_text(f"✅ تم رفع الحظر عن {name}")
        if action == 'setchn':
            if text not in config['channels']:
                config['channels'].append(text)
                save_config(config)
                update.message.reply_text(f"✅ تمت إضافة القناة {text}")
        if action == 'unsetchn':
            if text in config['channels']:
                config['channels'].remove(text)
                save_config(config)
                update.message.reply_text(f"❎ تمت إزالة القناة {text}")
        if action == 'notify':
            sent = 0
            for u in config['users']:
                if str(u) not in config['banned']:
                    try:
                        context.bot.send_message(chat_id=u, text=text)
                        sent += 1
                    except:
                        pass
            update.message.reply_text(f"📨 تم الإرسال إلى {sent} مستخدم")
        context.user_data.pop('admin_action', None)
        show_admin_menu(update.callback_query or update, context)
        return

    # user search text
    if not context.user_data.get('awaiting'):
        return
    context.user_data['awaiting'] = False

    query_text = text
    dtype      = context.user_data.get('search_type','photo')
    all_hits   = []
    page       = 1
    endpoint   = 'https://pixabay.com/api/videos/' if dtype in ['video','music','gif'] else 'https://pixabay.com/api/'
    
    # جمع حتى 100 نتيجة
    while len(all_hits) < 100:
        params = {
            'key': PIXABAY_API_KEY,
            'q': query_text,
            'per_page': 100,
            'page': page
        }
        if endpoint.endswith('/videos/'):
            if dtype == 'gif':
                params['video_type'] = 'animation'
            if dtype == 'music':
                params['category'] = 'music'
        else:
            params['image_type'] = dtype

        resp = requests.get(endpoint, params=params).json()
        hits = resp.get('hits', [])
        if not hits:
            break
        all_hits.extend(hits)
        if len(hits) < 100:
            break
        page += 1

    results = all_hits[:100]
    if not results:
        update.message.reply_text("¯\\_(ツ)_/¯\nكلماتك غريبة يا غلام")
        return

    # خزّن النتائج وابدأ العرض
    context.user_data['results'] = results
    context.user_data['idx']     = 0
    config['searches'] += 1
    save_config(config)
    send_media(update, context, first=True)

# ---------[ send & navigate media ]----------

def send_media(upd, context, first=False):
    # تحديد الدردشة والبيانات
    if isinstance(upd, Update) and upd.message:
        chat_id = upd.message.chat.id
    else:
        chat_id = upd.callback_query.message.chat.id

    idx  = context.user_data['idx']
    item = context.user_data['results'][idx]

    # تحميل ملف
    if 'videos' in item:
        url = item['videos']['medium']['url']
        bio = download_file(url)
        media = InputMediaVideo(media=bio, caption=f"🎬 بواسطة {item['user']}")
    else:
        url = item.get('largeImageURL') or item.get('webformatURL')
        bio = download_file(url)
        media = InputMediaPhoto(media=bio, caption=f"📷 بواسطة {item['user']}")

    # أزرار التنقل والاختيار
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("« السابق", callback_data='prev'))
    if idx < len(context.user_data['results']) - 1:
        nav.append(InlineKeyboardButton("التالي »", callback_data='next'))

    buttons = [
        nav,
        [InlineKeyboardButton("اختيار🥇", callback_data='select')],
        [InlineKeyboardButton("رجوع 🏠", callback_data='main_menu')]
    ]
    markup = InlineKeyboardMarkup(buttons)
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

def navigate_results(query, context, action):
    if action == 'next':
        context.user_data['idx'] += 1
    elif action == 'prev':
        context.user_data['idx'] -= 1
    elif action == 'select':
        query.edit_message_reply_markup(reply_markup=None)
        return
    send_media(query, context, first=False)

# -----------------[ main ]------------------

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(on_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, on_text))

    updater.start_polling()
    updater.idle()
