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

# Telegram bot handlers
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

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = update.message.text.strip()
    logger.info(f"Received name from user {user_id}: {name}")

    if not name:
        await update.message.reply_text(f"Arre, naam toh btao! {get_emoji('error')} Kuch cool sa naam daal do!")
        return NAME

    context.user_data['name'] = name
    await update.message.reply_text(
        f"Acha, {name}, badhiya choice! {get_emoji('welcome')} "
        "Ab apna 10-digit phone number bhejo, jaise 9876543210. (+91 apne aap add ho jayega!)"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    phone = update.message.text.strip()
    logger.info(f"Received phone from user {user_id}: {phone}")

    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text(
            f"Arre, phone number 10 digits ka hona chahiye! {get_emoji('error')} "
            "Sirf numbers daal do, jaise 9876543210."
        )
        return PHONE

    formatted_phone = f"+91{phone}"
    logger.info(f"Formatted phone number for user {user_id}: {formatted_phone}")

    for uid, data in user_index.items():
        user_file = os.path.join(USER_DATA_DIR, f"user_{data['user_number']}.json")
        with open(user_file, 'r') as f:
            user_data = json.load(f)
        if user_data['phone_number'] == formatted_phone:
            await update.message.reply_text(
                f"Yeh number (+91{phone}) toh pehle se hai! {get_emoji('error')} Koi naya number try karo!"
            )
            return PHONE

    user_number = str(len(user_index) + 1)
    user_index[user_id] = {'user_number': user_number}

    user_data = {
        'name': context.user_data['name'],
        'phone_number': formatted_phone,
        'chat_history': [{"role": "system", "content": SYSTEM_PROMPT}]
    }
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    with open(user_file, 'w') as f:
        json.dump(user_data, f, indent=4)

    with open(USER_INDEX_FILE, 'w') as f:
        json.dump(user_index, f, indent=4)
    logger.info(f"User {user_id} signed up with user number {user_number}: {user_data}")

    welcome_message = (
        f"Hlo {context.user_data['name']}, signup ho gaya, swagat hai TaniGPT mein! "
        f"Apka user number hai {user_number}. Ab bol, kya scene hai? {get_emoji('welcome')}"
    )
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END

async def cancel_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Signup cancel kar diya, bro! {get_emoji('success')} Dobara try karo with /start!"
    )
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    logger.info(f"Received /admin command from user {user_id}")

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text(
            f"Sorry bro, yeh admin wala scene sirf boss ke liye hai! {get_emoji('admin')}"
        )
        return ConversationHandler.END

    await update.message.reply_text(f"Admin password daal do, boss! {get_emoji('admin')}")
    return PASSWORD

async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    password = update.message.text.strip()
    logger.info(f"Received password attempt from user {user_id}")

    if password != ADMIN_PASSWORD:
        await update.message.reply_text(
            f"Galat password, bro! {get_emoji('error')} Dobara try kar ya /cancel kar!"
        )
        return PASSWORD

    keyboard = [
        ["Users", "History"],
        ["Delete User", "Exit"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Welcome to TaniGPT Admin Panel, boss! {get_emoji('admin')} Kya karna hai?",
        reply_markup=reply_markup
    )
    return MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    choice = update.message.text.strip()
    logger.info(f"Admin menu choice from user {user_id}: {choice}")

    if choice == "Exit":
        await update.message.reply_text(
            f"Admin panel se exit kar diya, boss! {get_emoji('success')}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    elif choice == "Users":
        if not user_index:
            await update.message.reply_text(f"Abhi koi users nahi hain, bro! {get_emoji('error')}")
        else:
            user_list = "Registered Users:\n"
            for uid, data in user_index.items():
                user_file = os.path.join(USER_DATA_DIR, f"user_{data['user_number']}.json")
                with open(user_file, 'r') as f:
                    user_data = json.load(f)
                user_list += (
                    f"User Number: {data['user_number']}\n"
                    f"Telegram ID: {uid}\n"
                    f"Name: {user_data['name']}\n"
                    f"Phone: {user_data['phone_number']}\n\n"
                )
            await update.message.reply_text(user_list)

    elif choice == "History":
        await update.message.reply_text(f"Kis user ka history dekhna hai? User number daal do: {get_emoji('admin')}")
        return VIEW_HISTORY

    elif choice == "Delete User":
        await update.message.reply_text(f"Kis user ko delete karna hai? User number daal do: {get_emoji('admin')}")
        return DELETE_USER

    keyboard = [
        ["Users", "History"],
        ["Delete User", "Exit"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai, boss? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def view_user_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_number = update.message.text.strip()
    logger.info(f"Received user number {user_number} for history from user {user_id}")

    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    if not os.path.exists(user_file):
        await update.message.reply_text(f"Yeh user number galat hai, bro! {get_emoji('error')}")
        return MENU

    with open(user_file, 'r') as f:
        user_data = json.load(f)

    history = user_data.get('chat_history', [])
    if len(history) <= 1:
        await update.message.reply_text(
            f"User {user_number} ka koi history nahi hai, boss! {get_emoji('error')}"
        )
    else:
        history_text = f"Chat History for User {user_number} ({user_data['name']}):\n\n"
        for msg in history:
            if msg['role'] == 'system':
                continue
            role = "User" if msg['role'] == 'user' else "TaniGPT"
            history_text += f"{role}: {msg['content']}\n\n"
        await update.message.reply_text(history_text)

    keyboard = [
        ["Users", "History"],
        ["Delete User", "Exit"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai, boss? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_number = update.message.text.strip()
    logger.info(f"Received user number {user_number} for deletion from user {user_id}")

    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    if not os.path.exists(user_file):
        await update.message.reply_text(f"Yeh user number galat hai, bro! {get_emoji('error')}")
        return MENU

    user_id_to_delete = None
    for uid, data in list(user_index.items()):
        if data['user_number'] == user_number:
            user_id_to_delete = uid
            break

    if user_id_to_delete:
        del user_index[user_id_to_delete]
        with open(USER_INDEX_FILE, 'w') as f:
            json.dump(user_index, f, indent=4)

    os.remove(user_file)
    await update.message.reply_text(f"User {user_number} delete ho gaya, boss! {get_emoji('success')}")

    keyboard = [
        ["Users", "History"],
        ["Delete User", "Exit"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai, boss? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Admin panel se exit kar diya, boss! {get_emoji('success')}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "Welcome to *TaniGPT*, a sophisticated AI-powered chatbot crafted by *Tnix AI* for Telegram. "
        "Engineered with advanced technology, TaniGPT delivers seamless, engaging conversations tailored to diverse user needs. "
        "Communicating in English with a professional yet approachable tone, it leverages cutting-edge natural language processing to ensure precise, meaningful dialogue. "
        "TaniGPT embodies Tnix AI’s commitment to innovation, serving as a reliable digital companion that enhances user interaction within Telegram’s dynamic ecosystem."
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    logger.info(f"Clearing history for user {user_id}")

    if user_id not in user_index:
        await update.message.reply_text(f"Pehle signup karo, bro! {get_emoji('error')} Use /start.")
        return

    user_number = user_index[user_id]['user_number']
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    with open(user_file, 'r') as f:
        user_data = json.load(f)
    user_data['chat_history'] = [{"role": "system", "content": SYSTEM_PROMPT}]
    with open(user_file, 'w') as f:
        json.dump(user_data, f, indent=4)
    await update.message.reply_text(
        f"Hlo {user_data['name']}, tera history clear ho gaya! {get_emoji('success')}"
    )

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
