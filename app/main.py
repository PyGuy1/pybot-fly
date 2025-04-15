from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os, secrets, logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz

app = Flask(__name__)
CORS(app, supports_credentials=True)

instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
Session(app)

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠︎ GEMINI_API_KEY not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-001")

SYSTEM_PROMPT = {
    "role": "user",
    "parts": ["You are PyBot, a helpful assistant developed by PyGuy. "
              "Always respond in a clear, concise, cool, and friendly manner. "
              "Keep your responses informative but simple, avoiding unnecessary complexity."]
}
INITIAL_MODEL_RESPONSE = {
    "role": "model",
    "parts": ["Okay, I understand. I'm PyBot, ready to help!"]
}

# Get time from location (city or timezone)
def get_time(location="Asia/Kolkata"):
    try:
        tz = pytz.timezone(location if "/" in location else f"Etc/GMT{location}")
    except:
        tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)
    return now.strftime("%I:%M %p on %A, %B %d, %Y")

# Search Google (used for weather, IPL, news)
def search_web(query):
    try:
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        result = soup.find("div", class_="BNeawe").text
        return result
    except:
        return None

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").lower().strip()
    user_location = data.get("location", "").strip()  # From frontend

    if not message:
        return jsonify({"reply": "⚠︎ Please type something."}), 400

    # Time
    if "time" in message or "date" in message:
        reply = get_time(user_location or "Asia/Kolkata")
        return jsonify({"reply": reply})

    # Weather
    if "weather" in message:
        location = user_location or "your area"
        weather = search_web(f"current weather in {location}")
        if weather:
            return jsonify({"reply": weather})
        return jsonify({"reply": "⚠︎ Unable to get weather."})

    # IPL
    if "ipl" in message and "won" in message:
        result = search_web("who won latest IPL 2024 match")
        if result:
            return jsonify({"reply": result})
        return jsonify({"reply": "⚠︎ Unable to get IPL result."})

    # News
    if "news" in message or "headlines" in message:
        result = search_web("latest WHO news")
        if result:
            return jsonify({"reply": result})
        return jsonify({"reply": "⚠︎ No news found."})

    # Gemini fallback
    if "history" not in session or not isinstance(session["history"], list):
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    session["history"].append({"role": "user", "parts": [message]})

    MAX_TURNS = 10
    preserved = len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > preserved + MAX_TURNS * 2:
        session["history"] = session["history"][:preserved] + session["history"][-MAX_TURNS * 2:]

    try:
        response = model.generate_content(contents=session["history"])
        reply = response.text.strip()
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True
        return jsonify({"reply": reply})
    except Exception:
        return jsonify({"reply": "⚠︎ Gemini AI is currently down. Try again."}), 500

@app.route("/")
def home():
    return "✅ PyBot backend running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
