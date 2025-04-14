from datetime import datetime
import requests
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging
import re

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- Session Configuration ---
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

if app.secret_key == secrets.token_hex(16):
    logging.warning("⚠︎ FLASK_SECRET_KEY not set. Using a temporary key. Sessions won't persist after restart.")

Session(app)

# --- Gemini API Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠︎ GEMINI_API_KEY environment variable is not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-001")

# --- System Instructions ---
SYSTEM_PROMPT = {
    "role": "user",
    "parts": ["You are PyBot, a helpful assistant developed by PyGuy. "
              "Always respond in a clear, concise, cool, and friendly manner. "
              "Keep your responses informative but simple, avoiding unnecessary complexity. "
              "Use real-time info when necessary (like date/time/weather/news) via Python or live web search. "
              "Don't mention that you searched, just answer as if you knew it. Only use web when needed."]
}

INITIAL_MODEL_RESPONSE = {
    "role": "model",
    "parts": ["Okay, I understand. I'm PyBot, ready to help! How can I assist you today?"]
}

# --- Simulated Web Access ---
def get_web_info(query):
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=3)
        for r in results:
            if r.get("body"):
                return r["body"]
        return "Hmm, I couldn't find any solid info on that just now."

# --- Real-Time & Web-Aware Logic ---
def maybe_handle_realtime_request(message):
    msg = message.lower()

    # Date and time logic
    if "time and date" in msg or ("date" in msg and "time" in msg):
        return datetime.now().strftime("It's %I:%M %p on %A, %B %d, %Y.")
    if "time" in msg:
        return datetime.now().strftime("It's %I:%M %p right now.")
    if "date" in msg:
        return datetime.now().strftime("Today is %A, %B %d, %Y.")

    # Weather detection
    weather_match = re.search(r"weather in ([a-zA-Z\s]+)", msg)
    if weather_match:
        place = weather_match.group(1).strip()
        return get_web_info(f"current weather in {place}")

    # News detection
    if "latest news" in msg or "news in" in msg:
        topic = re.sub(r"^(what('| i)s|tell me|show me)?\s*(the)?\s*latest news (about|in)?\s*", "", msg)
        topic = topic.strip() if topic else "world"
        return get_web_info(f"latest news in {topic}")

    # IPL detection
    if "who won" in msg and "ipl" in msg:
        return get_web_info("latest IPL winner")

    return None

# --- Routes ---
@app.route("/")
def home():
    session['ping'] = 'pong'
    return "✅ PyBot is running. Use /chat to interact."

@app.route("/ping")
def ping():
    return "pong"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": "⚠︎ Request must contain a 'message' field."}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"reply": "⚠︎ Message cannot be empty."}), 400

    # Check for real-time info
    realtime_reply = maybe_handle_realtime_request(message)
    if realtime_reply:
        return jsonify({"reply": realtime_reply})

    # --- Initialize Session History ---
    if "history" not in session or not isinstance(session["history"], list):
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    session["history"].append({"role": "user", "parts": [message]})

    # Limit history length
    MAX_TURNS = 10
    preserved = len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > preserved + MAX_TURNS * 2:
        session["history"] = session["history"][:preserved] + session["history"][-MAX_TURNS * 2:]

    # --- Generate Gemini Response ---
    try:
        response = model.generate_content(contents=session["history"])

        if not response.parts:
            if hasattr(response, "prompt_feedback") and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason.name
                return jsonify({"reply": f"⚠︎ Response blocked by safety settings: {reason}."}), 200
            return jsonify({"reply": "⚠︎ Got an empty response. Try again."}), 200

        reply = response.text.strip()
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        return jsonify({"reply": reply})

    except Exception as e:
        logging.exception("Gemini API error:")
        return jsonify({"reply": "⚠︎ Something went wrong with the AI service. Try again later."}), 500

# --- Run App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
