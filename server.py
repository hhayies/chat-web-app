from flask import Flask, redirect, flash, render_template, request, session, g
from flask_session import Session
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required, roomin_checked

import sqlite3
import datetime, pytz
import random
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

socketio = SocketIO(app, cors_allowed_origins='*')

room_id = 0

def get_db():

    if "db" not in g:
        g.db = sqlite3.connect("project.db")
    return g.db


def check_field(name, mes):

    value = request.form.get(name)
    if not value:
        flash(f"{name}を入力してください")
    return value


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

    else:
        username = check_field("username", "ユーザー名")
        password = check_field("password" , "パスワード")
        confirmation = check_field("confirmation", "確認パスワード")

        if not username or not password or not confirmation:
            return render_template("register.html")

        if username == password:
            flash("ユーザー名とパスワードは違うものを入力してください")
            return render_template("register.html")

        if password != confirmation:
            flash("確認パスワードが一致していません")
            return render_template("register.html")

        if len(password) < 3:
            flash("3文字以上のパスワードを入力してください")
            return render_template("register.html")

        hash = generate_password_hash(password)

        try:
            con = get_db()
            new_user = con.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
            con.commit()
            con.close()
        except:
            flash("ユーザー名が既に使われています")
            return render_template("register.html")

        session["user_id"] = new_user
        return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()
    if request.method == "POST":
        username = check_field("username", "ユーザー名")
        password = check_field("password" , "パスワード")

        if not username or not password:
            return render_template("login.html")

        con = get_db()
        cur = con.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        rows = cur.fetchall()
        con.close()

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("ユーザー名もしくはパスワードが間違っています")
            return render_template("login.html")

        session["user_id"] = rows[0]["id"]
        return redirect("/")

    else:
        return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/make', methods=["GET", "POST"])
@login_required
@roomin_checked
def make():

    global room_id
    con = get_db()
    if request.method == "GET":
        room_id = random.randint(100000, 999999)
        row = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()

        while len(row) != 0:
            room_id = random.randint(100000, 999999)
            row = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()

        con.close()
        return render_template('make.html', room_id=room_id)

    else:
        password = request.form.get("password")
        if not password or len(password) > 10:
            flash("10文字以下のパスワードを入力してください")
            return render_template("make.html", room_id=room_id)

        con.execute("INSERT INTO chat_room (id, password) VALUES (?, ?)", room_id, password)
        is_anonymous = int(request.form.get("anonymous"))
        con.execute("UPDATE users SET is_anonymous = ? WHERE id = ?", is_anonymous, session["user_id"])
        con.commit()
        return render_template('chatroom.html', room_id=room_id, password=password)


@app.route('/join', methods=["GET", "POST"])
@login_required
@roomin_checked
def join():

    global room_id
    if request.method == "POST":
        room_id = check_field("room_id", "ルームid")
        password = check_field("password", "パスワード")

        if not room_id or not password:
            return render_template("join.html")

        if not room_id.isdecimal():
            flash("ルームidには数字を入力してください")
            return render_template("join.html")

        room_id = int(request.form.get("roomid"))
        con = get_db()
        room = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()

        if len(room) == 0:
            flash("入力された情報に合う部屋が存在しませんでした")
            return render_template("join.html")

        room_pass = str(room["password"])

        if room_pass != password:
            flash("入力されたパスワードが間違っています")
            return render_template("join.html")

        is_anonymous = int(request.form.get("anonymous"))

        con.execute("UPDATE users SET is_anonymous = ? WHERE id = ?", is_anonymous, session["user_id"])
        con.commit()
        con.close()
        return render_template("chatroom.html", room_id=room_id, password=password)

    else:
        return render_template('join.html')


@app.route('/chatroom', methods=["GET", "POST"])
@login_required
def chatroom():

    global room_id
    if request.method == "POST":
        room_id = int(request.form.get("id"))
        return redirect('/')

    else:
        return render_template('join.html')


@socketio.on('connect')
def connect(auth):

    con = get_db()
    cur = con.execute("SELECT * FROM users WHERE id = ?", session["user_id"]).fetchone()
    is_anonymous = cur["is_anonymous"]

    if is_anonymous:
        user_name = "Anonymous"
    else:
        user_name = con.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]["username"]

    con.execute("UPDATE chat_room SET people_num = (people_num + 1) WHERE id = ?", room_id)
    cur = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()
    user_count = cur["people_num"]

    join_room(room_id)

    con.execute("INSERT INTO members (room_id, user_id, user_name) VALUES (?, ?, ?)", room_id, session["user_id"], user_name)
    con.commit()

    members = con.execute("SELECT user_name FROM members WHERE room_id = ?", room_id).fetchall()
    members = [str(i["user_name"]) for i in members]

    con.close()
    emit('count_update', {'user_count': user_count, 'name': user_name, 'members': members, 'alert': True},  room=room_id)
    emit('display_name', {'name': user_name})


@socketio.on('disconnect')
def disconnect():

    time.sleep(0.001)
    con = get_db()
    con.execute("UPDATE chat_room SET people_num = (people_num - 1) WHERE id = ?", room_id)
    cur = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()
    user_count = cur["people_num"]
    con.execute("UPDATE users SET is_anonymous = 0 WHERE id = ?", session["user_id"])

    leave_room(room_id)

    con.execute("DELETE FROM members WHERE room_id = ? AND user_id = ?", room_id, session["user_id"])
    members = con.execute("SELECT user_name FROM members WHERE room_id = ?", room_id).fetchall()
    members = [str(i["user_name"]) for i in members]
    con.commit()

    if user_count == 0:
        con.execute("DELETE FROM chat_room WHERE id = ?", room_id)

    con.close()
    emit('count_update', {'user_count': user_count, 'members': members, 'alert': False}, room=room_id)


@socketio.on('chat_message')
def chat_message(json):

    global room_id
    text = json["text"]
    user = json["user"]
    id = json["id"]
    msg_type = json["type"]
    room_id = int(id)

    date = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))

    date_str = "-" + date.strftime('%H:%M') + "-"

    if msg_type == "button":
        emit('chat_message', {'text': text , 'user': user , 'date': date_str , 'type': True}, room=room_id)

    elif msg_type == "message":
        emit('chat_message', {'text': text , 'user': user , 'date': date_str , 'type': False}, room=room_id)


@socketio.on('good_count')
def good_count(json):

    global room_id
    room_id = int(json["id"])
    con = get_db()

    if (json["is_reset"]):
        con.execute("UPDATE chat_room SET good_count = 0 WHERE id = ?", room_id)
        con.commit()
        con.close()

    else:
        con.execute("UPDATE chat_room SET good_count = (good_count + 1) WHERE id = ?", room_id)
        con.commit()
        cur = con.execute("SELECT * FROM chat_room WHERE id = ?", room_id).fetchone()
        good_count = cur["good_count"]
        con.close()
        emit('good_countup', {'good_count': good_count}, room=room_id)


if __name__ == '__main__':
    socketio.run(app, debug=True)
