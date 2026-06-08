import os
import json
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_data(f):
    if not os.path.exists(f): return []
    try:
        with open(f, 'r') as file: return json.load(file)
    except: return []

def save_data(f, data):
    with open(f, 'w') as file: json.dump(data, file)

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    msg = user_input.lower()

    # --- 1. DASHBOARD / STATUS ---
    if any(k in msg for k in ["dashboard", "status", "info"]):
        jadwal = load_data("jadwal.json")
        notes = load_data("notes.json")
        reply = "-- DASHBOARD --\n[JADWAL]: " + ("\n".join([f"{i+1}. {j}" for i, j in enumerate(jadwal)]) if jadwal else "KOSONG")
        reply += "\n\n[NOTES]: " + ("\n".join([f"- {n}" for n in notes]) if notes else "KOSONG")
        return jsonify({"reply": reply})

    # --- 2. HAPUS LOGIC (Apapun yang ada kata 'hapus') ---
    if "hapus" in msg or "selesai" in msg or "buang" in msg:
        target = re.sub(r'(hapus|selesai|buang|tugas|jadwal|note|catatan)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = load_data("jadwal.json")
        new_jadwal = [j for j in jadwal if target not in j.lower()]
        save_data("jadwal.json", new_jadwal)
        return jsonify({"reply": f"EVE: '{target.upper()}' BERHASIL DIHAPUS DARI JADWAL."})

    # --- 3. NOTE LOGIC (Khusus buat yang ada kata 'note') ---
    if "note" in msg or "catat" in msg:
        note_content = re.sub(r'(note|catat|tulis)', '', msg, flags=re.IGNORECASE).strip()
        notes = load_data("notes.json")
        notes.append(note_content)
        save_data("notes.json", notes)
        return jsonify({"reply": f"EVE: NOTE DISIMPAN: {note_content.upper()}"})

    # --- 4. JADWAL LOGIC (Sisanya) ---
    if any(k in msg for k in ["pasang", "tambah", "jadwal"]):
        task = re.sub(r'(pasang|tambah|jadwal|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = load_data("jadwal.json")
        jadwal.append(task)
        save_data("jadwal.json", jadwal)
        return jsonify({"reply": f"EVE: TUGAS DITAMBAHKAN: {task.upper()}"})

    # --- 5. GLOBAL AI ---
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": user_input}]}
        )
        return jsonify({"reply": "EVE: " + response.json()['choices'][0]['message']['content'].upper()})
    except:
        return jsonify({"reply": "EVE: AI ERROR."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
