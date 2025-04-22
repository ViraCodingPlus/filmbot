import os
import logging
import tempfile
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import video_search
from datetime import datetime

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define command handlers
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text(f'سلام {user.mention_html()}!\n'
                              f'به ربات جستجوی فیلم و سریال خوش آمدید.\n'
                              f'برای جستجو، نام فیلم یا سریال را بنویسید.\n'
                              f'برای دیدن لیست ژانرها، دستور /genres را وارد کنید.',
                              parse_mode='HTML')

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('برای جستجوی فیلم یا سریال، نام آن را وارد کنید.\n'
                             'دستورات موجود:\n'
                             '/start - شروع کار با ربات\n'
                             '/help - نمایش راهنما\n'
                             '/genres - نمایش لیست ژانرها\n'
                             '/countries - نمایش لیست کشورها\n'
                             '/search [نام] --type [movie|series] --genre [id] - جستجوی پیشرفته')

def list_genres(update: Update, context: CallbackContext) -> None:
    """List all available genres with buttons."""
    genres, _ = video_search.load_json_data()
    
    # Create buttons for genres
    keyboard = []
    row = []
    for i, genre in enumerate(genres):
        genre_id = genre.get('id')
        genre_title = genre.get('title')
        callback_data = f"genre_{genre_id}"
        
        # Add 3 buttons per row
        if i % 3 == 0 and i > 0:
            keyboard.append(row)
            row = []
        
        row.append(InlineKeyboardButton(genre_title, callback_data=callback_data))
    
    # Add the last row if not empty
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('لطفاً یک ژانر انتخاب کنید:', reply_markup=reply_markup)

