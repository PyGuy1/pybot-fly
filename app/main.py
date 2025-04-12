from flask import Flask, request, jsonify, session
import google.generativeai as genai
import os
import secrets  # For generating a random secret key
from flask_cors import CORS
from flask_session import Session

app = Flask(__name__)
CORS(app)

# Auto-generate a random secret key if not set in environment variable
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(24))

# Use flask-session to store session data
app.config["SESSION_TYPE"] = "filesystem"  # or "redis" if you want a persistent store
Session(app)

# Get Gemini API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set!")

# Configure the Gemini model
genai.configure(api_key=GEMINI_API_KEY)

# Home route
@app.route("/")
def home():
    return "PyBot is running at https://pybot-fly.onrender.com"

# Ping route
@app.route("/ping")
def ping():
    return "pong"

# Chat route
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    if not message:
        return jsonify({"reply": "Please enter a message!"}), 400

    # Initialize conversation history if it doesn't exist
    if "conversation_history" not in session:
        session["conversation_history"] = []

    # Add the user's message to the conversation history
    session["conversation_history"].append({"role": "user", "text": message})

    # Instruction for the Gemini model
    instructions = "You are PyBot, a helpful assistant developed by PyGuy. Always respond in a clear, concise, and friendly manner. Keep your responses informative but simple, avoiding unnecessary complexity."

    try:
        # Prepare the conversation history and instructions
        conversation_history = session["conversation_history"]
        conversation_history_str = "\n".join([f"{entry['role']}: {entry['text']}" for entry in conversation_history])

        # Generate content using the Gemini API with instructions and history
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(
            contents=[
                {"text": instructions},  # Add the instructions
                {"text": conversation_history_str},  # Add the conversation history
                {"text": message}  # Add the current message from the user
            ]
        )

        # Add the bot's response to the conversation history
        session["conversation_history"].append({"role": "bot", "text": response.text})

        return jsonify({"reply": response.text})

    except Exception as e:
        return jsonify({"reply": f"⚠︎ Error talking to server: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0")
