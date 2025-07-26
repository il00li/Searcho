#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
import asyncio
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import Conflict

# Configuration - Environment variables embedded for Render deployment
BOT_TOKEN = "8496475334:AAFVBYMsb_d_K80YkD06V3ZlcASS2jzV0uQ"
ADMIN_ID = 7251748706
PIXABAY_API_KEY = "51444506-bffefcaf12816bd85a20222d1"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_banned INTEGER DEFAULT 0,
            join_date TEXT,
            last_active TEXT,
            search_count INTEGER DEFAULT 0
        )
    ''')
    
    # Mandatory channels table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            channel_id TEXT PRIMARY KEY,
            channel_username TEXT,
            added_date TEXT
        )
    ''')
    
    # User sessions table for search state
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER PRIMARY KEY,
            search_query TEXT,
            search_type TEXT,
            current_page INTEGER DEFAULT 0,
            results_data TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

class BotDatabase:
    """Database operations handler"""
    
    @staticmethod
    def add_user(user_id: int, username: str = None, first_name: str = None):
        """Add or update user in database"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, join_date, last_active, search_count)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT search_count FROM users WHERE user_id = ?), 0))
        ''', (user_id, username, first_name, current_time, current_time, user_id))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def is_user_banned(user_id: int) -> bool:
        """Check if user is banned"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result and result[0] == 1
    
    @staticmethod
    def ban_user(user_id: int):
        """Ban a user"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def unban_user(user_id: int):
        """Unban a user"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_mandatory_channels() -> List[Tuple[str, str]]:
        """Get list of mandatory channels"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT channel_id, channel_username FROM mandatory_channels')
        channels = cursor.fetchall()
        
        conn.close()
        return channels
    
    @staticmethod
    def add_mandatory_channel(channel_id: str, channel_username: str):
        """Add mandatory channel"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO mandatory_channels 
            (channel_id, channel_username, added_date)
            VALUES (?, ?, ?)
        ''', (channel_id, channel_username, current_time))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def remove_mandatory_channel(channel_id: str):
        """Remove mandatory channel"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM mandatory_channels WHERE channel_id = ?', (channel_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def increment_search_count(user_id: int):
        """Increment user's search count"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET search_count = search_count + 1, last_active = ?
            WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def save_user_session(user_id: int, query: str, search_type: str, page: int, results: dict):
        """Save user's search session"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_sessions 
            (user_id, search_query, search_type, current_page, results_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, query, search_type, page, json.dumps(results)))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_user_session(user_id: int) -> Optional[dict]:
        """Get user's search session"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT search_query, search_type, current_page, results_data 
            FROM user_sessions WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                'query': result[0],
                'search_type': result[1],
                'current_page': result[2],
                'results': json.loads(result[3]) if result[3] else {}
            }
        return None
    
    @staticmethod
    def get_statistics() -> dict:
        """Get bot statistics"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Get total searches
        cursor.execute('SELECT SUM(search_count) FROM users')
        total_searches = cursor.fetchone()[0] or 0
        
        # Get mandatory channels count
        cursor.execute('SELECT COUNT(*) FROM mandatory_channels')
        total_channels = cursor.fetchone()[0]
        
        # Get active users (searched in last 30 days)
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE datetime(last_active) > datetime('now', '-30 days')
        ''')
        active_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_searches': total_searches,
            'total_channels': total_channels,
            'active_users': active_users
        }
    
    @staticmethod
    def get_all_users() -> List[int]:
        """Get all user IDs for broadcasting"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
        users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return users

class PixabayAPI:
    """Pixabay API handler"""
    
    @staticmethod
    def search(query: str, search_type: str = "photo", page: int = 1, per_page: int = 20) -> dict:
        """Search Pixabay API"""
        try:
            # Map search types to Pixabay API endpoints
            type_mapping = {
                "photo": "https://pixabay.com/api/",
                "video": "https://pixabay.com/api/videos/",
                "vectors": "https://pixabay.com/api/",
                "illustrations": "https://pixabay.com/api/",
                "music": "https://pixabay.com/api/music/",
                "gif": "https://pixabay.com/api/"
            }
            
            base_url = type_mapping.get(search_type, "https://pixabay.com/api/")
            
            params = {
                "key": PIXABAY_API_KEY,
                "q": query,
                "page": page,
                "per_page": per_page,
                "safesearch": "true",
                "lang": "ar"
            }
            
            # Additional parameters for specific types
            if search_type in ["vectors", "illustrations"]:
                params["image_type"] = search_type.rstrip('s')  # Remove 's' from end
            elif search_type == "gif":
                params["image_type"] = "photo"
                params["category"] = "backgrounds"
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Pixabay API error: {e}")
            return {"hits": [], "total": 0}
        except Exception as e:
            logger.error(f"Unexpected error in Pixabay search: {e}")
            return {"hits": [], "total": 0}

class TelegramBot:
    """Main Telegram bot class"""
    
    def __init__(self):
        self.application = None
        self.search_types = {
            "photo": "صور 📷",
            "video": "فيديو 🎬", 
            "vectors": "رسوم متجهة 📐",
            "illustrations": "رسوم توضيحية 🎨",
            "music": "موسيقى 🎵",
            "gif": "صور متحركة 🎭"
        }
    
    async def check_subscription(self, user_id: int, bot: Bot) -> bool:
        """Check if user is subscribed to all mandatory channels"""
        channels = BotDatabase.get_mandatory_channels()
        
        if not channels:
            return True
        
        for channel_id, _ in channels:
            try:
                # Check if user is member of the channel
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    return False
            except Exception as e:
                logger.error(f"Error checking subscription for channel {channel_id}: {e}")
                return False
        
        return True
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Add user to database
        BotDatabase.add_user(user.id, user.username, user.first_name)
        
        # Check if user is banned
        if BotDatabase.is_user_banned(user.id):
            await update.message.reply_text("🚫 تم حظركم من استخدام البوت")
            return
        
        # Check subscription
        is_subscribed = await self.check_subscription(user.id, context.bot)
        
        if not is_subscribed:
            welcome_message = """   (•_•)  
  <)   )╯  
   /   \\  
