import os
import json
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- DATABASE UTILS ---
def load_data(filename):
    if not os.path.exists(filename): return []
    try:
        with open(filename, 'r') as f: return json.load(f)
    except: return []

def save_data(filename, data):
    with open(filename, 'w') as f: json.dump(data, f)

# --- ROUTES ---
@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    msg_lower = user_input.lower()
    
    # 1. LOGIC JADWAL (LOCAL)
    if any(k in msg_lower for k in ["jadwal", "schedule", "pasang", "tambah", "hapus"]):
        jadwal = load_data("jadwal.json")
        
        if "pasang" in msg_lower or "tambah" in msg_lower:
            new_task = re.sub(r'(pasang|tambah|jadwal|schedule)', '', user_input, flags=re.IGNORECASE).strip()
            if new_task:
                jadwal.append(new_task)
                save_data("jadwal.json", jadwal)
                return jsonify({"reply": "EVE (LOCAL): TUGAS DITAMBAHKAN: " + new_task.upper()})
            return jsonify({"reply": "EVE (LOCAL): APA YANG MAU DIPASANG?"})
        
        elif "hapus" in msg_lower:
            target = re.sub(r'(hapus|jadwal|schedule)', '', user_input, flags=re.IGNORECASE).strip()
            new_jadwal = [j for j in jadwal if target.lower() not in j.lower()]
            if len(new_jadwal) < len(jadwal):
                save_data("jadwal.json", new_jadwal)
                return jsonify({"reply": "EVE (LOCAL): TUGAS '" + target.upper() + "' BERHASIL DIHAPUS."})
            return jsonify({"reply": "EVE (LOCAL): TUGAS TIDAK DITEMUKAN."})
        
        else:
            header = "-- EVE SYSTEM LOG --\nSTATUS: " + str(len(jadwal)) + " TUGAS AKTIF\n"
            list_jadwal = "\n".join([f"{i+1}. {j.upper()}" for i, j in enumerate(jadwal)]) if jadwal else "KOSONG"
            return jsonify({"reply": header + list_jadwal + "\n--------------------"})

    # 2. LOGIC NOTES (LOCAL)
    elif "note" in msg_lower or "catatan" in msg_lower:
        notes = load_data("notes.json")
        if "note" in msg_lower and not "catatan" in msg_lower:
            new_note = re.sub(r'(note)', '', user_input, flags=re.IGNORECASE).strip()
            if new_note:
                notes.append(new_note)
                save_data("notes.json", notes)
                return jsonify({"reply": "EVE (LOCAL): CATATAN DISIMPAN: " + new_note.upper()})
        else:
            header = "-- EVE NOTES LOG --\n"
            list_notes = "\n".join([f"- {n.upper()}" for n in notes]) if notes else "KOSONG"
            return jsonify({"reply": header + list_notes + "\n--------------------"})

    # 3. LOGIC AI (GLOBAL)
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
        return jsonify({"reply": "EVE (GLOBAL): " + reply.upper()})
    except Exception as e:
        return jsonify({"reply": "EVE: GLOBAL INTERFACE ERROR - " + str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
