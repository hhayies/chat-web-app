from flask import Flask, redirect, flash, render_template, request, session
from flask_session import Session
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from cs50 import SQL
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, roomin_checked

import datetime, pytz
import random
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///project.db")

# cors_allowed_originは本来適切に設定するべき
socketio = SocketIO(app, cors_allowed_origins='*')

# ルームid
room_id = 0


""""""""""""""""""""""ログイン処理"""""""""""""""""""""""


# 新規登録の処理
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            flash("ユーザー名を入力してください")
        if not password:
            flash("パスワードを入力してください")

        if not confirmation:
            flash("確認パスワードを入力してください")
            return render_template("register.html")

        # ユーザとパスワードが一致していた場合、エラーを表示させる
        if username == password:
            flash("ユーザー名とパスワードは違うものを入力してください")
            return render_template("register.html")

        # パスワードと再確認パスワードが一致していない場合、エラーを表示
        if password != confirmation:
            flash("確認パスワードが一致していません")
            return render_template("register.html")

        # ユーザのパスワードの長さを3文字以上にする。
        if len(password) < 3:
            flash("3文字以上のパスワードを入力してください")
            return render_template("register.html")

        hash = generate_password_hash(password)

        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            flash("すでに登録されています")
            return render_template("register.html")

        session["user_id"] = new_user

        return redirect("/")

# ログイン処理
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ユーザー名が入力されているかの確認
        if not request.form.get("username"):
            flash("ユーザー名を入力してください")

        # パスワードが入力されているかの確認
        if not request.form.get("password"):
            flash("パスワードを入力してください")
            return render_template("login.html")

        # データベースからユーザー名を取得
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # 入力情報が正しいかの確認
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("ユーザー名もしくはパスワードが間違っています")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# ログアウト処理
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


"""""""""""""""""""  チャット画面遷移までの処理  """""""""""""

# ホーム画面表示
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# ルーム作成画面
@app.route('/make', methods=["GET", "POST"])
@login_required
@roomin_checked
def make():
    global room_id

    if request.method == "GET":

        # ランダムに6桁の数字を生成
        room_id = random.randint(100000, 999999)

        # データベースに同じ数字の部屋が存在しないか確認
        row = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)

        # 存在する場合はもう一度生成しなおす
        while len(row) != 0:
            room_id = random.randint(100000, 999999)
            row = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)

        return render_template('make.html', room_id=room_id)

    # post送信の場合の処理
    else:
        # パスワードの取得
        password = request.form.get("password")

        # パスワードが正しく入力できているかの判定
        if not password or len(password) > 10:
            flash("10文字以下のパスワードを入力してください")
            return render_template("make.html", room_id=room_id)

        # データベースにルーム情報を挿入
        db.execute("INSERT INTO chat_room (id, password) VALUES (?, ?)", room_id, password)

        # 匿名機能の判定
        is_anonymous = int(request.form.get("anonymous"))

        db.execute("UPDATE users SET is_anonymous = ? WHERE id = ?", is_anonymous, session["user_id"])

        # チャットルームの画面に遷移する
        return render_template('chatroom.html', room_id=room_id, password=password)


# ルーム参加処理
@app.route('/join', methods=["GET", "POST"])
@login_required
@roomin_checked
def join():
    global room_id

    if request.method == "POST":

        # ルームidの取得
        room_id = request.form.get("roomid")

        # パスワードの取得
        password = request.form.get("password")

        # 空になっていないかの確認
        if not request.form.get("roomid"):
            flash("ルームidを入力してください")

        if not request.form.get("password"):
            flash("パスワードを入力してください")
            return render_template("join.html")

        # room_idが数字かどうか判定
        if not room_id.isdecimal():
            flash("ルームidには数字を入力してください")
            return render_template("join.html")

        room_id = int(request.form.get("roomid"))

        # データベースからルーム情報の取得
        room = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)
        if len(room) == 0:
            flash("入力された情報に合う部屋が存在しませんでした")
            return render_template("join.html")

        # 入力情報が正しいかの確認
        room_pass = str(room[0]["password"])

        if room_pass != password:
            flash("入力されたパスワードが間違っています")
            return render_template("join.html")

        # 匿名機能の判定
        is_anonymous = int(request.form.get("anonymous"))

        db.execute("UPDATE users SET is_anonymous = ? WHERE id = ?", is_anonymous, session["user_id"])

        # 画面遷移
        return render_template("chatroom.html", room_id=room_id, password=password)

    else:
        return render_template('join.html')

