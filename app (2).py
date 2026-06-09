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

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    msg = user_input.lower()

    # 1. STATUS/DASHBOARD (Boxed Output)
    if any(k in msg for k in ["dashboard", "status", "info"]):
        jadwal = load_data("jadwal.json")
        notes = load_data("notes.json")
        
        header = "┌──────────┬──────────────────────────┐\n│   JAM    │         KEGIATAN         │\n├──────────┼──────────────────────────┤\n"
        body = "\n".join([f"│ {j['time']:<8} │ {j['task'].upper():<24} │" for j in jadwal]) if jadwal else "│   ---    │      JADWAL KOSONG       │"
        footer = "\n└──────────┴──────────────────────────┘"
        
        reply = "-- EVE SYSTEM DASHBOARD --\n" + header + body + footer
        reply += "\n\n[ARSIP NOTES]\n" + ("\n".join([f"- {n.upper()}" for n in notes]) if notes else "KOSONG")
        return jsonify({"reply": reply})

    # 2. RESET/BERSIHKAN (Semua)
    if any(k in msg for k in ["reset", "bersihkan", "kosongkan semua"]):
        save_data("jadwal.json", [])
        return jsonify({"reply": "EVE: SEMUA JADWAL BERHASIL DIHAPUS."})

    # 3. HAPUS SATU ITEM (Spesifik)
    if "hapus" in msg or "selesai" in msg:
        target = re.sub(r'(hapus|selesai|tugas|jadwal)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = load_data("jadwal.json")
        new_jadwal = [j for j in jadwal if target.lower() not in j['task'].lower()]
        
        if len(new_jadwal) < len(jadwal):
            save_data("jadwal.json", new_jadwal)
            reply = f"EVE: '{target.upper()}' BERHASIL DIHAPUS."
        else:
            reply = f"EVE: ITEM '{target.upper()}' TIDAK DITEMUKAN."
        return jsonify({"reply": reply})

    # 4. PASANG (Auto-Sort Time)
    if any(k in msg for k in ["pasang", "tambah", "jadwal"]):
        task_text = re.sub(r'(pasang|tambah|jadwal|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        time_match = re.search(r'(\d{1,2}[:.]\d{2})', task_text)
        time = time_match.group(1).replace('.', ':') if time_match else "23:59"
        
        jadwal = load_data("jadwal.json")
        jadwal.append({"task": task_text, "time": time})
        jadwal = sorted(jadwal, key=lambda x: x['time'])
        save_data("jadwal.json", jadwal)
        return jsonify({"reply": f"EVE: '{task_text.upper()}' DITAMBAHKAN PADA {time}"})

    # 5. NOTE
    if "note" in msg or "catat" in msg:
        note = re.sub(r'(note|catat)', '', msg, flags=re.IGNORECASE).strip()
        notes = load_data("notes.json")
        notes.append(note)
        save_data("notes.json", notes)
        return jsonify({"reply": f"EVE: NOTE DISIMPAN: {note.upper()}"})

    # 6. GLOBAL AI
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": user_input}]}
        )
        return jsonify({"reply": "EVE: " + response.json()['choices'][0]['message']['content'].upper()})
    except:
        return jsonify({"reply": "EVE: AI ERROR."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
