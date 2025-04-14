from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Enable cross-origin cookies for session tracking

# --- Session Configuration ---
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16):
    logging.warning("FLASK_SECRET_KEY not set, using temporary secret key. Sessions may not persist across restarts.")

Session(app)

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-001")

# Initial system instruction and first response
SYSTEM_PROMPT = {
    "role": "user",
    "parts": [
        "You are PyBot, a helpful assistant developed by PyGuy. "
        "Always respond in a clear, concise, cool, and friendly manner. "
        "Keep your responses informative but simple, avoiding unnecessary complexity."
    ]
}

INITIAL_MODEL_RESPONSE = {
    "role": "model",
    "parts": ["Okay, I understand. I'm PyBot, ready to help! How can I assist you today?"]
}

@app.route("/")
def home():
    session['ping'] = 'pong'
    logging.info("Home route accessed.")
    return "PyBot is running. Check /chat endpoint."

@app.route("/ping")
def ping():
    return "pong"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": "⚠︎ Request must contain a 'message' field."}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"reply": "⚠︎ Please enter a non-empty message!"}), 400

    # Initialize chat history if not already present
    if "history" not in session or not isinstance(session["history"], list):
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    # Add user message
    session["history"].append({"role": "user", "parts": [user_message]})

    # Limit history to last 10 turns (+2 system messages)
    MAX_TURNS = 10
    base_len = len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > base_len + MAX_TURNS * 2:
        session["history"] = session["history"][:base_len] + session["history"][-MAX_TURNS * 2:]

    try:
        response = model.generate_content(contents=session["history"])

        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason.name
                reply = f"⚠︎ My response was blocked due to safety settings ({reason}). Try rephrasing your message."
            else:
                reply = "⚠︎ I received an empty response. Please try again."
        else:
            reply = response.text.strip()

        # Save response to session
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Gemini API Error: {str(e)}", exc_info=True)
        return jsonify({"reply": "⚠︎ Error communicating with the AI service. Please try again later."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
