import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from utils import *
import pyrebase
import re
import requests
from datetime import date as d

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True


config = {
  "apiKey": "AIzaSyD1OYOIIDK1ZXTFDs-ykrQwo3baTouP1pU",
  "authDomain": "verifit-99eee.firebaseapp.com",
  "databaseURL": "https://verifit-99eee.firebaseio.com",
  "storageBucket": "verifit-99eee.appspot.com"
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email and password:
            try:
                user = auth.sign_in_with_email_and_password(email,password)
                session['user_id'] = user["idToken"]
            except:
                return render_template("login.html", error="Invalid email or password")
            
        return redirect('/')
    else:
        return render_template("login.html")

@app.route("/", methods=["GET", "POST"])
def index():
    if session.get("user_id"):
        if request.method == "GET":
            date = d.today().strftime("mm-dd-yyyy")
            menu = {
                "breakfast": get_menu(date, 0),
                "lunch": get_menu(date, 1),
                "dinner": get_menu(date, 2)
            }
            return render_template("index.html", date="Today", menu=menu)
        else:
            date = reformat(request.form.get("date"))
            menu = {
                "breakfast": get_menu(date, 0),
                "lunch": get_menu(date, 1),
                "dinner": get_menu(date, 2)
            }
            return render_template("index.html", date=date, menu=menu)
    else:
        return render_template("welcome.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if email and password and confirmation:
            if not re.match(r"[\w@!.~#]{6,128}", password):
                return render_template("register.html", error="Passwords must be 6+ characters and contain only alphanumeric characters or @!.~#")
            if not password == confirmation:
                return render_template("register.html", error="Password and confirmation do not match")
        try:
            user = auth.create_user_with_email_and_password(email, password)
        except requests.exceptions.HTTPError:
            return render_template("register.html", error="Email in use")
        token = user["idToken"]
        auth.send_email_verification(token)
        return redirect("/")
        
    else:
        return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")