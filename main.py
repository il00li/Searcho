import telegram, requests, json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# بيانات الدخول والربط
BOT_TOKEN = '8496475334:AAFVBYMsb_d_K80YkD06V3ZlcASS2jzV0uQ'
PIXABAY_KEY = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_ID = 7251748706
MANDATORY_CHANNELS = []

# 🛡️ وظيفة التحقق من الاشتراك
def is_subscribed(user_id, context):
    for channel in MANDATORY_CHANNELS:
        try:
            status = context.bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

# 🎧 عرض رسالة الاشتراك
def send_subscription_prompt(chat_id, context):
    buttons = [[InlineKeyboardButton("تحقق | Verify", callback_data='verify')]]
    for ch in MANDATORY_CHANNELS:
        buttons.insert(0, [InlineKeyboardButton(ch, url=f'https://t.me/{ch.replace("@", "")}')])
    msg = "(•_•)\n<)   )╯\n /   \\\n🎧 | اشترك في القنوات أولاً ثم اضغط 'تحقق | Verify'."
    context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(buttons))

# 🏁 بدء البوت
def start(update, context):
    user_id = update.effective_user.id
    if not is_subscribed(user_id, context):
        send_subscription_prompt(update.effective_chat.id, context)
    else:
        msg = "(⊙_☉)\n /|\\\n / \\\nهل تريد بدء بحث؟!"
        keyboard = [
            [InlineKeyboardButton("بدء البحث 🎧", callback_data='start_search')],
            [InlineKeyboardButton("نوع البحث 💐", callback_data='search_type')]
        ]
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))

# 🧠 تحديد نوع البحث
def show_search_types(update, context):
    update.callback_query.answer()
    buttons = []
    for t in ['vectors', 'illustrations', 'video', 'photo', 'music', 'gif']:
        mark = '👻' if context.user_data.get('search_type') == t else ''
        buttons.append([InlineKeyboardButton(f"{mark} {t}", callback_data=f'type_{t}')])
    buttons.append([InlineKeyboardButton("بدء البحث", callback_data='start_search')])
    context.bot.send_message(chat_id=update.effective_chat.id, text="💐 اختر نوع البحث:", reply_markup=InlineKeyboardMarkup(buttons))

# 🔄 التعامل مع الأزرار
def handle_buttons(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    uid = query.from_user.id

    if data == 'verify':
        if is_subscribed(uid, context):
            start(update, context)
        else:
            send_subscription_prompt(query.message.chat.id, context)
    elif data.startswith('type_'):
        context.user_data['search_type'] = data.replace('type_', '')
        show_search_types(update, context)
    elif data == 'search_type':
        show_search_types(update, context)
    elif data == 'start_search':
        context.user_data['awaiting_query'] = True
        context.bot.send_message(chat_id=query.message.chat.id, text="✏️ أرسل كلمات البحث:")

    elif data in ['next', 'prev', 'select']:
        results = context.user_data.get('results', [])
        i = context.user_data.get('index', 0)
        if data == 'next' and i < len(results) - 1: i += 1
        elif data == 'prev' and i > 0: i -= 1
        context.user_data['index'] = i

        selected = results[i]
        msg = f"🎨 [{selected['type']}] بواسطة {selected['user']}\n{selected['pageURL']}"
        buttons = []
        if data != 'select':
            buttons.append([
                InlineKeyboardButton("«", callback_data='next'),
                InlineKeyboardButton("»", callback_data='prev')
            ])
            buttons.append([InlineKeyboardButton("اختيار🥇", callback_data='select')])
        query.edit_message_text(text=msg, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

# 📡 استقبال كلمات البحث
def handle_text(update, context):
    if not context.user_data.get('awaiting_query'): return
    query = update.message.text
    stype = context.user_data.get('search_type', 'photo')
    url = f'https://pixabay.com/api/?key={PIXABAY_KEY}&q={query}&image_type={stype}&per_page=10'
    res = requests.get(url).json()
    hits = res.get('hits', [])
    context.user_data['awaiting_query'] = False

    if hits:
        context.user_data['results'] = hits
        context.user_data['index'] = 0
        first = hits[0]
        msg = f"🎨 [{first['type']}] بواسطة {first['user']}\n{first['pageURL']}"
        buttons = [
            [InlineKeyboardButton("«", callback_data='next'), InlineKeyboardButton("»", callback_data='prev')],
            [InlineKeyboardButton("اختيار🥇", callback_data='select')]
        ]
        update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        update.message.reply_text("¯\\_(ツ)_/¯\nكلماتك غريبة يا غلام")

# 👑 أوامر المدير
def admin_command(update, context):
    uid = update.effective_user.id
    if uid != ADMIN_ID: return
    cmd = update.message.text

    if cmd.startswith("/ban"):
        args = cmd.split(" ")
        if len(args) >= 3:
            user_id, username = args[1], args[2]
            with open("banned.json", "a") as f:
                json.dump({user_id: username}, f)
            update.message.reply_text(f"🚫 تم حظر المستخدم {username}")
    elif cmd.startswith("/channels"):
        update.message.reply_text(f"📢 قنوات الاشتراك الحالية: {', '.join(MANDATORY_CHANNELS) or 'لا يوجد'}")
    elif cmd.startswith("/add_channel"):
        ch = cmd.split(" ")[1]
        MANDATORY_CHANNELS.append(ch)
        update.message.reply_text(f"✅ تم إضافة {ch}")
    elif cmd.startswith("/remove_channel"):
        ch = cmd.split(" ")[1]
        if ch in MANDATORY_CHANNELS:
            MANDATORY_CHANNELS.remove(ch)
            update.message.reply_text(f"❎ تم إزالة {ch}")
    elif cmd.startswith("/stats"):
        stats = {
            'users': '🧍 عدد المستخدمين غير مخزن حالياً',
            'searches': '🔍 عدد عمليات البحث غير متوفر حالياً',
            'channels': len(MANDATORY_CHANNELS)
        }
        update.message.reply_text("\n".join(stats.values()))
    elif cmd.startswith("/notify"):
        msg = cmd.replace("/notify", "").strip()
        if msg:
            update.message.reply_text("📤 جاري إرسال الإشعارات...")
            # هذه النسخة لا تخزن المستخدمين لذا تحتاج إلى قاعدة بيانات حقيقية
            update.message.reply_text("📛 إشعار وهمي فقط في هذه النسخة")

# 🧬 تشغيل البوت
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(CommandHandler('ban', admin_command))
    dp.add_handler(CommandHandler('add_channel', admin_command))
    dp.add_handler(CommandHandler('remove_channel', admin_command))
    dp.add_handler(CommandHandler('channels', admin_command))
    dp.add_handler(CommandHandler('stats', admin_command))
    dp.add_handler(CommandHandler('notify', admin_command))
    dp.add_handler(CallbackQueryHandler(handle_buttons))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
