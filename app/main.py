from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
from datetime import datetime
import os, secrets, logging
import requests
from bs4 import BeautifulSoup
import pytz

# --- Flask Setup ---
app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- Session Config ---
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

if app.secret_key == secrets.token_hex(16):
    logging.warning("⚠︎ FLASK_SECRET_KEY not set. Using a temporary key. Sessions won't persist after restart.")

Session(app)

# --- Gemini Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠︎ GEMINI_API_KEY environment variable is not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-001")

# --- PyBot Prompt Instructions ---
SYSTEM_PROMPT = {
    "role": "user",
    "parts": ["You are PyBot, a helpful assistant developed by PyGuy. "
              "Always respond in a clear, concise, cool, and friendly manner. "
              "Keep your responses informative but simple, avoiding unnecessary complexity."]
}
INITIAL_MODEL_RESPONSE = {
    "role": "model",
    "parts": ["Okay, I understand. I'm PyBot, ready to help! How can I assist you today?"]
}

# --- Helper Functions ---

def get_time(timezone="Asia/Kolkata"):
    try:
        tz = pytz.timezone(timezone)
    except:
        tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)
    return now.strftime("%I:%M %p on %A, %B %d, %Y")

def search_web(query):
    try:
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        result = soup.find("div", class_="BNeawe").text
        return result
    except:
        return "⚠︎ Couldn't fetch the latest info. Please try again."

# --- Chat Route ---
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": "⚠︎ Request must contain a 'message' field."}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"reply": "⚠︎ Message cannot be empty."}), 400

    # Check for real-time queries first
    msg_lower = message.lower()

    if "time" in msg_lower or "date" in msg_lower:
        if "india" in msg_lower:
            return jsonify({"reply": f"🕒 It's {get_time('Asia/Kolkata')}."})
        return jsonify({"reply": f"🕒 It's {get_time()}."})

    if "weather" in msg_lower:
        location = msg_lower.split("in")[-1].strip() if "in" in msg_lower else "your area"
        result = search_web(f"weather in {location}")
        return jsonify({"reply": f"🌤 Weather in {location.title()}: {result}"})

    if "news" in msg_lower or "headlines" in msg_lower:
        result = search_web("latest WHO news")
        return jsonify({"reply": f"📰 WHO: {result}"})

    if "ipl" in msg_lower and "won" in msg_lower:
        result = search_web("who won latest IPL 2024")
        return jsonify({"reply": f"🏏 {result}"})

    # --- Gemini AI Chat Response ---
    if "history" not in session or not isinstance(session["history"], list):
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    session["history"].append({"role": "user", "parts": [message]})

    # Limit turns
    MAX_TURNS = 10
    preserved = len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > preserved + MAX_TURNS * 2:
        session["history"] = session["history"][:preserved] + session["history"][-MAX_TURNS * 2:]

    try:
        response = model.generate_content(contents=session["history"])
        reply = response.text.strip() if response.parts else "⚠︎ I couldn't understand. Please try again."

        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        return jsonify({"reply": reply})

    except Exception as e:
        logging.exception("Gemini API Error:")
        return jsonify({"reply": "⚠︎ AI service is currently facing an issue. Please try again later."}), 500

# --- Default Home Route ---
@app.route("/")
def home():
    return "✅ PyBot backend is live!"

@app.route("/ping")
def ping():
    return "pong"

# --- Run Server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
