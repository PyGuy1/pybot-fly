from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Session Configuration
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16):
    logging.warning("FLASK_SECRET_KEY not set, using temporary secret key. Sessions may not persist across restarts.")

Session(app)

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initial prompts
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

    # Initialize or validate history
    if "history" not in session:
        logging.info(f"New session ({session.sid}): Initializing chat history.")
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]
    elif not isinstance(session["history"], list):
        logging.warning(f"Session ({session.sid}): History is not a list. Re-initializing.")
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    # Add user message
    session["history"].append({"role": "user", "parts": [message]})

    # Limit conversation length
    MAX_HISTORY_TURNS = 10
    max_messages = (MAX_HISTORY_TURNS * 2) + 2  # +2 for SYSTEM_PROMPT and INITIAL_MODEL_RESPONSE
    if len(session["history"]) > max_messages:
        session["history"] = session["history"][:2] + session["history"][-MAX_HISTORY_TURNS * 2:]

    # Flatten conversation for Gemini input
    conversation = []
    for msg in session["history"]:
        role = msg["role"]
        content = " ".join(msg["parts"])
        if role == "user":
            conversation.append(f"User: {content}")
        elif role == "model":
            conversation.append(f"PyBot: {content}")

    # Add "PyBot:" as the next expected response
    history_text = "\n".join(conversation) + "\nPyBot:"

    try:
        response = model.generate_content(history_text)

        if not response.parts:
            logging.warning(f"Session ({session.sid}): Gemini returned no parts.")
            return jsonify({"reply": "⚠️ I received an empty response from the AI. Please try again."}), 500

        reply = response.text.strip()
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        logging.info(f"Session ({session.sid}): Successfully generated reply.")
        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Session ({session.sid}): Error during Gemini API call: {str(e)}", exc_info=True)
        return jsonify({"reply": "⚠️ Error communicating with the AI service. Please try again later."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
