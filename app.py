import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Gunakan Environment Variable agar aman (jangan hardcode di sini)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

@app.route('/eve', methods=['POST'])
def eve_interface():
    user_input = request.json.get('message')
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "Kamu EVE, asisten sekretaris yang efisien. Jika user memberi jadwal, catat dengan format [JADWAL: nama - waktu]."},
            {"role": "user", "content": user_input}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        reply = response.json()['choices'][0]['message']['content']
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Maaf, EVE sedang ada gangguan teknis."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)