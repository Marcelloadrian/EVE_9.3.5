import os
import json
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- DATABASE UTILS ---
def load_data(f):
    if not os.path.exists(f): return []
    try:
        with open(f, 'r') as file: return json.load(file)
    except: return []

def save_data(f, data):
    with open(f, 'w') as file: json.dump(data, file)

# --- ROUTES ---
@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    msg = user_input.lower()
    
    # --- FLEXIBLE INTENT DETECTION ---
    is_jadwal = any(k in msg for k in ["jadwal", "schedule", "tugas", "ingetin", "ingatkan"])
    is_note = any(k in msg for k in ["note", "arsip", "catatan"])
    is_dashboard = any(k in msg for k in ["dashboard", "status", "keadaan terkini", "info"])
    is_add = any(k in msg for k in ["pasang", "tambah", "buat", "catat", "save"])
    is_delete = any(k in msg for k in ["hapus", "selesai", "buang"])

    # 1. DASHBOARD / STATUS (Ringkasan Total)
    if is_dashboard:
        jadwal = load_data("jadwal.json")
        notes = load_data("notes.json")
        reply = "-- EVE SYSTEM DASHBOARD --\n"
        reply += "[JADWAL AKTIF]\n" + ("\n".join([f"{i+1}. {j.upper()}" for i, j in enumerate(jadwal)]) if jadwal else "KOSONG")
        reply += "\n\n[ARSIP NOTES]\n" + ("\n".join([f"- {n.upper()}" for n in notes]) if notes else "KOSONG")
        return jsonify({"reply": reply + "\n--------------------------"})

    # 2. LOGIC JADWAL (Flexible)
    elif is_jadwal:
        jadwal = load_data("jadwal.json")
        if is_add:
            task = re.sub(r'(pasang|tambah|buat|catat|save|jadwal|schedule|tugas|ingetin|ingatkan)', '', user_input, flags=re.IGNORECASE).strip()
            if task:
                jadwal.append(task)
                save_data("jadwal.json", jadwal)
                return jsonify({"reply": "EVE (LOCAL): TUGAS DITAMBAHKAN: " + task.upper()})
        elif is_delete:
            target = re.sub(r'(hapus|selesai|buang|jadwal|schedule|tugas|ingetin|ingatkan)', '', user_input, flags=re.IGNORECASE).strip()
            new_j = [j for j in jadwal if target.lower() not in j.lower()]
            save_data("jadwal.json", new_j)
            return jsonify({"reply": f"EVE (LOCAL): TUGAS '{target.upper()}' DIPROSES."})
        else:
            return jsonify({"reply": "JADWAL:\n" + ("\n".join([f"{i+1}. {j.upper()}" for i, j in enumerate(jadwal)]) if jadwal else "KOSONG")})

    # 3. LOGIC NOTES (Flexible)
    elif is_note:
        notes = load_data("notes.json")
        if is_add:
            note = re.sub(r'(note|arsip|catatan|pasang|tambah|buat|catat|save)', '', user_input, flags=re.IGNORECASE).strip()
            if note:
                notes.append(note)
                save_data("notes.json", notes)
                return jsonify({"reply": "EVE (LOCAL): CATATAN DISIMPAN: " + note.upper()})
        else:
            return jsonify({"reply": "ARSIP:\n" + ("\n".join([f"- {n.upper()}" for n in notes]) if notes else "KOSONG")})

    # 4. GLOBAL AI (Fallback)
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": user_input}]
            }
        )
        return jsonify({"reply": "EVE (GLOBAL): " + response.json()['choices'][0]['message']['content'].upper()})
    except Exception as e:
        return jsonify({"reply": "EVE: GLOBAL INTERFACE ERROR"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
