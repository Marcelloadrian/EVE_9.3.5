import os
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data jadwal sementara (di memori)
jadwal_list = ["09:00 - Meeting Proyek", "14:00 - Review Kode"]

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '').lower()
    
    # LOGIC ROUTING:
    # Kalau user nanya jadwal, kita handle sendiri (Local)
    if "jadwal" in user_input or "schedule" in user_input:
        return jsonify({"reply": "EVE: Jadwal hari ini: " + ", ".join(jadwal_list)})
    
    # Kalau percakapan biasa (Local Logic/Simple)
    if len(user_input) < 30:
        return jsonify({"reply": "EVE (Local): " + user_input[::-1]}) # Contoh aja, ganti sama logika lokal lo
    
    # Kalau ribet, baru tembak ke Global API (Groq)
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama3-70b-8192", # Pakai model yang pinter buat yg ribet
                "messages": [{"role": "user", "content": user_input}]
            }
        )
        reply = response.json()['choices'][0]['message']['content']
        return jsonify({"reply": "EVE (Global): " + reply})
    except Exception as e:
        return jsonify({"reply": "EVE: Lagi ada masalah di koneksi global."})

if __name__ == '__main__':
    app.run(port=5000)
