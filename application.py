import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, make_response
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from utils import login_required, get_goals, get_menu, reformat, add_items, get_entry, get_total, update, get_options, update_options, update_goals
import re
import requests
from datetime import date as d
import sqlite3

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True


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
        conn = sqlite3.connect("verifit.db")
        db = conn.cursor()
        email = request.form.get("email")
        password = request.form.get("password")
        if email and password:
            db.execute("Select * from users where email=?", (email,))
            user = db.fetchone()
            if not user or not check_password_hash(user[2], password):
                return render_template("login.html", error="Invalid email or password")
            session['user_id'] = user[0]
        return redirect('/')
    else:
        return render_template("login.html")

@app.route("/", methods=["GET", "POST"])
def index():
    if session.get("user_id"):
        if request.method == "GET":
            date = d.today().strftime("%m-%d-%y")
            menu = {
                "breakfast": get_menu(date, 0),
                "lunch": get_menu(date, 1),
                "dinner": get_menu(date, 2)
            }
            breakfastEntry = get_entry("breakfast", session.get("user_id"), date)
            lunchEntry = get_entry("lunch", session.get("user_id"), date)
            dinnerEntry = get_entry("dinner", session.get("user_id"), date)
            totals = {
            "b": get_total(breakfastEntry),
            "l": get_total(lunchEntry),
            "d": get_total(dinnerEntry)
            }
            goal = get_goals(session.get("user_id"))["calories"]
            resp = make_response(render_template("index.html", date=date, menu=menu, breakfast=breakfastEntry, lunch=lunchEntry, dinner=dinnerEntry, totals=totals, goal=goal))
            resp.set_cookie("date", date)
            return resp
        else:
            date = reformat(request.form.get("date"))
            if not date:
                date = request.cookies.get("date")
                if not date:
                    date = d.today().strftime("%m-%d-%y")
                items = []
                edit = False
                for item in request.form.items():
                    if len(item) > 1 and item[1] != '':
                        items.append(item)
                    elif item[0] == "breakfast" or item[0] == "lunch" or item[0] == "dinner":
                        edit = False
                        meal = item[0]
                    elif item[0] == "bEdit":
                        edit = True
                        meal = "breakfast"
                    elif item[0] == "lEdit":
                        edit = True
                        meal = "lunch"
                    elif item[0] == "dEdit":
                        edit = True
                        meal = "dinner"
                if edit:
                    update(meal, items, session.get("user_id"), date)
                else:
                    add_items(meal, items, session.get("user_id"), date)
            menu = {
                "breakfast": get_menu(date, 0),
                "lunch": get_menu(date, 1),
                "dinner": get_menu(date, 2)
            }
            breakfastEntry = get_entry("breakfast", session.get("user_id"), date)
            lunchEntry = get_entry("lunch", session.get("user_id"), date)
            dinnerEntry = get_entry("dinner", session.get("user_id"), date)
            totals = {
            "b": get_total(breakfastEntry),
            "l": get_total(lunchEntry),
            "d": get_total(dinnerEntry)
            }
            goal = get_goals(session.get("user_id"))["calories"]
            resp = make_response(render_template("index.html", date=date, menu=menu, breakfast=breakfastEntry, lunch=lunchEntry, dinner=dinnerEntry, totals=totals, goal=goal))
            resp.set_cookie("date", date)
            return resp
    else:
        return render_template("welcome.html")

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        opts= get_options(session.get('user_id'))
        name = request.form.get("name")
        email = request.form.get("email")
        old = request.form.get("password")
        new = request.form.get("new")
        confirm = request.form.get('confirm')
        newOpts = {}
        if check_password_hash(opts["hash"], old):
            if new != '':
                if not re.match(r"[\w@!.~#]{6,128}",new):
                    return render_template("settings.html", opts=opts, error="Passwords must be 6+ characters and contain only alphanumeric characters or @!.~#")
                elif not confirm == new:
                    return render_template("settings.html", opts=opts, error="Passwords do not match")
                else:
                    newOpts["hash"] = generate_password_hash(new)
            else:
                newOpts["hash"] = opts["hash"]
            if email != '':
                newOpts["email"] = email
            else:
                newOpts["email"] = opts["email"]
            if name != '':
                newOpts["name"] = name
            else:
                name = opts["name"]
            print(newOpts)
            update_options(session.get('user_id'), newOpts)
            return redirect("/settings")
        else:
            return render_template("settings.html", opts=opts, error="Old password incorrect")
    else:
        opts= get_options(session.get('user_id'))
        return render_template("settings.html", opts=opts)

@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    if request.method == "POST":
        currWeight = request.form.get("currWeight")
        goalWeight = request.form.get("goalWeight")
        calories = request.form.get("calories")
        update_goals(session.get("user_id"), currWeight, goalWeight, calories)
        return redirect("/goals")
    else:
        goals = get_goals(session.get("user_id"))
        return render_template("goals.html", goals=goals)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = sqlite3.connect("verifit.db")
        db = conn.cursor()
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if email and password and confirmation:
            if not re.match(r"[\w@!.~#]{6,128}", password):
                return render_template("register.html", error="Passwords must be 6+ characters and contain only alphanumeric characters or @!.~#")
            if not password == confirmation:
                return render_template("register.html", error="Password and confirmation do not match")
        db.execute("Select * from users where email=?;", (email,))
        if db.fetchone():
            return render_template("register.html", error="Email in use")
        hsh = generate_password_hash(password)
        db.execute("Insert into users (email, hash, name) values (?, ?, ?);", (email, hsh, name))
        conn.commit()
        return redirect("/")
        
    else:
        return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")