from flask import Flask, request, jsonify
import uuid
import os
import json
from chatbot_copy import chat_step, load_state, save_state

app = Flask(__name__)

STATE_DIR = "conversations"
os.makedirs(STATE_DIR, exist_ok=True)

def get_state_file(conversation_id: str):
    return os.path.join(STATE_DIR, f"{conversation_id}.json")

@app.route("/initialize", methods=["POST"])
def initialize():
    """Start a new conversation"""
    conversation_id = str(uuid.uuid4())
    state = {"answers": {}, "messages": [], "question_index": 0, "skip": 0, "attempt_counter": {}}

    # Save initial state
    save_state(state, get_state_file(conversation_id))

    # First question comes from chat_step with empty input
    result = chat_step(state, "")
    return jsonify({
        "conversation_id": conversation_id,
        "reply": result["reply"],
        "state": result["state"],
        "done": result["done"]
    })

@app.route("/chat-step", methods=["POST"])
def chat_step_endpoint():
    """Send a message and get chatbot reply"""
    data = request.json
    conversation_id = data.get("conversation_id")
    user_input = data.get("user_input", "")

    if not conversation_id:
        return jsonify({"error": "conversation_id required"}), 400

    state_file = get_state_file(conversation_id)
    if os.path.exists(state_file):
        state = load_state(state_file)
    else:
        return jsonify({"error": "Conversation not found"}), 404

    result = chat_step(state, user_input)

    # Persist new state
    save_state(result["state"], state_file)

    return jsonify(result)

@app.route("/load-conversation/<conversation_id>", methods=["GET"])
def load_conversation(conversation_id):
    """Resume an existing conversation"""
    state_file = get_state_file(conversation_id)
    if not os.path.exists(state_file):
        return jsonify({"error": "Conversation not found"}), 404

    state = load_state(state_file)
    return jsonify({"conversation_id": conversation_id, "state": state})

@app.route("/save-conversation/<conversation_id>", methods=["POST"])
def save_conversation(conversation_id):
    """Manually save state (optional)"""
    data = request.json
    state = data.get("state")
    if not state:
        return jsonify({"error": "State required"}), 400

    save_state(state, get_state_file(conversation_id))
    return jsonify({"message": "Conversation saved"})

@app.route("/delete-conversation/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    """Delete a conversation and its state file"""
    state_file = get_state_file(conversation_id)
    if os.path.exists(state_file):
        os.remove(state_file)
        return jsonify({"message": "Conversation deleted"})
    return jsonify({"error": "Conversation not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