def list_countries(update: Update, context: CallbackContext) -> None:
    """List all available countries with buttons."""
    _, countries = video_search.load_json_data()
    
    # Create buttons for countries (3 per row)
    keyboard = []
    row = []
    for i, country in enumerate(countries):
        country_id = country.get('id')
        country_title = country.get('title')
        callback_data = f"country_{country_id}"
        
        # Add 3 buttons per row
        if i % 3 == 0 and i > 0:
            keyboard.append(row)
            row = []
        
        row.append(InlineKeyboardButton(country_title, callback_data=callback_data))
    
    # Add the last row if not empty
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('لطفاً یک کشور انتخاب کنید:', reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("genre_"):
        genre_id = callback_data.split("_")[1]
        context.user_data['genre_id'] = int(genre_id)
        query.edit_message_text(text=f"ژانر انتخاب شد. اکنون نام فیلم یا سریال را وارد کنید.")
    
    elif callback_data.startswith("country_"):
        country_id = callback_data.split("_")[1]
        context.user_data['country_id'] = int(country_id)
        query.edit_message_text(text=f"کشور انتخاب شد. اکنون نام فیلم یا سریال را وارد کنید.")
    
    elif callback_data.startswith("type_"):
        content_type = callback_data.split("_")[1]
        context.user_data['content_type'] = content_type
        query.edit_message_text(text=f"نوع محتوا انتخاب شد.")
        
        # Check if there's a pending search
        if 'pending_search' in context.user_data:
            search_query = context.user_data.pop('pending_search')
            perform_search(update, context, search_query, content_type, 
                          context.user_data.get('genre_id'), 
                          context.user_data.get('country_id'))

def advanced_search(update: Update, context: CallbackContext) -> None:
    """Handle advanced search command with arguments."""
    args = context.args
    
    if not args:
        update.message.reply_text('لطفاً عبارت جستجو را وارد کنید.\n'
                                 'مثال: /search عنوان فیلم --type movie --genre 28')
        return
    
    query = []
    content_type = None
    genre_id = None
    country_id = None
    
    i = 0
    while i < len(args):
        if args[i] == '--type' and i + 1 < len(args):
            content_type = args[i + 1]
            i += 2
        elif args[i] == '--genre' and i + 1 < len(args):
            try:
                genre_id = int(args[i + 1])
                i += 2
            except ValueError:
                update.message.reply_text('شناسه ژانر باید یک عدد باشد.')
                return
        elif args[i] == '--country' and i + 1 < len(args):
            try:
                country_id = int(args[i + 1])
                i += 2
            except ValueError:
                update.message.reply_text('شناسه کشور باید یک عدد باشد.')
                return
        else:
            query.append(args[i])
            i += 1
    
    search_query = ' '.join(query)
    perform_search(update, context, search_query, content_type, genre_id, country_id)

def search(update: Update, context: CallbackContext) -> None:
    """Search for movies and series based on message text."""
    search_query = update.message.text
    
    # Get filters from user_data if available
    genre_id = context.user_data.get('genre_id')
    country_id = context.user_data.get('country_id')
    content_type = context.user_data.get('content_type')
    
    # Clear user_data after using it
    if 'genre_id' in context.user_data:
        del context.user_data['genre_id']
    if 'country_id' in context.user_data:
        del context.user_data['country_id']
    if 'content_type' in context.user_data:
        del context.user_data['content_type']
    
    # Ask user to select content type if not specified
    if not content_type:
        keyboard = [
            [
                InlineKeyboardButton("فیلم", callback_data="type_movie"),
                InlineKeyboardButton("سریال", callback_data="type_series"),
                InlineKeyboardButton("هر دو", callback_data="type_both")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('لطفاً نوع محتوا را انتخاب کنید:', reply_markup=reply_markup)
        
        # Save the search query for later use
        context.user_data['pending_search'] = search_query
        return
    
    perform_search(update, context, search_query, content_type, genre_id, country_id)

def perform_search(update: Update, context: CallbackContext, query, content_type=None, genre_id=None, country_id=None) -> None:
    """Perform the actual search and send results."""
    message = update.message or update.callback_query.message
    message.reply_text(f'در حال جستجوی "{query}"... لطفاً صبر کنید.')
    
    results = []
    
    if not content_type or content_type in ['movie', 'both']:
        # Search in movies
        movie_results = video_search.search_movies(query, genre_id, country_id)
        results.extend(movie_results)
    
    if not content_type or content_type in ['series', 'both']:
        # Search in series
        series_results = video_search.search_series(query, genre_id, country_id)
        results.extend(series_results)
    
    if not results:
        message.reply_text("متأسفانه نتیجه‌ای یافت نشد.")
        return
    
    # Limit results to avoid overwhelming Telegram
    MAX_RESULTS = 5
    if len(results) > MAX_RESULTS:
        message.reply_text(f"تعداد {len(results)} نتیجه یافت شد. نمایش {MAX_RESULTS} نتیجه اول:")
        results = results[:MAX_RESULTS]
    else:
        message.reply_text(f"تعداد {len(results)} نتیجه یافت شد:")
    
    # Send results
    for result in results:
        title = result.get('title', 'بدون عنوان')
        year = result.get('year', '')
        genre = result.get('genre', '')
        description = result.get('description', '')
        content_type = result.get('type', '')
        poster = result.get('poster', '')
        
        caption = f"🎬 *{title}*\n"
        caption += f"📅 سال: {year}\n"
        caption += f"🎭 ژانر: {genre}\n"
        caption += f"📺 نوع: {content_type}\n\n"
        
        # Add description if available
        if description:
            # If description is too long, truncate it
            if len(description) > 800:
                short_desc = description[:800] + "..."
                caption += f"📝 توضیحات: {short_desc}\n\n"
            else:
                caption += f"📝 توضیحات: {description}\n\n"
        
        sources = result.get('sources', [])
        if sources:
            caption += "🔗 منابع:\n"
            for i, source in enumerate(sources[:5]):  # Limit to 5 sources to avoid message length issues
                parsed_source = video_search.parse_source(source)
                if parsed_source:
                    source_type = parsed_source.get('type', 'نامشخص')
                    quality = parsed_source.get('quality', 'نامشخص')
                    url = parsed_source.get('url', '')
                    
                    caption += f"{i+1}. [{quality} - {source_type}]({url})\n"
            
            if len(sources) > 5:
                caption += f"و {len(sources) - 5} منبع دیگر...\n"
        
        # Send poster if available, otherwise just send the message
        if poster:
            try:
                message.reply_photo(photo=poster, caption=caption, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                # If the error is about the message being too long, truncate it
                if "message is too long" in str(e).lower():
                    # Create a shorter caption without description
                    short_caption = f"🎬 *{title}*\n"
                    short_caption += f"📅 سال: {year}\n"
                    short_caption += f"🎭 ژانر: {genre}\n"
                    short_caption += f"📺 نوع: {content_type}\n\n"
                    
                    # Add sources with shorter links
                    if sources:
                        short_caption += "🔗 منابع:\n"
                        for i, source in enumerate(sources[:3]):  # Only 3 sources
                            parsed_source = video_search.parse_source(source)
                            if parsed_source:
                                source_type = parsed_source.get('type', 'نامشخص')
                                quality = parsed_source.get('quality', 'نامشخص')
                                url = parsed_source.get('url', '')
                                short_caption += f"{i+1}. {quality} - {source_type}\n"
                        
                    try:
                        # Try sending the photo with the shorter caption
                        message.reply_photo(photo=poster, caption=short_caption, parse_mode='Markdown')
                        
                        # Send the description separately if it's available
                        if description:
                            desc_message = f"*توضیحات {title}:*\n\n{description}"
                            if len(desc_message) > 4000:  # Telegram message limit
                                desc_message = desc_message[:3997] + "..."
                            message.reply_text(desc_message, parse_mode='Markdown')
                    except Exception as e2:
                        logger.error(f"Error sending shortened message: {e2}")
                        message.reply_text(f"*{title}* - اطلاعات بیشتر را نمی‌توان نمایش داد.", parse_mode='Markdown')
                else:
                    message.reply_text(caption, parse_mode='Markdown', disable_web_page_preview=False)
        else:
            try:
                message.reply_text(caption, parse_mode='Markdown', disable_web_page_preview=False)
            except Exception as e:
                logger.error(f"Error sending text message: {e}")
                
                # If the error is about the message being too long, split it
                if "message is too long" in str(e).lower():
                    # Send basic info first
                    basic_info = f"🎬 *{title}*\n"
                    basic_info += f"📅 سال: {year}\n"
                    basic_info += f"🎭 ژانر: {genre}\n"
                    basic_info += f"📺 نوع: {content_type}\n"
                    
                    message.reply_text(basic_info, parse_mode='Markdown')
                    
                    # Send description separately if available
                    if description:
                        desc_message = f"*توضیحات {title}:*\n\n{description}"
                        if len(desc_message) > 4000:  # Telegram message limit
                            desc_message = desc_message[:3997] + "..."
                        message.reply_text(desc_message, parse_mode='Markdown')
                        
                    # Send sources separately if available
                    if sources:
                        sources_message = f"*منابع {title}:*\n\n"
                        for i, source in enumerate(sources[:5]):
                            parsed_source = video_search.parse_source(source)
                            if parsed_source:
                                source_type = parsed_source.get('type', 'نامشخص')
                                quality = parsed_source.get('quality', 'نامشخص')
                                url = parsed_source.get('url', '')
                                sources_message += f"{i+1}. [{quality} - {source_type}]({url})\n"
                        
                        message.reply_text(sources_message, parse_mode='Markdown')
                else:
                    message.reply_text(f"*{title}* - خطا در نمایش اطلاعات کامل.", parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    # Get the token from environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token or token == "YOUR_TOKEN":
        print("Please set your TELEGRAM_BOT_TOKEN in the .env file")
        return
    
    # Create the Updater and pass it your bot's token
    updater = Updater(token)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("genres", list_genres))
    dispatcher.add_handler(CommandHandler("countries", list_countries))
    dispatcher.add_handler(CommandHandler("search", advanced_search))
    
    # Register callback query handler for button presses
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    # Register message handler for search queries
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search))
    
    # Start the Bot
    print(f"Starting Telegram bot...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main() 