from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
from flask_app import app, User, db  # Ensure the correct import path

# Your bot token and WebApp URL
TOKEN = '6994167772:AAEtzyhyeWecWhaWy6RpksILvVta4BQhOTY'  # Replace with your actual bot token
WEB_APP_URL = 'https://3d527cd63904.ngrok.app'  # Replace with your actual Ngrok URL

authorized_admins = [5514238536, 987654321]  # Replace with actual Telegram user IDs of admins



def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command, starts a session in the Flask app, and generates a Web App link."""
    user = update.message.from_user
    user_id = user.id

    with app.app_context():
        # Check if the user is in the database
        db_user = User.query.filter_by(telegram_id=str(user_id)).first()
        if not db_user:
            # Create a new user if they don't exist
            db_user = User(
                name=user.username or user.first_name,
                email=f"{user.username or user_id}@example.com",
                telegram_id=str(user_id)
            )
            db.session.add(db_user)
            db.session.commit()

        # At this point, db_user is still bound to the session

        # Start the session with the Flask app
        try:
            response = requests.post(f"{WEB_APP_URL}/start_session", data={
                'user_id': user_id,
                'name': db_user.name,  # Accessing attributes while within the session
                'email': db_user.email
            })

            if response.status_code == 200:
                session_data = response.json()
                session_token = session_data.get("session_token")
                web_app_url = f'{WEB_APP_URL}?telegram_id={user_id}&session_token={session_token}'
                
                # Send the Web App link
                keyboard = [
                    [InlineKeyboardButton("Open Web App", web_app=WebAppInfo(url=web_app_url))]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('Click the button below to open the Web App:', reply_markup=reply_markup)

            else:
                update.message.reply_text("Could not start the session. Please try again later.")

        except requests.exceptions.RequestException as e:
            update.message.reply_text(f"Error: {str(e)}. Please try again later.")



def admin(update: Update, context: CallbackContext) -> None:
    """Handles the /admin command, checks if the user is an authorized admin, and sends the admin login link."""
    user_id = update.message.from_user.id

    with app.app_context():  # Ensure the Flask app context is active
        # Check if the user is banned
        db_user = User.query.filter_by(telegram_id=str(user_id)).first()
        if db_user and db_user.is_banned:
            update.message.reply_text("You have been banned from accessing this bot.")
            return

    # Check if the user is authorized as an admin
    if user_id in authorized_admins:
        login_url = f"{WEB_APP_URL}/telegram_login/{user_id}"
        update.message.reply_text(f"Please log in to access the admin panel: {login_url}")
    else:
        update.message.reply_text("You are not authorized to access the admin panel.")

def run_bot():
    """Starts the Telegram bot and sets up command handlers."""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin))

    # Start polling for updates from Telegram
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    run_bot()
