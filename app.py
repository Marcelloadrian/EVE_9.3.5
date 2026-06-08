import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JADWAL_FILE = "jadwal.json"

def load_jadwal():
    if not os.path.exists(JADWAL_FILE): return []
    with open(JADWAL_FILE, 'r') as f: return json.load(f)

def save_jadwal(data):
    with open(JADWAL_FILE, 'w') as f: json.dump(data, f)

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    msg_lower = user_input.lower()
    
    # 1. Routing Lokal: Kelola Jadwal
    if "jadwal" in msg_lower or "schedule" in msg_lower:
        jadwal = load_jadwal()
        if "tambah" in msg_lower or "catat" in msg_lower:
            new_task = user_input.replace("tambah", "").replace("catat", "").strip()
            jadwal.append(new_task)
            save_jadwal(jadwal)
            return jsonify({"reply": "EVE (Local): Oke, sudah dicatat: " + new_task})
        else:
            return jsonify({"reply": "EVE (Local): Jadwal kamu: " + (", ".join(jadwal) if jadwal else "Kosong")})

    # 2. Routing Global: Tanya AI Groq
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": user_input}]
            }
        )
        reply = response.json()['choices'][0]['message']['content']
        return jsonify({"reply": "EVE (Global): " + reply})
    except Exception as e:
        return jsonify({"reply": "EVE: Error koneksi ke server global."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
