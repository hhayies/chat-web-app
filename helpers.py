import os
import requests
import urllib.parse
from cs50 import SQL

from flask import redirect, flash, render_template, request, session
from functools import wraps

db = SQL("sqlite:///project.db")

def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# ２つ以上のチャットルーム内に入れないようにする
def roomin_checked(f):
    @wraps(f)
    def is_room():
        rows = db.execute("SELECT * FROM members WHERE user_id = ?", session.get("user_id"))
        if len(rows) != 0:
            flash("すでに他のルーム参加しています")
            return redirect("/")
        return f()
    return is_room

