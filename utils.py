from functools import wraps
from flask import g, request, redirect, url_for, session
import requests
from lxml import html
from lxml.cssselect import CSSSelector
import re

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def get_menu(date, meal):
    url = f'http://www.foodpro.huds.harvard.edu/foodpro/menu_items.asp?date={date}&meal={meal}'
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None
    site = html.fromstring(response.content)
    selector = CSSSelector("[href*='http\://www.foodpro.huds.harvard.edu/foodpro/item.asp?recipe=']")
    items = selector(site)
    menu=[]
    nutritionRegex = re.compile(r"Serving Size:</b> (?P<quantity>.+?)(&nbsp;)(?P<unit>.+?)<br />.*<b>Calories:</b> (?P<calories>.+?)<br />.*?<b>Total Fat:</b> (?P<fat>.+?) g<br />.*?<b>Total Carbs:</b> (?P<carbs>.+?) g<br />.*?<b>Protein:</b> (?P<protein>.+?) g<br />", re.S)
    #calServRegex = re.compile(r'Serving Size:</b>(?P<quantity>.+?)(&nbsp;)?(?P<unit>.+?)<br />\s*<b>Calories:</b>(?P<calories>.+?)<br />')
    for item in items:
        itemUrl = item.get('href')
        name = item.text.strip()
        try:
            itemResponse = requests.get(itemUrl)
            itemResponse.raise_for_status()
        except requests.RequestException:
            return None
        raw = itemResponse.text
        matches = nutritionRegex.search(raw)
        if not matches:
            return None
        info = matches.groupdict()
        info['name'] = name
        menu.append(info)
    return menu

def reformat(date):
    part = re.match(r"(\d{4})-(\d{2})-(\d{2})", date)
    new = f"{part.group(2)}-{part.group(3)}-{part.group(1)}"
    return new




        
