from flask import Flask, request, jsonify
import google.generativeai as genai
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in environment variables!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

@app.route("/")
def home():
    return "PyBot is running!"

@app.route("/ping")
def ping():
    return "pong"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    if not message:
        return jsonify({"reply": "Please enter a message!"}), 400
    response = model.generate_content(message)
    return jsonify({"reply": response.text})

# Run the app without manually specifying a port
if __name__ == "__main__":
    app.run(host="0.0.0.0")
