from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Session config
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

if app.secret_key == secrets.token_hex(16):
    logging.warning("FLASK_SECRET_KEY not set, using temporary secret key. Sessions may not persist across restarts.")

Session(app)

# Gemini API config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initial instructions and system prompt
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

@app.route("/chat", methods=["POST"])
def chat():
    logging.info(f"Chat request received. Session ID: {session.sid if session else 'No Session'}")

    data = request.get_json()
    if not data or "message" not in data:
        logging.warning("Chat request missing 'message' field.")
        return jsonify({"reply": "Request body must be JSON with a 'message' field."}), 400

    message = data["message"].strip()
    if not message:
        logging.warning("Chat request received empty 'message'.")
        return jsonify({"reply": "Please enter a non-empty message!"}), 400

    # Initialize or reset session history
    if "history" not in session or not isinstance(session["history"], list):
        logging.info(f"Initializing session history.")
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    # Add user's message to history
    session["history"].append({"role": "user", "parts": [message]})

    # Limit the history length to avoid exceeding token limits
    MAX_HISTORY_TURNS = 10
    base_length = len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > base_length + MAX_HISTORY_TURNS * 2:
        session["history"] = session["history"][:base_length] + session["history"][-MAX_HISTORY_TURNS * 2:]

    try:
        # Generate response using Gemini API
        response = model.generate_content(contents=session["history"])

        if not response.parts:
            logging.warning(f"Empty response from Gemini.")
            return jsonify({"reply": "⚠️ I received an empty response from the AI. Please try again."}), 500

        reply = response.text.strip()
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        logging.info("Reply successfully generated.")
        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Gemini API error: {str(e)}", exc_info=True)
        return jsonify({"reply": "⚠️ Error communicating with the AI service. Please try again later."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
