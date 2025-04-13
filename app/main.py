from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
import google.generativeai as genai
import os
import secrets
import logging # Optional: for better debugging

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, supports_credentials=True) # IMPORTANT: Ensure supports_credentials=True if your frontend needs to send cookies

# --- Session Configuration ---
# Choose a secure, persistent location for session files if deploying
# The default might be a temporary directory depending on the OS/environment.
# Example: Use a subdirectory in your app's instance folder
instance_path = os.path.join(app.instance_path, 'flask_session')
os.makedirs(instance_path, exist_ok=True) # Ensure the directory exists
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = instance_path
app.config["SESSION_PERMANENT"] = True # Make sessions permanent until they expire (default: True)
# app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1) # Optional: Set session expiry time
# Secret key for Flask session (needs to be consistent across restarts)
# Using secrets.token_hex() generates a new key *every time the app starts*.
# For persistent sessions, you NEED a fixed secret key. Store it securely.
# Option 1: Hardcode (NOT recommended for production)
# app.secret_key = "your_super_secret_and_unchanging_key"
# Option 2: Environment variable (Recommended)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
if app.secret_key == secrets.token_hex(16): # Check if it fell back to default
    logging.warning("FLASK_SECRET_KEY not set, using temporary secret key. Sessions may not persist across restarts.")

Session(app) # Initialize Flask-Session AFTER configuration

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=GEMINI_API_KEY)
# Consider making the model configurable or choosing based on needs
# gemini-1.5-flash might be faster/cheaper for chat if context allows
model = genai.GenerativeModel(" gemini-2.0-flash-latest") # Use a specific or latest stable model

# Define the initial system prompt
SYSTEM_PROMPT = {
    "role": "user", # Gemini API often uses 'user' for the initial prompt directing the 'model'
    "parts": ["You are PyBot, a helpful assistant developed by PyGuy. "
              "Always respond in a clear, concise, cool, and friendly manner. "
              "Keep your responses informative but simple, avoiding unnecessary complexity."]
}
# Define the first model response to guide the conversation start
INITIAL_MODEL_RESPONSE = {
    "role": "model",
    "parts": ["Okay, I understand. I'm PyBot, ready to help! How can I assist you today?"]
}


@app.route("/")
def home():
    # It's helpful to confirm session is working here too
    session['ping'] = 'pong' # Set a value
    logging.info(f"Home route accessed. Session ID: {session.sid if session else 'No Session'}")
    return "PyBot is running. Check /chat endpoint."

@app.route("/ping")
def ping():
    return "pong"

@app.route("/chat", methods=["POST"])
def chat():
    logging.info(f"Chat request received. Session ID: {session.sid if session else 'No Session'}") # Log session ID

    data = request.get_json()
    if not data or "message" not in data:
        logging.warning("Chat request missing 'message' field.")
        return jsonify({"reply": "Request body must be JSON with a 'message' field."}), 400

    message = data["message"].strip()
    if not message:
        logging.warning("Chat request received empty 'message'.")
        return jsonify({"reply": "Please enter a non-empty message!"}), 400

    # --- Session History Management ---
    # Initialize conversation history if it doesn't exist in the session
    if "history" not in session:
        logging.info(f"New session ({session.sid}): Initializing chat history.")
        # Start with the system prompt and the model's opening line
        session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]
        # Note: You might only want the SYSTEM_PROMPT depending on how you want the convo to start
        # session["history"] = [SYSTEM_PROMPT]
    else:
        # Basic type check in case session data got corrupted somehow
        if not isinstance(session["history"], list):
            logging.warning(f"Session ({session.sid}): History is not a list. Re-initializing.")
            session["history"] = [SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE]


    # --- Append User Message ---
    session["history"].append({"role": "user", "parts": [message]})

    # --- Optional: Limit History Length ---
    # Prevent history from growing indefinitely (saves tokens/cost and avoids context limits)
    MAX_HISTORY_TURNS = 10 # Keep last 10 pairs (user + model) + initial prompts
    # Calculate the number of messages to keep (2 per turn + initial messages)
    max_messages = (MAX_HISTORY_TURNS * 2) + len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])
    if len(session["history"]) > max_messages:
        logging.info(f"Session ({session.sid}): History limit reached. Trimming history.")
        # Keep the initial prompts and the most recent turns
        session["history"] = session["history"][:len([SYSTEM_PROMPT, INITIAL_MODEL_RESPONSE])] + session["history"][-MAX_HISTORY_TURNS*2:]


    # --- Call Gemini API ---
    try:
        # Send the current conversation history to Gemini
        # Ensure the history format matches Gemini's requirements (list of dicts with 'role' and 'parts')
        logging.info(f"Session ({session.sid}): Sending history to Gemini (length: {len(session['history'])} messages)")
        # print(f"DEBUG: Sending History: {session['history']}") # Uncomment for deep debugging

        response = model.generate_content(
            contents=session["history"]
            # Add safety_settings or generation_config if needed
            # generation_config=genai.types.GenerationConfig(
            #     candidate_count=1,
            #     temperature=0.7,
            # )
        )

        # --- Process Response ---
        # Handle potential lack of response or blocked content
        if not response.parts:
             # Check if it was blocked
            if response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason.name
                logging.warning(f"Session ({session.sid}): Gemini request blocked. Reason: {block_reason}")
                reply = f"⚠️ My response was blocked due to safety settings ({block_reason}). Please rephrase your message."
            else:
                logging.error(f"Session ({session.sid}): Gemini returned no parts and no block reason.")
                reply = "⚠️ I received an empty response from the AI. Please try again."
        else:
            reply = response.text.strip()


        # --- Append Model Response and Save Session ---
        session["history"].append({"role": "model", "parts": [reply]})
        session.modified = True  # Explicitly mark session as modified to ensure saving

        logging.info(f"Session ({session.sid}): Successfully generated reply.")
        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Session ({session.sid}): Error during Gemini API call: {str(e)}", exc_info=True) # Log traceback
        # Optionally, remove the last user message if the API call failed before getting a response
        # session["history"].pop()
        # session.modified = True
        return jsonify({"reply": f"⚠️ Error communicating with the AI service. Please try again later."}), 500

if __name__ == "__main__":
    # Use Waitress or Gunicorn for production instead of Flask's built-in server
    # Example: waitress-serve --host=0.0.0.0 --port=8080 your_app_module:app
    app.run(host="0.0.0.0", port=8080, debug=True) # Keep debug=True for development ONLY
