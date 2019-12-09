from functools import wraps
from flask import g, request, redirect, url_for, session
import requests
from lxml import html
from lxml.cssselect import CSSSelector
import re
import sqlite3

def login_required(f):
    """
    A session checking wrapper function.

    If the user is logged in (has an id), proceed to wrapped fucntion; else redirect to login.

    Parameters:
        f (function): The function that is to be wrapped, login protected.

    Returns:
        decorated_function (function): The wrapped function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def update(meal, items, user, date, currVal=0):
    """
    Update item quantities of an entry in the database.

    For items already added to a meal by the user. Set the items for that meal and day to the new quantity. Remove if 0.

    Parameters:
        meal (string): breakfast, lunch, or dinner
        items (list[Tuple]): a list of items ids and quantities
        user (int): User ID
        date (string): MM-DD-YY
        currVal (int): quantity of another instance of item in the database
    
    Returns:
        None
    """
    meal= clean(meal)
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    for item in items:
        if currVal + int(item[1]) > 0:
            query = f"Update {meal} set quantity=? where uid=? and date=? and item=?"
            db.execute(query, (currVal + int(item[1]), user, date, item[0]))
        else:
            query = f"Delete from {meal} where uid=? and date=? and item=?"
            db.execute(query, (user, date, item[0]))
    conn.commit()
    conn.close()
    
def get_options(user):
    """
    Retrieve the a users settings from the database.

    Parameters:
        user (int): User ID

    Returns:
        opt (dict): A dictionary containing user email, hash, and name.
    """
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    db.execute("Select email, hash, name from users where id=?", (user,))
    rec = db.fetchone()
    opt = {
        "email": rec[0],
        "hash": rec[1],
        "name": rec[2]
    }
    conn.close(0)
    return opt

def update_options(user, opts):
    """
    Update the users settings on the database.

    Parameters:
        user (int): User ID
        opts (dict): A dictionary with the users new email, hash, and name.
    
    Returns:
        None
    """
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    db.execute("Update users set email=?, hash=?, name=? where id=?", (opts["email"], opts["hash"], opts["name"], user))
    conn.commit()
    conn.close()
    
def get_goals(user):
    """
    Retrieve the a users goals from the database. If the user is not in the goals db, create an entry.

    Parameters:
        user (int): User ID

    Returns:
        goals (dict): A dictionary containing user current weight, goal weight, and calorie goal.
    """
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    db.execute("Select currWeight, goalWeight, calories from goals where uid=?", (user,))
    rec = db.fetchone()
    if not rec:
        db.execute("Insert into goals values (?, ?, ?, ?)", (user, None, None, None))
        conn.commit()
        goals = {
            "currWeight": None,
            "goalWeight": None,
            "calories": None
        }
    else:
        goals = {
            "currWeight": rec[0],
            "goalWeight": rec[1],
            "calories": rec[2]
        }
    conn.close()
    return goals

def update_goals(user, currWeight, goalWeight, calories):
    """
    Update the users goals on the database.

    Parameters:
        user (int): User ID
        currWeight (int): the users current weight
        goalWeight (int): the weight the user is trying to obtain
        calories (int): the users daily calorie goal
    
    Returns:
        None
    """
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    db.execute("Update goals set currWeight=?, goalWeight=?, calories=? where uid=?", (currWeight, goalWeight, calories, user))
    conn.commit()
    conn.close()

def add_items(meal, items, user, date):
    """
    Add items to an entry in the database.

    For items already added to a meal by the user. Set the items for that meal and day to the new quantity.

    Parameters:
        meal (string): breakfast, lunch, or dinner
        items (list[Tuple]): a list of items ids and quantities
        user (int): User ID
        date (string): MM-DD-YY
    
    Returns:
        None
    """
    meal= clean(meal)
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    for item in items:
        """
        In this instance, f strings must be used because SQLite3 does not support variable table names.
        For this reason, the meal variable has been sanitized to only alphanumeric characters.
        """
        db.execute(f"Select * from {meal} where item=? and date=? and uid=?;", (item[0], date, user))
        existing = db.fetchone()
        if existing:
            update(meal, [item], user, date, currVal=existing[1])
        else:
            """
            In this instance, f strings must be used because SQLite3 does not support variable table names.
            For this reason, the meal variable has been sanitized to only alphanumeric characters.
            """
            query = f"Insert into {meal} values (?, ?, ?, ?)"
            db.execute(query, (item[0], item[1], user, date))
    conn.commit()
    conn.close()

def get_entry(meal, user, date):
    """
    Find the items and nutritional info for a users meal.

    Parameters:
        meal (string): breakfast, lunch, or dinner
        user (int): User ID
        date (string): MM-DD-YY

    Returns:
        result (List[ImmutableDict]): A list of sqlite3 immutable dicts with items and their info
    """
    meal = clean(meal)
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    """
    In this instance, f strings must be used because SQLite3 does not support variable table names.
    For this reason, the meal variable has been sanitized to only alphanumeric characters.
    """
    query = f"Select SUM(quantity), * from {meal} inner join recipes on {meal}.item=recipes.id where {meal}.uid=? and {meal}.date=? group by {meal}.item;"
    db.execute(query, (user, date))
    result = db.fetchall()
    conn.close()
    return result

def get_total(result):
    """
    Calculate macronutrient and calorie totals for a meal.

    Parameters:
        result (list[ImmutableDict]): A list of immutable dicts given by get_entry()
    
    Returns:
        A dictionary with total values for calories, carbs, protein, and fat.
    """
    totals = {
        "calories": 0,
        "carbs": 0,
        "protein": 0,
        "fat": 0
    }
    for item in result:
        totals["calories"] += round(item[0] * item[7], 2)
        totals["carbs"] += round(item[0] * item[8], 2)
        totals["protein"] += round(item[0] * item[9], 2)
        totals["fat"] += round(item[0] * item[10], 2)
    return totals

def clean(string):
    """
    Remove non alphanumeric characters in a string.

    Parameters:
        string (string): the string to be sanitized

    Returns:
        out (string): the input string, stripped of non alphanumeric characters.
    """
    return ''.join(c for c in string if c.isalnum())

def get_menu(date, meal):
    """
    Scrape the HUDS menu to find what items will be offered for a meal on date.

    If a recipe on the menu is not in the recipes db, scrape the recipe page for info.

    Parameters:
        date (string): MM-DD-YY
        meal (int): 0= breakfast/brunch 1=lunch 2=dinner

    Returns:
        menu (list[dict]): a list of dictionaries containing id, name, calories, carbs, protein, fat, 
        and serving size for each item.
    """
    conn = sqlite3.connect("verifit.db")
    db = conn.cursor()
    url = f'http://www.foodpro.huds.harvard.edu/foodpro/menu_items.asp?date={date}&meal={meal}&type=30'
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None
    site = html.fromstring(response.content)
    selector = CSSSelector("[href*='http\://www.foodpro.huds.harvard.edu/foodpro/item.asp?recipe=']")
    items = selector(site)
    menu=[]
    recipeRegex = re.compile(r"recipe=(?P<recipe>\d+)&")
    nutritionRegex = re.compile(r"Serving Size:</b> (?P<quantity>.+?)(&nbsp;)(?P<unit>.+?)<br />.*<b>Calories:</b> (?P<calories>.+?)<br />.*?<b>Total Fat:</b> (?P<fat>.+?) g<br />.*?<b>Total Carbs:</b> (?P<carbs>.+?) g<br />.*?<b>Protein:</b> (?P<protein>.+?) g<br />", re.S)
    for item in items:
        itemUrl = item.get('href')
        name = item.text.strip()
        recipe = recipeRegex.search(itemUrl).group("recipe")
        db.execute("Select * from recipes where id=?;", (int(recipe),))
        recipeCheck = db.fetchone()
        if not recipeCheck:
            try:
                itemResponse = requests.get(itemUrl)
                itemResponse.raise_for_status()
            except requests.RequestException:
                print("ITEM REQUEST RETURNED NONE")
                return None
            raw = itemResponse.text
            matches = nutritionRegex.search(raw)
            if matches:
                info = matches.groupdict()
                info['name'] = name
                info['id'] = recipe
                menu.append(info)
                db.execute("Insert into recipes values (?,?,?,?,?,?,?,?);", (recipe, name, matches.group("calories"), matches.group("carbs"), matches.group("protein"), matches.group("fat"), matches.group("quantity"), matches.group("unit")))
                conn.commit()
        else:
            addition = {
                "id": recipeCheck[0],
                "name":recipeCheck[1],
                "quantity":recipeCheck[6],
                "unit":recipeCheck[7],
                "calories":recipeCheck[2],
                "carbs":recipeCheck[3],
                "fat":recipeCheck[5],
                "protein":recipeCheck[4],
            }
            menu.append(addition)
    conn.close()
    return menu

def reformat(date):
    """
    Reformat a date from YYYY-MM-DD to MM-DD-YY.

    Parameters:
        date (string): YYYY-MM-DD
    
    Returns:
        date (string): MM-DD:YY.
    """
    if not date:
        return None
    part = re.match(r"\d{2}(\d{2})-(\d{2})-(\d{2})", date)
    new = f"{part.group(2)}-{part.group(3)}-{part.group(1)}"
    return new




        
