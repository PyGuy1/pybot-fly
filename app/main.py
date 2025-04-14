from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app, supports_credentials=True)  # Important for session cookies to work with frontend

# --- Session Configuration ---
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True

# Secret key setup
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16):
    logging.warning("FLASK_SECRET_KEY not set, using temporary key. Sessions may not persist across restarts.")

Session(app)

# --- Gemini API Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# --- System Prompt ---
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

# --- Routes ---

@app.route("/")
def home():
    session['ping'] = 'pong'
    logging.info(f"Home route accessed. Session: {session.get('ping')}")
    return "PyBot is running. Check /chat endpoint."

@app.route("/ping")
def ping():
    return "pong"

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    logging.info("Session reset triggered.")
    return jsonify({"status": "cleared"})

@app.route("/chat", methods=["POST"])
def chat():
    logging.info("Chat request received.")
    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"reply": "⚠️ Request body must be JSON with a 'message' field."}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"reply": "⚠️ Please enter a non-empty message!"}), 400

    # --- Initialize session history ---
    if "history" not in session or not isinstance(session["history"], list):
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    session["history"].append({"role": "user", "parts": [message]})

    # --- Trim old messages (optional) ---
    MAX_HISTORY_TURNS = 10
    max_messages = (MAX_HISTORY_TURNS * 2) + 2
    if len(session["history"]) > max_messages:
        session["history"] = session["history"][:2] + session["history"][-MAX_HISTORY_TURNS * 2:]

    try:
        # --- Call Gemini ---
        logging.info(f"Sending {len(session['history'])} messages to Gemini.")
        response = model.generate_content(contents=session["history"])

        if not response.parts:
            if response.prompt_feedback.block_reason:
                reason = response.prompt_feedback.block_reason.name
                reply = f"⚠️ My response was blocked due to safety settings ({reason}). Please rephrase your message."
            else:
                reply = "⚠️ I received an empty response from the AI. Please try again."
        else:
            reply = response.text.strip()

        # --- Save reply to session ---
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        return jsonify({"reply": reply})

    except Exception as e:
        logging.exception("Error during Gemini API call.")
        return jsonify({"reply": "⚠️ Error communicating with the AI service. Please try again later."}), 500

# --- Start Server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