🎧 | اشترك في القنوات اولا [@Ili8_8ill]"""
            
            channels = BotDatabase.get_mandatory_channels()
            keyboard = []
            
            for channel_id, channel_username in channels:
                if channel_username:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"📢 {channel_username}",
                            url=f"https://t.me/{channel_username.replace('@', '')}"
                        )
                    ])
            
            keyboard.append([
                InlineKeyboardButton("تحقق | Verify ✅", callback_data="verify_subscription")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
        else:
            await self.show_main_menu(update, context)
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu after verification"""
        main_message = """(⊙_☉)  
  /|\\
  / \\
هل تريد بدء بحث؟!"""
        
        keyboard = [
            [InlineKeyboardButton("بدء البحث 🎧", callback_data="start_search")],
            [InlineKeyboardButton("نوع البحث💐", callback_data="search_type_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(main_message, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(main_message, reply_markup=reply_markup)
    
    async def verify_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle subscription verification"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        is_subscribed = await self.check_subscription(user_id, context.bot)
        
        if is_subscribed:
            await self.show_main_menu(update, context)
        else:
            await query.answer("❌ لم تشترك في جميع القنوات المطلوبة", show_alert=True)
    
    async def search_type_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show search type selection menu"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        selected_type = context.user_data.get('selected_search_type', None) if context.user_data else None
        
        for search_type, display_name in self.search_types.items():
            if selected_type == search_type:
                display_name = f"👻 {display_name}"
            keyboard.append([
                InlineKeyboardButton(
                    display_name, 
                    callback_data=f"select_type_{search_type}"
                )
            ])
        
        if selected_type:
            keyboard.append([
                InlineKeyboardButton(f"بحث في {self.search_types[selected_type]} 🔍", callback_data="start_typed_search")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "اختر نوع البحث:",
            reply_markup=reply_markup
        )
    
    async def select_search_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search type selection"""
        query = update.callback_query
        await query.answer()
        
        search_type = query.data.replace("select_type_", "")
        if not context.user_data:
            context.user_data = {}
        context.user_data['selected_search_type'] = search_type
        
        # Refresh the menu with updated selection
        await self.search_type_menu(update, context)
    
    async def start_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start general search"""
        query = update.callback_query
        await query.answer()
        
        if not context.user_data:
            context.user_data = {}
        context.user_data['search_mode'] = 'general'
        await query.edit_message_text(
            "ارسل كلمة البحث:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
            ]])
        )
    
    async def start_typed_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start typed search"""
        query = update.callback_query
        await query.answer()
        
        selected_type = context.user_data.get('selected_search_type') if context.user_data else None
        if not selected_type:
            await query.answer("❌ اختر نوع البحث أولاً", show_alert=True)
            return
        
        if not context.user_data:
            context.user_data = {}
        context.user_data['search_mode'] = 'typed'
        await query.edit_message_text(
            f"ارسل كلمة البحث لـ {self.search_types[selected_type]}:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="search_type_menu")
            ]])
        )
    
    async def handle_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search query from user"""
        if not context.user_data or 'search_mode' not in context.user_data:
            return
        
        search_query = update.message.text
        user_id = update.effective_user.id
        
        # Determine search type
        if context.user_data['search_mode'] == 'typed':
            search_type = context.user_data.get('selected_search_type', 'photo')
        else:
            search_type = 'photo'  # Default for general search
        
        # Show searching message
        searching_msg = await update.message.reply_text("🔍 جاري البحث...")
        
        # Perform search
        results = PixabayAPI.search(search_query, search_type, page=1)
        
        if not results['hits']:
            await searching_msg.edit_text("""   ¯\\_(ツ)_/¯
    كلماتك غريبة يا غلام""")
            return
        
        # Save search session
        BotDatabase.save_user_session(user_id, search_query, search_type, 0, results)
        BotDatabase.increment_search_count(user_id)
        
        # Show first result
        await self.show_search_result(searching_msg, user_id, 0)
        
        # Clear search mode
        if context.user_data:
            context.user_data.pop('search_mode', None)
    
    async def show_search_result(self, message, user_id: int, page: int):
        """Show search result at specific page"""
        session = BotDatabase.get_user_session(user_id)
        if not session:
            await message.edit_text("❌ لا توجد نتائج محفوظة")
            return
        
        results = session['results']
        hits = results.get('hits', [])
        
        if not hits or page >= len(hits):
            await message.edit_text("❌ لا توجد نتائج أخرى")
            return
        
        result = hits[page]
        
        # Update session with current page
        BotDatabase.save_user_session(
            user_id, session['query'], session['search_type'], 
            page, results
        )
        
        # Prepare result message and media
        caption = f"البحث: {session['query']}\nالنوع: {self.search_types.get(session['search_type'], 'صور')}\nالصفحة: {page + 1}/{len(hits)}"
        
        # Navigation buttons
        keyboard = []
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("« السابق", callback_data=f"nav_prev_{page}"))
        if page < len(hits) - 1:
            nav_buttons.append(InlineKeyboardButton("التالي »", callback_data=f"nav_next_{page}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("اختيار 🥇", callback_data=f"select_result_{page}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Send based on content type
            if session['search_type'] == 'video':
                video_url = result.get('videos', {}).get('medium', {}).get('url', '')
                if video_url:
                    await message.edit_text(f"{caption}\n\n🎬 رابط الفيديو: {video_url}", reply_markup=reply_markup)
                else:
                    await message.edit_text(f"{caption}\n\n❌ فيديو غير متوفر", reply_markup=reply_markup)
            else:
                # For images (photo, vectors, illustrations, gif)
                image_url = result.get('webformatURL', result.get('largeImageURL', ''))
                if image_url:
                    try:
                        await message.delete()
                        bot = message.get_bot()
                        await bot.send_photo(
                            chat_id=message.chat_id,
                            photo=image_url,
                            caption=caption,
                            reply_markup=reply_markup
                        )
                    except:
                        await message.edit_text(f"{caption}\n\n🖼️ رابط الصورة: {image_url}", reply_markup=reply_markup)
                else:
                    await message.edit_text(f"{caption}\n\n❌ صورة غير متوفرة", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error showing result: {e}")
            await message.edit_text(f"{caption}\n\n❌ خطأ في عرض النتيجة", reply_markup=reply_markup)
    
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle navigation between results"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith("nav_prev_"):
            current_page = int(data.split("_")[-1])
            new_page = current_page - 1
        elif data.startswith("nav_next_"):
            current_page = int(data.split("_")[-1])
            new_page = current_page + 1
        else:
            return
        
        await self.show_search_result(query.message, user_id, new_page)
    
    async def select_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle result selection"""
        query = update.callback_query
        await query.answer("✅ تم اختيار النتيجة!")
        
        # Remove keyboard to show selection is complete
        await query.edit_message_reply_markup(reply_markup=None)
    
    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return to main menu"""
        await self.show_main_menu(update, context)
    
    # Admin commands
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ غير مصرح لك")
            return
        
        keyboard = [
            [InlineKeyboardButton("إحصائيات البوت 📊", callback_data="admin_stats")],
            [InlineKeyboardButton("إدارة المستخدمين 👥", callback_data="admin_users")],
            [InlineKeyboardButton("إدارة القنوات 📢", callback_data="admin_channels")],
            [InlineKeyboardButton("إرسال إشعار 📨", callback_data="admin_broadcast")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔧 لوحة تحكم الإدارة:", reply_markup=reply_markup)
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id != ADMIN_ID:
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        
        stats = BotDatabase.get_statistics()
        
        stats_text = f"""📊 إحصائيات البوت:

👥 إجمالي المستخدمين: {stats['total_users']}
🔍 إجمالي عمليات البحث: {stats['total_searches']}
📢 قنوات الاشتراك الإجباري: {stats['total_channels']}
✅ المستخدمون النشطون (30 يوم): {stats['active_users']}"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text, reply_markup=reply_markup)
    
    def setup_handlers(self):
        """Setup bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.verify_subscription, pattern="^verify_subscription$"))
        self.application.add_handler(CallbackQueryHandler(self.search_type_menu, pattern="^search_type_menu$"))
        self.application.add_handler(CallbackQueryHandler(self.select_search_type, pattern="^select_type_"))
        self.application.add_handler(CallbackQueryHandler(self.start_search, pattern="^start_search$"))
        self.application.add_handler(CallbackQueryHandler(self.start_typed_search, pattern="^start_typed_search$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_navigation, pattern="^nav_"))
        self.application.add_handler(CallbackQueryHandler(self.select_result, pattern="^select_result_"))
        self.application.add_handler(CallbackQueryHandler(self.back_to_main, pattern="^back_to_main$"))
        self.application.add_handler(CallbackQueryHandler(self.admin_stats, pattern="^admin_stats$"))
        
        # Message handler for search queries
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_search_query))

def main():
    """Main function"""
    try:
        # Initialize database
        init_db()
        
        # Create bot instance
        bot = TelegramBot()
        
        # Create application with conflict handling and better settings
        bot.application = (
            Application.builder()
            .token(BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )
        
        # Setup handlers
        bot.setup_handlers()
        
        logger.info("Starting bot...")
        
        # Start polling with better conflict handling
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Bot startup attempt {retry_count + 1}/{max_retries}")
                bot.application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                    poll_interval=2.0,
                    timeout=30,
                    bootstrap_retries=3,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                # If we reach here, polling started successfully
                break
                
            except telegram.error.Conflict as e:
                retry_count += 1
                logger.warning(f"Conflict detected (attempt {retry_count}): {e}")
                if retry_count < max_retries:
                    wait_time = retry_count * 10
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries reached. Another bot instance might be running.")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")
                raise
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main()