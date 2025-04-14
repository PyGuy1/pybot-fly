from flask import Flask, request, jsonify, session
import google.generativeai as genai
import os
import secrets
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

# Initialize the Gemini model with the proper version (ensure you include the version suffix)
MODEL_NAME = "gemini-1.5-flash-001"

# Home route
@app.route("/")
def home():
    return "PyBot is running at https://pybot-fly.onrender.com"

# Ping route
@app.route("/ping")
def ping():
    return "pong"

# Cache creation route
def create_cache(conversation_history):
    """Create a cache for context storage"""
    try:
        cache = genai.caches.create(
            model=MODEL_NAME,
            config=genai.types.CreateCachedContentConfig(
                display_name='chat-session-cache',  # Cache identifier
                system_instruction="You are a helpful assistant. Respond in a clear and concise manner.",
                contents=conversation_history,
                ttl="3600s",  # Cache will expire in 1 hour
            )
        )
        return cache
    except Exception as e:
        print(f"Error creating cache: {str(e)}")
        return None

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

    # Create or fetch the cache based on the conversation history
    cache = create_cache(session["conversation_history"])

    if not cache:
        return jsonify({"reply": "⚠️ Failed to create cache for the conversation. Try again later."}), 500

    # Use the cache for context in the request
    try:
        response = genai.models.generate_content(
            model=MODEL_NAME,
            contents=[
                {"text": "You are PyBot, a helpful assistant."},  # Instructions for the assistant
                {"text": message},  # Current user message
            ],
            config=genai.types.GenerateContentConfig(cached_content=cache.name)  # Use the cached content
        )

        # Add the bot's response to the conversation history
        session["conversation_history"].append({"role": "bot", "text": response.text})

        return jsonify({"reply": response.text})

    except Exception as e:
        return jsonify({"reply": f"⚠️ Error talking to server: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
