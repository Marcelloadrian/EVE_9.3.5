import os
import json
import requests
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Memori percakapan (Dictionary untuk menyimpan history per session)
chat_memory = {}

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
    
    # Update Memory (Simpan 10 pesan terakhir)
    history = chat_memory.get("user", [])
    history.append({"role": "user", "content": user_input})
    if len(history) > 10: history.pop(0)
    chat_memory["user"] = history
    
    # --- INTENT DETECTION ---
    is_jadwal = any(k in msg for k in ["jadwal", "schedule", "tugas", "ingetin", "ingatkan"])
    is_note = any(k in msg for k in ["note", "arsip", "catatan"])
    is_dashboard = any(k in msg for k in ["dashboard", "status", "keadaan terkini", "info"])
    is_add = any(k in msg for k in ["pasang", "tambah", "buat", "catat", "save"])
    is_delete = any(k in msg for k in ["hapus", "selesai", "buang"])

    # 1. DASHBOARD
    if is_dashboard:
        jadwal = load_data("jadwal.json")
        notes = load_data("notes.json")
        reply = "-- EVE SYSTEM DASHBOARD --\n[JADWAL]: " + str(len(jadwal)) + " item\n[ARSIP]: " + str(len(notes)) + " item\n\n"
        reply += "\n".join([f"{i+1}. {j.upper()}" for i, j in enumerate(jadwal)])
        return jsonify({"reply": reply})

    # 2. LOGIC JADWAL & NOTES (Local)
    elif is_jadwal or is_note:
        db_file = "jadwal.json" if is_jadwal else "notes.json"
        data_list = load_data(db_file)
        
        if is_add:
            item = re.sub(r'(pasang|tambah|buat|catat|save|note|arsip|catatan|jadwal|schedule|tugas|ingetin|ingatkan)', '', user_input, flags=re.IGNORECASE).strip()
            data_list.append(item)
            save_data(db_file, data_list)
            return jsonify({"reply": "EVE (LOCAL): DITAMBAHKAN KE " + db_file.replace(".json", "").upper()})
        
        elif is_delete and is_jadwal:
            target = re.sub(r'(hapus|selesai|buang|jadwal|schedule|tugas|ingetin|ingatkan)', '', user_input, flags=re.IGNORECASE).strip()
            data_list = [j for j in data_list if target.lower() not in j.lower()]
            save_data(db_file, data_list)
            return jsonify({"reply": f"EVE (LOCAL): TUGAS '{target.upper()}' DIPROSES."})
        
        return jsonify({"reply": "LIST:\n" + "\n".join([f"- {i.upper()}" for i in data_list])})

    # 3. GLOBAL AI (With Context Memory)
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": history # Kirim history supaya tidak pikun
            }
        )
        ai_reply = response.json()['choices'][0]['message']['content']
        history.append({"role": "assistant", "content": ai_reply})
        return jsonify({"reply": "EVE (GLOBAL): " + ai_reply.upper()})
    except Exception as e:
        return jsonify({"reply": "EVE: GLOBAL INTERFACE ERROR - " + str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
