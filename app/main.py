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

    # Define custom instructions for the model's behavior
    custom_instructions = """
    You are PyBot, a helpful assistant developed by PyGuy. 
    Always respond in a clear, concise, and friendly manner.
    Keep your responses informative but simple, avoiding unnecessary complexity.
    """

    try:
        # Generate reply from Gemini with custom instructions
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(
            contents=message,  # The message from the user
            instructions=custom_instructions  # Pass the custom instructions
        )

        return jsonify({"reply": response.text})

    except Exception as e:
        return jsonify({"reply": f"⚠︎ Error talking to server: {str(e)}"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0")
