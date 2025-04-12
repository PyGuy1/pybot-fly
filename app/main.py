import os
import secrets
from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Automatically generate SECRET_KEY if not set
if not app.config.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = secrets.token_hex(16)

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
    data = request.get_json()
    message = data.get("message", "")
    if not message:
        return jsonify({"reply": "Please enter a message!"}), 400

    try:
        # Generate reply from Gemini using the correct method
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(
            contents=message  # Use 'contents' as the argument name
        )

        return jsonify({"reply": response.text})

    except Exception as e:
        return jsonify({"reply": f"⚠︎ Error talking to server: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0")
