import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder='.')

# Pastikan GROQ_API_KEY sudah di-set di Environment Variables dashboard Render lo!
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    user_data = request.json
    user_input = user_data.get('message', '')
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "Kamu EVE, sekretaris AI yang efisien. Jawablah dengan ringkas dan profesional."},
            {"role": "user", "content": user_input}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        reply = response_data['choices'][0]['message']['content']
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Maaf, EVE sedang ada kendala teknis."}), 500

@app.route('/ping', methods=['GET'])
def ping():
    return "EVE is awake", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
