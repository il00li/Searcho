import os
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import requests

# Telegram Bot Token
TOKEN = '8496475334:AAFVBYMsb_d_K80YkD06V3ZlcASS2jzV0uQ'

# Pixabay API Key
PIXABAY_API_KEY = '51444506-bffefcaf12816bd85a20222d1'

# Manager ID
MANAGER_ID = 7251748706

# Mandatory Subscription Channels
MANDATORY_CHANNELS = ['@crazys7']

def start(update, context):
    user_id = update.effective_user.id
    if not is_subscribed(user_id):
        context.bot.send_message(
            chat_id=user_id,
            text="(•_•)\n<)   )╯\n /   \\\n🎧 | اشترك في القنوات اولا [@crazys7] ، بعدها يتم التحقق من اشتراكة في قنوات الاشتراك الاجباري عبر زر اسفل ازرار قنوات الاشتراك الاجباري \"تحقق | Verify\" اذا اشترك يمكنة استخدام البوت .",
            reply_markup=get_subscription_keyboard()
        )
    else:
        context.bot.send_message(
            chat_id=user_id,
            text="(⊙_☉)\n /|\\\n / \\\nهل تريد بدء بحث?!",
            reply_markup=get_search_keyboard()
        )

def is_subscribed(user_id):
    for channel in MANDATORY_CHANNELS:
        if not context.bot.get_chat_member(chat_id=channel, user_id=user_id).status == 'member':
            return False
    return True

def get_subscription_keyboard():
    keyboard = [[InlineKeyboardButton("تحقق | Verify", callback_data='verify')]]
    return InlineKeyboardMarkup(keyboard)

def get_search_keyboard():
    keyboard = [
        [InlineKeyboardButton("بدء البحث 🎧", callback_data='start_search')],
        [InlineKeyboardButton("نوع البحث💐", callback_data='search_type')]
    ]
    return InlineKeyboardMarkup(keyboard)

def search_type(update, context):
    keyboard = [
        [InlineKeyboardButton("Vectors", callback_data='type_vectors'), InlineKeyboardButton("Illustrations", callback_data='type_illustrations')],
        [InlineKeyboardButton("Video", callback_data='type_video'), InlineKeyboardButton("Photo", callback_data='type_photo')],
        [InlineKeyboardButton("Music", callback_data='type_music'), InlineKeyboardButton("GIF", callback_data='type_gif')],
        [InlineKeyboardButton("بدء البحث", callback_data='start_search')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="اختر نوع البحث:", reply_markup=reply_markup)

def handle_search(update, context):
    query = update.callback_query
    query.answer()

    if query.data == 'start_search':
        context.bot.send_message(chat_id=update.effective_chat.id, text="أدخل كلمات البحث:")
        context.set_state('WAITING_FOR_QUERY')
    elif query.data.startswith('type_'):
        search_type = query.data.split('_')[1]
        context.user_data['search_type'] = search_type
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"تم تحديد نوع البحث: {search_type.capitalize()}")
    elif query.data == 'verify':
        if is_subscribed(update.effective_user.id):
            context.bot.send_message(chat_id=update.effective_chat.id, text="(⊙_☉)\n /|\\\n / \\\nهل تريد بدء بحث?!", reply_markup=get_search_keyboard())
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="عذرًا، يجب عليك الاشتراك في القنوات الإلزامية أولاً.")

def handle_query(update, context):
    query = update.message.text
    search_type = context.user_data.get('search_type', 'photo')
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'image_type': search_type,
        'per_page': 10,
        'page': 1
    }
    response = requests.get('https://pixabay.com/api/', params=params)
    data = response.json()

    if data['hits']:
        current_page = 1
        total_pages = (data['totalHits'] + 9) // 10
        message = display_results(data['hits'], current_page, total_pages)
        keyboard = get_pagination_keyboard(current_page, total_pages)
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=keyboard)
        context.user_data['search_results'] = data['hits']
        context.user_data['current_page'] = current_page
        context.user_data['total_pages'] = total_pages
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="¯\\_(ツ)_/¯\n كلماتك غريبة يا غلام")

    context.set_state('SEARCH_RESULTS')

def display_results(results, current_page, total_pages):
    message = f"الصفحة {current_page}/{total_pages}\n\n"
    for result in results:
        message += f"[{result['type'].capitalize()}] {result['user']}\n"
    return message

def get_pagination_keyboard(current_page, total_pages):
    keyboard = []
    if current_page > 1:
        keyboard.append([InlineKeyboardButton("«", callback_data=f'prev_page')])
    if current_page < total_pages:
        keyboard.append([InlineKeyboardButton("»", callback_data=f'next_page')])
    keyboard.append([InlineKeyboardButton("اختيار🥇", callback_data=f'select')])
    return InlineKeyboardMarkup(keyboard)

def handle_pagination(update, context):
    query = update.callback_query
    query.answer()

    if query.data == 'prev_page':
        current_page = context.user_data['current_page']
        total_pages = context.user_data['total_pages']
        if current_page > 1:
            current_page -= 1
            message = display_results(context.user_data['search_results'], current_page, total_pages)
            keyboard = get_pagination_keyboard(current_page, total_pages)
            context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=query.message.message_id, text=message, reply_markup=keyboard)
            context.user_data['current_page'] = current_page
    elif query.data == 'next_page':
        current_page = context.user_data['current_page']
        total_pages = context.user_data['total_pages']
        if current_page < total_pages:
            current_page += 1
            message = display_results(context.user_data['search_results'], current_page, total_pages)
            keyboard = get_pagination_keyboard(current_page, total_pages)
            context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=query.message.message_id, text=message, reply_markup=keyboard)
            context.user_data['current_page'] = current_page
    elif query.data == 'select':
        current_page = context.user_data['current_page']
        results = context.user_data['search_results']
        selected_result = results[current_page - 1]
        context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=query.message.message_id, text=f"[{selected_result['type'].capitalize()}] {selected_result['user']}\n{selected_result['pageURL']}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_search, pattern='^(start_search|type_|verify)$'))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_query))
    dp.add_handler(CallbackQueryHandler(handle_pagination, pattern='^(prev_page|next_page|select)$'))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
