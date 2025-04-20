import os
import logging
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction
from mistralai import Mistral

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Setup API keys and tokens with fallback
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "tnixai2025")

if not MISTRAL_API_KEY or not TELEGRAM_BOT_TOKEN:
    logger.error("Missing MISTRAL_API_KEY or TELEGRAM_BOT_TOKEN in .env. Please check your configuration.")
    raise ValueError("Missing MISTRAL_API_KEY or TELEGRAM_BOT_TOKEN in .env. Set them in your .env file or environment variables.")

# Admin user ID
ADMIN_USER_ID = "5842560424"

# Mistral AI client
MODEL = "mistral-large-latest"
try:
    mistral_client = Mistral(api_key=MISTRAL_API_KEY)
    logger.info("Mistral AI client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Mistral client: {str(e)}")
    raise

# User data directory
USER_DATA_DIR = "user_data"
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

# User index file
USER_INDEX_FILE = "user_index.json"
user_index = {}
if os.path.exists(USER_INDEX_FILE):
    with open(USER_INDEX_FILE, 'r') as f:
        user_index = json.load(f)

# System prompt
SYSTEM_PROMPT = (
    "You are TaniGPT, powered by Tnix AI. "
    "Respond in Hinglish or English only, keeping a friendly and conversational tone. "
    "Keep responses relevant and engaging."
)

# Signup states
NAME, PHONE = range(2)

# Admin panel states
PASSWORD, MENU, VIEW_HISTORY, DELETE_USER = range(4)

# Emoji selection based on context
def get_emoji(context_type, message_content=""):
    emoji_map = {
        "welcome": ["😎", "🚀", "✨"],
        "error": ["😬", "😅", "🙈"],
        "admin": ["👑", "😎", "🔐"],
        "success": ["✅", "🎉", "👍"],
        "general": ["😊", "👍", "🤗"],
        "date": ["📅", "🕒"],
        "tanishk": ["🎤", "🎵"]
    }
    if context_type == "general" and "date" in message_content.lower():
        return emoji_map["date"][0]
    if context_type == "general" and "tanishk sharma" in message_content.lower():
        return emoji_map["tanishk"][0]
    return emoji_map.get(context_type, ["😊"])[0]

# Telegram bot handlers (unchanged from original, included for completeness)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    logger.info(f"Received /start command from user {user_id}")

    if user_id in user_index:
        user_number = user_index[user_id]['user_number']
        user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
        with open(user_file, 'r') as f:
            user_data = json.load(f)
        welcome_message = (
            f"Hlo {user_data['name']}, welcome back to TaniGPT! "
            f"Apka user number hai {user_number}. Chalo, kya baat karna hai? {get_emoji('welcome')}"
        )
        await update.message.reply_text(welcome_message)
        return ConversationHandler.END

    await update.message.reply_text(
        f"Yo bro, TaniGPT mein swagat hai! {get_emoji('welcome')} "
        "Pehle signup karo, bada maza aayega! Apna naam bhejo, cool sa!"
    )
    return NAME

# ... (other handlers like get_name, get_phone, etc., remain unchanged for brevity)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_message = update.message.text.lower().strip()
    logger.info(f"Received text from user {user_id}: {user_message}")

    if user_id not in user_index:
        await update.message.reply_text(f"Pehle signup karo, bro! {get_emoji('error')} Use /start.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    user_number = user_index[user_id]['user_number']
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    with open(user_file, 'r') as f:
        user_data = json.load(f)

    user_name = user_data['name']
    user_data['chat_history'].append({"role": "user", "content": user_message})

    MAX_HISTORY = 10
    if len(user_data['chat_history']) > MAX_HISTORY:
        user_data['chat_history'] = user_data['chat_history'][-MAX_HISTORY:]

    try:
        date_keywords = ["date", "today", "current date", "what's the date", "aaj ka din"]
        tanishk_keywords = ["tanishk sharma", "who is tanishk"]
        if any(keyword in user_message for keyword in date_keywords):
            current_date = datetime.now().strftime("Today is %A, %B %d, %Y")
            response = current_date
            logger.info(f"Date query detected, responding: {response}")
        elif any(keyword in user_message for keyword in tanishk_keywords):
            response = (
                "Tanishk Sharma is the Founder of Tnix AI. He is a music producer, casting director, singer, and writer. "
                "His songs include 'Lost in My Feeling', '06 October Forever and Always', and 'WQAT'."
            )
            logger.info("Tanishk Sharma query detected, responding with predefined info")
        else:
            start_time = time.time()
            response = mistral_client.chat.complete(
                model=MODEL,
                messages=user_data['chat_history']
            ).choices[0].message.content
            end_time = time.time()
            logger.info(f"Mistral AI response time: {end_time - start_time:.2f} seconds")

        user_data['chat_history'].append({"role": "assistant", "content": response})

        with open(user_file, 'w') as f:
            json.dump(user_data, f, indent=4)

        emoji = get_emoji("general", user_message)
        personalized_response = f"Hlo {user_name}, {response} {emoji}"
        await update.message.reply_text(personalized_response)

    except Exception as e:
        logger.error(f"Error in text processing: {str(e)}")
        emoji = get_emoji("error")
        await update.message.reply_text(f"Hlo {user_name}, kuch galat ho gaya: {str(e)} {emoji}")

def main():
    logger.info("Starting TaniGPT Bot...")
    try:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Signup conversation handler
        signup_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            },
            fallbacks=[CommandHandler("cancel", cancel_signup)],
        )

        # Admin conversation handler
        admin_handler = ConversationHandler(
            entry_points=[CommandHandler("admin", admin_panel)],
            states={
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password)],
                MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)],
                VIEW_HISTORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_user_history)],
                DELETE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user)],
            },
            fallbacks=[CommandHandler("cancel", cancel_admin)],
        )

        # Add handlers
        app.add_handler(signup_handler)
        app.add_handler(admin_handler)
        app.add_handler(CommandHandler("about", about))
        app.add_handler(CommandHandler("clear", clear))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        # Determine run mode (polling or webhook)
        if os.environ.get("USE_WEBHOOK", "false").lower() == "true":
            port = int(os.environ.get("PORT", 8443))
            app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=TELEGRAM_BOT_TOKEN,
                webhook_url=f"https://{os.environ.get('DOMAIN')}/{TELEGRAM_BOT_TOKEN}"
            )
            logger.info(f"Bot running in webhook mode on port {port}")
        else:
            logger.info("Bot running in polling mode")
            app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
