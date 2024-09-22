from flask import Flask, render_template, request, jsonify, redirect, url_for, session as flask_session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import secrets
from telegram import Bot
import requests
from flask_session import Session
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


TOKEN = '6994167772:AAEtzyhyeWecWhaWy6RpksILvVta4BQhOTY'  # Replace with your actual bot token

NOWPAYMENTS_API_KEY = '3C4ZQQH-MDBM0VV-PBZGJDS-XARMZ1F'  # Replace with your actual NOWPayments API key
NOWPAYMENTS_API_URL = 'https://api.nowpayments.io/v1'

session_directory = os.path.join(os.getcwd(), 'flask_session_storage')

# Check if the directory exists, if not, create it
if not os.path.exists(session_directory):
    os.makedirs(session_directory)

# Initialize the Flask application
app = Flask(__name__)

# Set up session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = session_directory
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'
app.config['SESSION_FILE_THRESHOLD'] = 500

# Initialize the session management
Session(app)

# Other configurations
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database_name.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'Samzycrash@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'xqinvoecxtyhisvk'   # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = ('Samzycrash', 'Samzycrash@gmail.com')  # Replace with your sender info

ADMIN_EMAILS = ['Deitystudio21@gmail.com']  # Replace with admin emails

# Initialize the database
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=100.0)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    telegram_id = db.Column(db.String(120), unique=True, nullable=False)

class GameLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bet_amount = db.Column(db.Float, nullable=False)
    crash_point = db.Column(db.Float, nullable=False)
    winnings = db.Column(db.Float, nullable=False)
    result = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class DepositLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(50), nullable=False)
    pay_address = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
class WithdrawalLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

# Create database tables
with app.app_context():
    db.create_all()

# Email Utility Function
def send_email(subject, body, recipients):
    sender_email = app.config['MAIL_USERNAME']
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Connect to the SMTP server
    server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
    server.starttls()
    server.login(sender_email, app.config['MAIL_PASSWORD'])

    for recipient in recipients:
        msg['To'] = recipient
        server.sendmail(sender_email, recipient, msg.as_string())

    server.quit()

# Middleware to make session permanent
@app.before_request
def ensure_user_authenticated():
    if 'telegram_id' not in flask_session:
        telegram_id = request.args.get('telegram_id') or request.form.get('telegram_id')
        if telegram_id:
            flask_session['telegram_id'] = telegram_id
            user = User.query.filter_by(telegram_id=telegram_id).first()
            if user:
                flask_session['user_id'] = user.id
            else:
                new_user = User(
                    name=f"User_{telegram_id}",
                    email=f"{telegram_id}@example.com",
                    telegram_id=telegram_id
                )
                db.session.add(new_user)
                db.session.commit()
                flask_session['user_id'] = new_user.id
    
    # Debugging logs to verify session data
    app.logger.info(f"Session Data: user_id={flask_session.get('user_id')}, telegram_id={flask_session.get('telegram_id')}")
    if 'user_id' not in flask_session or 'telegram_id' not in flask_session:
        app.logger.warning("User session is incomplete or missing!")

# Routes
@app.route('/')
def index():
    user_id = flask_session.get('user_id')
    return render_template('index.html', user_id=user_id)

@app.route('/user_balances', methods=['GET'])
def user_balances():
    users = db.session.query(User).all()
    user_balances = [{'telegram_id': user.telegram_id, 'name': user.name, 'balance': user.balance} for user in users]
    return jsonify(user_balances)

@app.route('/start_session', methods=['POST'])
def start_session():
    telegram_id = request.form.get('user_id')
    name = request.form.get('name')
    email = request.form.get('email')

    user = User.query.filter_by(telegram_id=telegram_id).first()

    if not user:
        # Create a new user if not found
        user = User(
            name=name,
            email=email,
            telegram_id=telegram_id
        )
        db.session.add(user)
        db.session.commit()

    # Set the session data
    flask_session['user_id'] = user.id
    flask_session['telegram_id'] = user.telegram_id

    app.logger.info(f"Session Data: user_id={flask_session.get('user_id')}, telegram_id={flask_session.get('telegram_id')}")

    session_token = secrets.token_hex(16)
    return jsonify({"session_token": session_token})

