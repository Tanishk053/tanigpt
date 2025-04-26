import os
import re
import logging
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, Response
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
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8443))

if not MISTRAL_API_KEY or not TELEGRAM_BOT_TOKEN:
    logger.error("Missing MISTRAL_API_KEY or TELEGRAM_BOT_TOKEN in .env")
    raise ValueError("Missing MISTRAL_API_KEY or TELEGRAM_BOT_TOKEN in .env")

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
NAME, PHONE, CONFIRM = range(3)

# Admin panel states
PASSWORD, MENU, VIEW_HISTORY, DELETE_USER = range(4)

# Emoji selection
def get_emoji(context_type, message_content=""):
    emoji_map = {
        "welcome": "🚀",
        "error": "😅",
        "admin": "🔐",
        "success": "✅",
        "general": "😊",
        "date": "📅",
        "tanishk": "🎵"
    }
    if context_type == "general" and "date" in message_content.lower():
        return emoji_map["date"]
    if context_type == "general" and "tanishk sharma" in message_content.lower():
        return emoji_map["tanishk"]
    return emoji_map.get(context_type, "😊")

# Flask app for webhook
flask_app = Flask(__name__)

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    logger.info(f"Received /start command from user {user_id}")

    if user_id in user_index:
        user_number = user_index[user_id]['user_number']
        await update.message.reply_text(
            f"Welcome back to TaniGPT! Your user number is {user_number}. Kya baat karna hai? {get_emoji('welcome')}"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Yo, swagat hai TaniGPT mein! {get_emoji('welcome')} "
        "Chalo signup karte hain. Apna naam bhejo (sirf letters allowed)!"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = update.message.text.strip()
    logger.info(f"Received name from user {user_id}: {name}")

    if not re.match(r"^[A-Za-z\s]+$", name):
        await update.message.reply_text(
            f"Arre, naam mein sirf letters aur spaces hone chahiye! {get_emoji('error')} Try again!"
        )
        return NAME

    context.user_data['name'] = name
    await update.message.reply_text(
        f"Badhiya naam, {name}! {get_emoji('welcome')} "
        "Ab apna 10-digit phone number bhejo (like 9876543210)."
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    phone = update.message.text.strip()
    logger.info(f"Received phone from user {user_id}: {phone}")

    if not re.match(r"^\d{10}$", phone):
        await update.message.reply_text(
            f"Phone number 10 digits ka hona chahiye, no spaces ya symbols! {get_emoji('error')} Try again."
        )
        return PHONE

    formatted_phone = f"+91{phone}"
    for uid, data in user_index.items():
        user_file = os.path.join(USER_DATA_DIR, f"user_{data['user_number']}.json")
        try:
            with open(user_file, 'r') as f:
                user_data = json.load(f)
            if user_data['phone_number'] == formatted_phone:
                await update.message.reply_text(
                    f"Yeh number (+91{phone}) already registered hai! {get_emoji('error')} Naya number daal."
                )
                return PHONE
        except Exception as e:
            logger.error(f"Error reading user file {user_file}: {str(e)}")
            continue

    context.user_data['phone'] = formatted_phone
    keyboard = [["Confirm"], ["Edit"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Details:\nName: {context.user_data['name']}\nPhone: {formatted_phone}\n"
        f"Theek hai? Confirm karo ya edit! {get_emoji('general')}",
        reply_markup=reply_markup
    )
    return CONFIRM

async def confirm_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    choice = update.message.text.strip().lower()
    logger.info(f"Received signup confirmation choice from user {user_id}: {choice}")

    if choice == "edit":
        await update.message.reply_text(
            f"Chalo, naam se shuru karte hain! Naya naam bhejo. {get_emoji('general')}",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME

    if choice != "confirm":
        await update.message.reply_text(
            f"Arre, Confirm ya Edit select karo! {get_emoji('error')}",
            reply_markup=ReplyKeyboardMarkup([["Confirm"], ["Edit"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return CONFIRM

    user_number = str(len(user_index) + 1)
    user_index[user_id] = {'user_number': user_number}

    user_data = {
        'name': context.user_data['name'],
        'phone_number': context.user_data['phone'],
        'chat_history': [{"role": "system", "content": SYSTEM_PROMPT}]
    }
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    try:
        with open(user_file, 'w') as f:
            json.dump(user_data, f, indent=4)
        with open(USER_INDEX_FILE, 'w') as f:
            json.dump(user_index, f, indent=4)
        logger.info(f"User {user_id} signed up with user number {user_number}: {user_data}")
    except Exception as e:
        logger.error(f"Error saving user data for {user_id}: {str(e)}")
        await update.message.reply_text(
            f"Kuch galat ho gaya signup ke time pe! {get_emoji('error')} Try again with /start."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Signup done! TaniGPT mein welcome, your user number is {user_number}. Ab kya scene hai? {get_emoji('welcome')}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancel_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Signup cancel kiya! {get_emoji('success')} /start se dobara try kar."
    )
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    logger.info(f"Received /admin command from user {user_id}")

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text(
            f"Sorry, admin access sirf boss ke liye! {get_emoji('admin')}"
        )
        return ConversationHandler.END

    await update.message.reply_text(f"Admin password daal do! {get_emoji('admin')}")
    return PASSWORD

async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    password = update.message.text.strip()
    logger.info(f"Received password attempt from user {user_id}")

    if password != ADMIN_PASSWORD:
        await update.message.reply_text(
            f"Galat password! {get_emoji('error')} Try again ya /cancel kar."
        )
        return PASSWORD

    keyboard = [["Users", "History"], ["Delete User", "Exit"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"TaniGPT Admin Panel mein welcome! Kya karna hai? {get_emoji('admin')}",
        reply_markup=reply_markup
    )
    return MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    choice = update.message.text.strip()
    logger.info(f"Admin menu choice from user {user_id}: {choice}")

    if choice == "Exit":
        await update.message.reply_text(
            f"Admin panel se exit kiya! {get_emoji('success')}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    elif choice == "Users":
        if not user_index:
            await update.message.reply_text(f"Koi users nahi hain! {get_emoji('error')}")
        else:
            user_list = "Registered Users:\n"
            for uid, data in user_index.items():
                user_file = os.path.join(USER_DATA_DIR, f"user_{data['user_number']}.json")
                try:
                    with open(user_file, 'r') as f:
                        user_data = json.load(f)
                    user_list += (
                        f"User Number: {data['user_number']}\n"
                        f"Telegram ID: {uid}\n"
                        f"Name: {user_data['name']}\n"
                        f"Phone: {user_data['phone_number']}\n\n"
                    )
                except Exception as e:
                    logger.error(f"Error reading user file {user_file}: {str(e)}")
                    user_list += f"User Number: {data['user_number']} - Error loading data\n\n"
            await update.message.reply_text(user_list)

    elif choice == "History":
        await update.message.reply_text(f"Kis user ka history? User number daal: {get_emoji('admin')}")
        return VIEW_HISTORY

    elif choice == "Delete User":
        await update.message.reply_text(f"Kis user ko delete? User number daal: {get_emoji('admin')}")
        return DELETE_USER

    keyboard = [["Users", "History"], ["Delete User", "Exit"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def view_user_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_number = update.message.text.strip()
    logger.info(f"Received user number {user_number} for history from user {user_id}")

    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    if not os.path.exists(user_file):
        await update.message.reply_text(f"Galat user number! {get_emoji('error')}")
        keyboard = [["Users", "History"], ["Delete User", "Exit"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
        return MENU

    try:
        with open(user_file, 'r') as f:
            user_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading user file {user_file}: {str(e)}")
        await update.message.reply_text(f"Error loading history! {get_emoji('error')}")
        keyboard = [["Users", "History"], ["Delete User", "Exit"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
        return MENU

    history = user_data.get('chat_history', [])
    if len(history) <= 1:  # Only system prompt
        await update.message.reply_text(f"User {user_number} ka koi history nahi! {get_emoji('error')}")
    else:
        history_text = f"Chat History for User {user_number} ({user_data['name']}):\n\n"
        for msg in history:
            if msg['role'] == 'system':
                continue
            role = "User" if msg['role'] == 'user' else "TaniGPT"
            content = msg['content'].replace('\n', ' ')  # Avoid formatting issues in Telegram
            history_text += f"{role}: {content}\n\n"
        # Telegram has a message length limit, so split if necessary
        if len(history_text) > 4096:
            parts = [history_text[i:i + 4096] for i in range(0, len(history_text), 4096)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(history_text)

    keyboard = [["Users", "History"], ["Delete User", "Exit"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_number = update.message.text.strip()
    logger.info(f"Received user number {user_number} for deletion from user {user_id}")

    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    if not os.path.exists(user_file):
        await update.message.reply_text(f"Galat user number! {get_emoji('error')}")
        keyboard = [["Users", "History"], ["Delete User", "Exit"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
        return MENU

    try:
        user_id_to_delete = next((uid for uid, data in user_index.items() if data['user_number'] == user_number), None)
        if user_id_to_delete:
            del user_index[user_id_to_delete]
            with open(USER_INDEX_FILE, 'w') as f:
                json.dump(user_index, f, indent=4)
        os.remove(user_file)
        await update.message.reply_text(f"User {user_number} deleted! {get_emoji('success')}")
    except Exception as e:
        logger.error(f"Error deleting user {user_number}: {str(e)}")
        await update.message.reply_text(f"Error deleting user! {get_emoji('error')}")

    keyboard = [["Users", "History"], ["Delete User", "Exit"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"Ab kya karna hai? {get_emoji('admin')}", reply_markup=reply_markup)
    return MENU

async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Admin panel se exit kiya! {get_emoji('success')}",
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
        await update.message.reply_text(f"Pehle signup kar! {get_emoji('error')} Use /start.")
        return

    user_number = user_index[user_id]['user_number']
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    try:
        with open(user_file, 'r') as f:
            user_data = json.load(f)
        user_data['chat_history'] = [{"role": "system", "content": SYSTEM_PROMPT}]
        with open(user_file, 'w') as f:
            json.dump(user_data, f, indent=4)
        await update.message.reply_text(f"History cleared! {get_emoji('success')}")
    except Exception as e:
        logger.error(f"Error clearing history for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Error clearing history! {get_emoji('error')}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_message = update.message.text.lower().strip()
    logger.info(f"Received text from user {user_id}: {user_message}")

    if user_id not in user_index:
        await update.message.reply_text(f"Pehle signup kar! {get_emoji('error')} Use /start.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    user_number = user_index[user_id]['user_number']
    user_file = os.path.join(USER_DATA_DIR, f"user_{user_number}.json")
    try:
        with open(user_file, 'r') as f:
            user_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading user file {user_file}: {str(e)}")
        await update.message.reply_text(f"Error loading your data! {get_emoji('error')}")
        return

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
        # Split long messages to avoid Telegram's 4096 character limit
        if len(response) > 4096:
            parts = [response[i:i + 4096] for i in range(0, len(response), 4096)]
            for part in parts:
                await update.message.reply_text(f"{part} {emoji}")
        else:
            await update.message.reply_text(f"{response} {emoji}")

    except Exception as e:
        logger.error(f"Error in text processing: {str(e)}")
        emoji = get_emoji("error")
        await update.message.reply_text(f"Kuch galat ho gaya: {str(e)} {emoji}")

# Flask webhook endpoint
@flask_app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    await app.process_update(update)
    return Response(status=200)

def main():
    global app
    logger.info("Starting TaniGPT Bot...")
    try:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Signup conversation handler
        signup_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_signup)],
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

        # Run mode: Webhook
        if WEBHOOK_URL:
            logger.info(f"Setting up webhook at {WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}")
            # Set webhook
            app.bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}")
            # Run Flask app
            flask_app.run(host="0.0.0.0", port=PORT, debug=False)
            logger.info(f"Bot running in webhook mode on port {PORT}")
        else:
            logger.info("Bot running in polling mode")
            app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
