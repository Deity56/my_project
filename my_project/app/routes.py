from flask import Blueprint, request, jsonify
import sqlite3

main = Blueprint('main', __name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@main.route('/balance/<int:user_id>', methods=['GET'])
def get_balance(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'balance': user['balance']})

@main.route('/balance/<int:user_id>', methods=['POST'])
def update_balance(user_id):
    new_balance = request.json.get('balance')
    conn = get_db_connection()
    conn.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})
