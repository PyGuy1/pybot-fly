import os
from flask import Flask, request, jsonify, session
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Get current time by timezone or default to India
def get_time(location=None):
    try:
        tz = pytz.timezone("Asia/Kolkata" if not location else location)
    except:
        tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)
    return now.strftime("%I:%M %p on %A, %B %d, %Y")

# Get result from web
def search_web(query):
    try:
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        result = soup.find("div", class_="BNeawe").text
        return result
    except Exception:
        return "⚠︎ Unable to fetch current info. Please try again later."

@app.route("/chat", methods=["POST"])
def chat():
    message = request.json.get("message", "").lower().strip()
    if not message:
        return jsonify({"response": "⚠︎ Please type something."})

    # Time and Date
    if "time" in message or "date" in message:
        if "india" in message:
            return jsonify({"response": f"It's {get_time('Asia/Kolkata')}."})
        return jsonify({"response": f"It's {get_time()}."})

    # Weather
    if "weather" in message:
        location = message.split("in")[-1].strip() if "in" in message else "your area"
        weather = search_web(f"weather in {location}")
        return jsonify({"response": f"Weather in {location.title()}: {weather}"})

    # News
    if "news" in message or "headlines" in message:
        headlines = search_web("latest WHO news")
        return jsonify({"response": f"WHO: {headlines}"})

    # IPL
    if "ipl" in message and "won" in message:
        result = search_web("who won latest IPL 2024")
        return jsonify({"response": result})

    # Default search fallback
    response = search_web(message)
    return jsonify({"response": response or "⚠︎ Sorry, I couldn’t find anything useful."})

@app.route("/")
def home():
    return "✅ PyBot backend is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

