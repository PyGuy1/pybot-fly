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
CORS(app, supports_credentials=True)  # Ensure supports_credentials=True if your frontend needs to send cookies

# --- Session Configuration ---
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True)  # Ensure the directory exists
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True  # Make sessions permanent until they expire
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16):
    logging.warning("FLASK_SECRET_KEY not set, using temporary secret key. Sessions may not persist across restarts.")

Session(app)

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-001")  # Use a specific model version

# Define the initial system prompt
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

# --- Context Caching Configuration ---
def create_cache(contents):
    try:
        # Create a cache with a TTL of 5 minutes
        cache = genai.Caches.create(
            model=model.model_name,
            config=genai.types.CreateCachedContentConfig(
                display_name="PyBot Cache",  # Name the cache for identification
                system_instruction="You are an assistant capable of handling various requests.",
                contents=contents,
                ttl="300s",  # Cache for 5 minutes
            )
        )
        return cache
    except Exception as e:
        logging.error(f"Error creating cache: {e}")
        return None

@app.route("/")
def home():
    session['ping'] = 'pong'  # Set a value
    logging.info(f"Home route accessed. Session ID: {session.sid if session else 'No Session'}")
    return "PyBot is running. Check /chat endpoint."

@app.route("/ping")
def ping():
    return "pong"

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

    # --- Session History Management ---
    if "history" not in session:
        logging.info(f"New session ({session.sid}): Initializing chat history.")
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]
    else:
        if not isinstance(session["history"], list):
            logging.warning(f"Session ({session.sid}): History is not a list. Re-initializing.")
            session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]

    # Append user message
    session["history"].append({"role": "user", "parts": [message]})

    # Limit history length
    MAX_HISTORY_TURNS = 10
    max_messages = (MAX_HISTORY_TURNS * 2) + len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > max_messages:
        logging.info(f"Session ({session.sid}): History limit reached. Trimming history.")
        session["history"] = session["history"][:len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])] + session["history"][-MAX_HISTORY_TURNS*2:]

    # --- Call Gemini API ---
    try:
        logging.info(f"Session ({session.sid}): Sending history to Gemini (length: {len(session['history'])} messages)")

        # Create a cache of the current history for reuse
        cache = create_cache(session["history"])
        if cache:
            response = model.generate_content(
                contents=session["history"],
                config=genai.types.GenerateContentConfig(cached_content=cache.name)
            )
        else:
            response = model.generate_content(contents=session["history"])

        # --- Process Response ---
        if not response.parts:
            if response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason.name
                logging.warning(f"Session ({session.sid}): Gemini request blocked. Reason: {block_reason}")
                reply = f"?? My response was blocked due to safety settings ({block_reason}). Please rephrase your message."
            else:
                logging.error(f"Session ({session.sid}): Gemini returned no parts and no block reason.")
                reply = "?? I received an empty response from the AI. Please try again."
        else:
            reply = response.text.strip()

        # --- Append Model Response and Save Session ---
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True

        logging.info(f"Session ({session.sid}): Successfully generated reply.")
        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Session ({session.sid}): Error during Gemini API call: {str(e)}", exc_info=True)
        return jsonify({"reply": f"?? Error communicating with the AI service. Please try again later."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
