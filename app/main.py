import os
import secrets
from flask import Flask, request, jsonify, session
import google.generativeai as genai
from flask_cors import CORS
from flask_session import Session  # Import Flask-Session

app = Flask(__name__)
CORS(app)

# Automatically generate SECRET_KEY if not set
if not app.config.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = secrets.token_hex(16)

# Set up server-side session storage
app.config['SESSION_TYPE'] = 'filesystem'  # This uses the filesystem to store sessions
app.config['SESSION_PERMANENT'] = False  # Sessions are not permanent by default
app.config['SESSION_USE_SIGNER'] = True  # Sign the session data for security
Session(app)  # Initialize Flask-Session

# Get Gemini API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set!")

# Configure the Gemini model with the correct API key
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
    # Initialize conversation history in session if not already set
    if 'conversation_history' not in session:
        session['conversation_history'] = []

    data = request.get_json()
    message = data.get("message", "")
    if not message:
        return jsonify({"reply": "Please enter a message!"}), 400

    try:
        # Add user message to conversation history
        session['conversation_history'].append(f"User: {message}")
        
        # Combine conversation history into a single prompt
        prompt = "You are PyBot, a helpful assistant developed by PyGuy. Always respond in a clear, concise, and friendly manner.\n"
        prompt += "\n".join(session['conversation_history'])  # Add history for context
        prompt += f"\nUser: {message}\nAssistant:"

        # Generate reply from Gemini using the correct method
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(
            contents=prompt  # Send prompt with instructions and conversation context
        )

        # Add the assistant's response to conversation history
        session['conversation_history'].append(f"Assistant: {response.text}")

        # Return the response
        return jsonify({"reply": response.text})

    except Exception as e:
        return jsonify({"reply": f"⚠︎ Error talking to server: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0")