@app.route('/log_game', methods=['POST'])
def log_game():
    data = request.json
    telegram_id = data.get('telegram_id')
    bet_amount = data.get('bet_amount')
    crash_point = data.get('crash_point')
    winnings = data.get('winnings')
    result = data.get('result')

    app.logger.info(f"Received log_game data: {data}")

    if None in [telegram_id, bet_amount, crash_point, winnings, result]:
        app.logger.error("Missing data in log_game request")
        return jsonify(error="Missing data"), 400

    user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        app.logger.error(f"User not found for telegram_id: {telegram_id}")
        return jsonify({"error": "User not found"}), 404

    new_log = GameLog(
        user_id=user.id,
        bet_amount=bet_amount,
        crash_point=crash_point,
        winnings=winnings,
        result=result
    )

    try:
        user.balance = float(data.get('new_balance'))
        db.session.add(new_log)
        db.session.commit()
        app.logger.info(f"Game log created and balance updated for user {telegram_id}")
        return jsonify(success=True)
    except Exception as e:
        app.logger.error(f"Error updating balance or logging game: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_game', methods=['POST'])
def start_game():
    user_id = flask_session.get('user_id')
    telegram_id = flask_session.get('telegram_id')
    
    if not user_id and not telegram_id:
        return jsonify({"error": "User not authenticated"}), 403

    # Retrieve the user from the database using either user_id or telegram_id
    user = db.session.get(User, user_id) if user_id else User.query.filter_by(telegram_id=telegram_id).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not request.is_json:
        return jsonify({"error": "Invalid request format. Expected JSON"}), 400

    # Retrieve the game data from the request
    data = request.json
    bet_amount = data.get('bet_amount')
    crash_point = data.get('crash_point')
    cashout_multiplier = data.get('cashout_multiplier')
    current_multiplier = data.get('current_multiplier')  # For manual cashout
    result = data.get('result')

    # Validate the presence of essential data
    if bet_amount is None or crash_point is None or current_multiplier is None or result is None:
        return jsonify({"error": "Missing required game data"}), 400

    try:
        bet_amount = float(bet_amount)
        crash_point = float(crash_point)
        cashout_multiplier = float(cashout_multiplier) if cashout_multiplier else None
        current_multiplier = float(current_multiplier)
    except ValueError:
        return jsonify({"error": "Invalid numeric values for bet_amount, crash_point, or multiplier"}), 400

    if bet_amount <= 0:
        return jsonify({"error": "Bet amount must be greater than zero"}), 400

    # Check if the user has sufficient balance
    if bet_amount > user.balance:
        return jsonify({"error": "Insufficient balance"}), 400

    # Deduct the bet amount once when the game starts
    user.balance -= bet_amount

    winnings = 0
    if result == 'win':
        # Use cashout_multiplier if set (automatic cashout), otherwise use current_multiplier (manual cashout)
        if cashout_multiplier and cashout_multiplier <= crash_point:
            winnings = bet_amount * cashout_multiplier  # Auto cashout based on the set multiplier
        else:
            winnings = bet_amount * current_multiplier  # Manual cashout based on the current multiplier

        # Update user balance by adding only the winnings (profit)
        user.balance += winnings

    # If the result is 'lose', no winnings and no further deduction from the balance.

    # Create a new game log entry
    new_log = GameLog(
        user_id=user.id,
        bet_amount=bet_amount,
        crash_point=crash_point,
        winnings=winnings,
        result=result
    )

    try:
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # Roll back the transaction in case of error
        return jsonify({"error": "Failed to save game log", "details": str(e)}), 500

    # Ensure the balance is rounded to two decimal places
    user.balance = round(user.balance, 2)

    # Return a response with the updated balance and log details
    return jsonify({
        "success": True,
        "new_balance": user.balance,
        "log": {
            "bet_amount": bet_amount,
            "crash_point": crash_point,
            "winnings": winnings,
            "result": result,
            "timestamp": new_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')  # Format timestamp
        }
    })




@app.route('/deposit_page', methods=['GET', 'POST'])
def deposit_page():
    user_id = flask_session.get('user_id')
    telegram_id = flask_session.get('telegram_id')

    if request.method == 'POST':
        amount = request.form.get('amount')

        if not amount or float(amount) <= 0:
            return render_template('deposit_page.html', error="Invalid amount")

        if not user_id or not telegram_id:
            return render_template('deposit_page.html', error="User not authenticated.")

        # Prepare the payment request to NOWPayments
        payload = {
            'price_amount': float(amount),
            'price_currency': 'usd',
            'pay_currency': 'usdttrc20',
            'ipn_callback_url': '',  # Update with correct URL
            'order_id': secrets.token_hex(8),
            'order_description': 'Deposit into your account'
        }

        headers = {
            'x-api-key': NOWPAYMENTS_API_KEY
        }

        response = requests.post(f'{NOWPAYMENTS_API_URL}/payment', json=payload, headers=headers)

        if response.status_code in [200, 201]:
            try:
                payment_data = response.json()
                if payment_data.get('payment_status') == 'waiting':
                   
                    new_deposit_log = DepositLog(
                        user_id=user_id,
                        amount=amount,
                        payment_status=payment_data.get('payment_status'),
                        pay_address=payment_data.get('pay_address'),
                        created_at=datetime.utcnow()
                    )
                    db.session.add(new_deposit_log)
                    db.session.commit()

                    # Send email notification to admins
                    subject = "New Deposit"
                    body = f"User {user_id} made a deposit of ${amount}."
                    send_email(subject, body, ADMIN_EMAILS)

                    return render_template(
                        'deposit_page.html',
                        pay_address=payment_data.get('pay_address'),
                        pay_amount=payment_data.get('pay_amount'),
                        qr_code_url=payment_data.get('payment_link'),
                        payment_status=payment_data.get('payment_status'),
                        expiration_estimate_date=payment_data.get('expiration_estimate_date')
                    )
                else:
                    app.logger.error(f"Unexpected payment status: {payment_data.get('payment_status')}")
                    return render_template('deposit_page.html', error="Unexpected payment status.")
            except ValueError as e:
                app.logger.error(f"Failed to parse payment response: {response.text} - Exception: {str(e)}")
                return render_template('deposit_page.html', error="Failed to parse payment response")
        else:
            app.logger.error(f"Failed to create payment: {response.text} - Status code: {response.status_code}")
            return render_template('deposit_page.html', error="Failed to create payment. Please try again.")

    return render_template('deposit_page.html')

@app.route('/admin/deposit_logs', methods=['GET'])
def get_deposit_logs():
    logs = DepositLog.query.all()
    deposit_logs = [
        {
            'user_id': log.user_id,
            'amount': log.amount,
            'payment_status': log.payment_status,
            'pay_address': log.pay_address,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'confirmed_at': log.confirmed_at.strftime('%Y-%m-%d %H:%M:%S') if log.confirmed_at else None
        }
        for log in logs
    ]
    return jsonify(deposit_logs)


@app.route('/withdraw', methods=['POST'])
def withdraw():
    telegram_id = request.form['telegram_id']
    amount = float(request.form['amount'])
    address = request.form['address']

    user = db.session.query(User).filter_by(telegram_id=telegram_id).first_or_404()

    if user.balance >= amount:
        user.balance -= amount

        # Create a new withdrawal log
        new_withdrawal_log = WithdrawalLog(
            user_id=user.id,
            amount=amount,
            address=address,
            status="Pending"
        )
        db.session.add(new_withdrawal_log)
        db.session.commit()

        # Send email notification to admins
        subject = "New Withdrawal"
        body = f"User {user.name} (ID: {user.id}) requested a withdrawal of ${amount} to address {address}."
        send_email(subject, body, ADMIN_EMAILS)

        return jsonify({"success": True, "message": "Withdrawal initiated"})
    else:
        return jsonify({"error": "Insufficient balance"}), 400



@app.route('/admin/withdrawal_logs', methods=['GET'])
def get_withdrawal_logs():
    user_id = flask_session.get('user_id')

    # Log the user ID and check for admin status
    app.logger.info(f"User ID from session: {user_id}")
    
    user = db.session.get(User, user_id)
    if not user:
        app.logger.warning(f"No user found with ID: {user_id}")
        return jsonify({'error': 'Unauthorized - No such user'}), 403

    if not user.is_admin:
        app.logger.warning(f"User {user_id} is not an admin")
        return jsonify({'error': 'Unauthorized - Not an admin'}), 403

    logs = WithdrawalLog.query.all()

    withdrawal_logs = [
        {
            'id': log.id,
            'user_id': log.user_id,
            'amount': log.amount,
            'address': log.address,
            'status': log.status,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'completed_at': log.completed_at.strftime('%Y-%m-%d %H:%M:%S') if log.completed_at else None
        }
        for log in logs
    ]
    return jsonify(withdrawal_logs)



@app.route('/user/withdrawal_logs', methods=['GET'])
def get_user_withdrawal_logs():
    user_id = flask_session.get('user_id')

    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Fetch only the withdrawal logs of the current user
    logs = WithdrawalLog.query.filter_by(user_id=user_id).all()

    withdrawal_logs = [
        {
            'id': log.id,
            'amount': log.amount,
            'address': log.address,
            'status': log.status,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'completed_at': log.completed_at.strftime('%Y-%m-%d %H:%M:%S') if log.completed_at else None
        }
        for log in logs
    ]
    return jsonify(withdrawal_logs)

@app.route('/admin/update_withdrawal_status', methods=['POST'])
def update_withdrawal_status():
    log_id = request.form['log_id']
    new_status = request.form['status']

    log = db.session.query(WithdrawalLog).filter_by(id=log_id).first_or_404()
    log.status = new_status
    if new_status == "Completed":
        log.completed_at = datetime.utcnow()

    db.session.commit()

    return jsonify({"success": True})

@app.route('/api/nowpayments/ipn', methods=['POST'])
def nowpayments_ipn():
    data = request.json
    app.logger.info("Received IPN data: %s", data)

    payment_status = data.get('payment_status')
    order_id = data.get('order_id')
    amount_received = float(data.get('actually_paid', 0))
    pay_address = data.get('pay_address')

    if payment_status == 'confirmed':
        # Find the deposit log corresponding to this payment
        deposit_log = DepositLog.query.filter_by(pay_address=pay_address, amount=amount_received).first()
        
        if deposit_log:
            deposit_log.payment_status = 'confirmed'
            deposit_log.confirmed_at = datetime.utcnow()

            # Update the user's balance
            user = db.session.query(User).filter_by(id=deposit_log.user_id).first()
            if user:
                user.balance += amount_received
                db.session.commit()
                app.logger.info(f"Deposit confirmed for user {user.telegram_id}. Amount: {amount_received}")
            else:
                app.logger.error("User not found for confirmed deposit.")
                return jsonify({"error": "User not found"}), 404
        else:
            app.logger.error("Deposit log not found for confirmed payment.")
            return jsonify({"error": "Deposit log not found"}), 404

        return jsonify({"message": "Payment confirmed and deposit log updated"}), 200

    elif payment_status == 'waiting':
        app.logger.info("Payment waiting for order_id: %s", order_id)
        return jsonify({"message": "Payment is waiting"}), 200

    else:
        app.logger.warning("Unhandled payment status: %s for order_id: %s", payment_status, order_id)
        return jsonify({"message": "Payment status unhandled"}), 200


@app.route('/game_logs/telegram/<string:telegram_id>', methods=['GET'])
def get_game_logs_by_telegram_id(telegram_id):
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if user:
        logs = GameLog.query.filter_by(user_id=user.id).order_by(GameLog.timestamp.desc()).all()
        return jsonify(logs=[{
            'bet_amount': log.bet_amount,
            'winnings': log.winnings,
            'crash_point': log.crash_point,
            'result': log.result,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for log in logs])
    return jsonify(error="User not found"), 404

@app.route('/balance/<int:telegram_id>', methods=['GET'])
def get_balance_by_telegram_id(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        return jsonify(balance=user.balance)
    return jsonify(error="User not found"), 404

@app.route('/cancel_deposit', methods=['POST'])
def cancel_deposit():
    user_id = flask_session.get('user_id')

    if not user_id:
        return jsonify({"error": "User not authenticated"}), 403

   
    deposit_log = DepositLog.query.filter_by(user_id=user_id, payment_status='waiting').order_by(DepositLog.created_at.desc()).first()

    if deposit_log:
        deposit_log.payment_status = 'cancelled'
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"error": "No pending deposit found."}), 404
    
@app.route('/submit_cashout', methods=['POST'])
def submit_cashout():
    data = request.json
    cashout_multiplier = data.get('cashoutMultiplier')

    return jsonify(success=True, cashoutMultiplier=cashout_multiplier)


@app.route('/update_balance', methods=['POST'])
def update_balance():
    data = request.json
    telegram_id = data.get('telegram_id')
    new_balance = data.get('balance')

    user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.balance = float(new_balance)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/deposit', methods=['POST'])
def deposit():
    telegram_id = request.form['telegram_id']
    amount = request.form['amount']
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first_or_404()
    user.balance += float(amount)
    db.session.commit()

    # Send email notification to admins
    subject = "New Deposit"
    body = f"User {user.name} (ID: {user.id}) made a deposit of ${amount}."
    send_email(subject, body, ADMIN_EMAILS)

    return "Deposit successful"



@app.route('/telegram_login/<int:telegram_id>')
def telegram_login(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        flask_session['user_id'] = user.id  
        if user.is_admin:
            return redirect(url_for('admin_panel'))
        else:
            return "Unauthorized", 403
    else:
        return "Unauthorized - User not found", 404

@app.route('/admin_panel', methods=['GET'])
def admin_panel():
    if not flask_session.get('user_id'):
        return redirect(url_for('index'))

    user = db.session.get(User, flask_session.get('user_id'))
    if not user.is_admin:
        return "Unauthorized", 403

    # Fetch users with valid telegram_id
    users = db.session.query(User).filter(User.telegram_id.isnot(None)).all()

    # Fetch the last game logs for each user
    last_game_logs = {
        user.telegram_id: db.session.query(GameLog).filter_by(user_id=user.id).order_by(GameLog.timestamp.desc()).first()
        for user in users if user.telegram_id is not None
    }

    # Fetch all withdrawal logs
    withdrawal_logs = db.session.query(WithdrawalLog).order_by(WithdrawalLog.created_at.desc()).all()

    return render_template('admin_panel.html', users=users, last_game_logs=last_game_logs, withdrawal_logs=withdrawal_logs)


@app.route('/last_game_logs', methods=['GET'])
def last_game_logs():
    logs = db.session.query(GameLog).order_by(GameLog.timestamp.desc()).limit(10).all()
    users = {user.id: user.telegram_id for user in db.session.query(User).all()}

    logs_with_details = []
    for log in logs:
        telegram_id = users.get(log.user_id, "Unknown")

        logs_with_details.append({
            'telegram_id': telegram_id,
            'bet_amount': log.bet_amount,
            'crash_point': log.crash_point,
            'winnings': log.winnings,
            'result': log.result,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })

    return jsonify(logs_with_details)

@app.route('/grant_admin/<int:telegram_id>', methods=['POST'])
def grant_admin(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if user:
        user.is_admin = True
        db.session.commit()
        return jsonify(success=True)
    return jsonify(error="User not found"), 404

@app.route('/revoke_admin/<int:telegram_id>', methods=['POST'])
def revoke_admin(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first_or_404()
    user.is_admin = False
    db.session.commit()
    return jsonify(success=True)

@app.route('/create_admin', methods=['POST'])
def create_admin():
    password = request.form.get('password')
    if password != 'your_admin_creation_password':
        return "Unauthorized", 401
    
    name = request.form.get('name')
    email = request.form.get('email')
    telegram_id = request.form.get('telegram_id')

    existing_user = db.session.query(User).filter_by(telegram_id=telegram_id).first()
    if existing_user:
        return "User already exists", 400

    new_admin = User(name=name, email=email, telegram_id=int(telegram_id), is_admin=True)
    db.session.add(new_admin)
    db.session.commit()

    return f"Admin user {name} created successfully", 200

@app.route('/ban_user/<int:telegram_id>', methods=['POST'])
def ban_user(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=str(telegram_id)).first_or_404()
    user.is_banned = True
    db.session.commit()

    send_ban_notification(telegram_id)

    return jsonify(success=True)

def send_ban_notification(telegram_id):
    bot = Bot(token=TOKEN)
    try:
        bot.send_message(chat_id=telegram_id, text="You have been banned from accessing this bot.")
    except Exception as e:
        app.logger.error(f"Failed to send ban notification: {e}")

@app.route('/unban_user/<int:telegram_id>', methods=['POST'])
def unban_user(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=str(telegram_id)).first_or_404()
    user.is_banned = False
    db.session.commit()

    send_unban_notification(telegram_id)

    return jsonify(success=True)

def send_unban_notification(telegram_id):
    bot = Bot(token=TOKEN)
    try:
        bot.send_message(chat_id=telegram_id, text="You have been unbanned and can now access the bot again.")
    except Exception as e:
        app.logger.error(f"Failed to send unban notification: {e}")

@app.route('/delete_user/<int:telegram_id>', methods=['POST'])
def delete_user(telegram_id):
    user = db.session.query(User).filter_by(telegram_id=telegram_id).first_or_404()
    db.session.delete(user)
    db.session.commit()
    return jsonify(success=True)

@app.route('/logout')
def logout():
    flask_session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
