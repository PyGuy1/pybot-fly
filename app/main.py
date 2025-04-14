from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import secrets

app = Flask(__name__)
CORS(app)

# Automatically generate a secret key if not set
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "⚠︎ Please send a valid message."})

    # Get or initialize conversation history
    history = session.get("history", [])

    # Add user message
    history.append({"role": "user", "content": user_message})

    # Generate PyBot reply
    reply = generate_reply(history)

    # Add bot reply to history
    history.append({"role": "assistant", "content": reply})
    session["history"] = history  # Update session

    return jsonify({"reply": reply})


def generate_reply(history):
    """
    Simple logic for generating replies based on history.
    Replace this with actual LLM calls if needed.
    """
    last_user_message = history[-1]["content"].lower()

    if "hello" in last_user_message or "hi" in last_user_message:
        return "Hey there! I'm PyBot 🤖. How can I assist you today?"
    elif "who made you" in last_user_message:
        return "I was created by **PyGuy**, my awesome developer! 🚀"
    elif "clear" in last_user_message:
        session.pop("history", None)
        return "🧹 Chat history cleared. Let's start fresh!"
    else:
        return "I'm PyBot, your terminal-style assistant. I may not be super smart yet, but I’m here to help! 🔧"

@app.route("/")
def index():
    return jsonify({"message": "PyBot backend is running."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

