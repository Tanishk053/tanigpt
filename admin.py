from flask import Flask, render_template, request, redirect, url_for
import json
import os

app = Flask(__name__)
USER_DATA_FILE = "users.json"
ADMIN_PASSWORD = "1029@tanishk"  # Change this!

def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    password = request.form['password']
    if password == ADMIN_PASSWORD:
        return redirect(url_for('dashboard'))
    return "Invalid password!", 403

@app.route('/dashboard')
def dashboard():
    users = load_users()
    return render_template('dashboard.html', users=users)

@app.route('/delete/<user_id>')
def delete_user(user_id):
    users = load_users()
    if user_id in users:
        del users[user_id]
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)