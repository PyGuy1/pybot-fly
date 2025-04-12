from flask import Flask, request, jsonify
import google.generativeai as genai
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Get Gemini API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set!")

# Configure the Gemini model
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

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

    # Generate reply from Gemini with the correct parameters
    response = model.generate_content(
        prompt=message,  # Adjust to correct parameter for prompt
        instructions="You are PyBot, a helpful assistant developed by AEVIX. Always respond in a clear, concise, and friendly way."  # Adjust if needed
    )

    return jsonify({"reply": response.text})

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0")