# チャット終了処理
@app.route('/chatroom', methods=["GET", "POST"])
@login_required
def chatroom():
    global room_id

    if request.method == "POST":

        # 退出するルームのidを取得して上書き
        room_id = int(request.form.get("id"))

        # ホーム画面に遷移
        return redirect('/')

    else:
        return render_template('join.html')



"""""""""""""""""""""  ユーザー接続処理  """""""""""""""


# ユーザーが新しく接続すると実行
@socketio.on('connect')
def connect(auth):

    # ユーザーの匿名機能　on/off　を確認
    is_anonymous = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]["is_anonymous"]

    # 匿名機能on
    if is_anonymous:
        user_name = "Anonymous"

    # ユーザー名をデータベースから取得(匿名機能off)
    else:
        user_name = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]["username"]

    # ユーザー数の更新
    db.execute("UPDATE chat_room SET people_num = (people_num + 1) WHERE id = ?", room_id)

    # ユーザー数
    user_count = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)[0]["people_num"]

    # ルーム参加
    join_room(room_id)

    # ルームのメンバー情報を追加
    db.execute("INSERT INTO members (room_id, user_id, user_name) VALUES (?, ?, ?)", room_id, session["user_id"], user_name)

    # ルームのメンバー情報を取得
    members = db.execute("SELECT user_name FROM members WHERE room_id = ?", room_id)

    # リスト変換
    members = [str(i["user_name"]) for i in members]

    # 接続者数の更新（全員向けに送信）
    # 入室通知をする(alert = true)
    emit('count_update', {'user_count': user_count, 'name': user_name, 'members': members, 'alert': True},  room=room_id)

    # 名前の表示
    emit('display_name', {'name': user_name})

    # テキストエリアの更新と名前の表示(接続した人のみに送信)
    # emit('restore_message', {'chat': chat, 'name': user_name})


# ユーザーの接続が切断すると実行
@socketio.on('disconnect')
def disconnect():

    # room_idが書き換わるのを待つ
    time.sleep(0.001)

    # ユーザー数の更新
    db.execute("UPDATE chat_room SET people_num = (people_num - 1) WHERE id = ?", room_id)

    # ユーザー数
    user_count = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)[0]["people_num"]

    # 匿名機能のoff
    db.execute("UPDATE users SET is_anonymous = 0 WHERE id = ?", session["user_id"])

    # ルーム退室
    leave_room(room_id)

    # ルームのメンバー情報を削除
    db.execute("DELETE FROM members WHERE room_id = ? AND user_id = ?", room_id, session["user_id"])

    # ルームのメンバー情報を取得
    members = db.execute("SELECT user_name FROM members WHERE room_id = ?", room_id)

    # リスト変換
    members = [str(i["user_name"]) for i in members]

    # 部屋の人数が0人なったら削除
    if user_count == 0:
        db.execute("DELETE FROM chat_room WHERE id = ?", room_id)

    # 接続者数の更新（全員向け）
    # 退室通知はしない(alert = false)
    emit('count_update', {'user_count': user_count, 'members': members, 'alert': False}, room=room_id)


# ボタンが押されるとメッセージを送信
@socketio.on('chat_message')
def chat_message(json):
    global room_id
    text = json["text"]
    user = json["user"]
    id = json["id"]
    msg_type = json["type"]
    room_id = int(id)

    # 日本時間での現在時刻を取得
    date = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))

    # 現在時刻のデータ形式を「datetime型」から「文字型」に変更
    date_str = "-" + date.strftime('%H:%M') + "-"

    # メッセージの種類を判別
    if msg_type == "button":
        emit('chat_message', {'text': text , 'user': user , 'date': date_str , 'type': True}, room=room_id)

    elif msg_type == "message":
        emit('chat_message', {'text': text , 'user': user , 'date': date_str , 'type': False}, room=room_id)

# 「いいね！」ボタンが押されると実行
@socketio.on('good_count')
def good_count(json):
    global room_id

    room_id = int(json["id"])

    if (json["is_reset"]):
        # 「いいね！」数データを0にする
        db.execute("UPDATE chat_room SET good_count = 0 WHERE id = ?", room_id)

    else:
        # 「いいね！」数データの更新
        db.execute("UPDATE chat_room SET good_count = (good_count + 1) WHERE id = ?", room_id)
        # データから値を読み取る
        good_count = db.execute("SELECT * FROM chat_room WHERE id = ?", room_id)[0]["good_count"]
        # いいね数をWeb上に反映
        emit('good_countup', {'good_count': good_count}, room=room_id)


if __name__ == '__main__':
    socketio.run(app, debug=True)
