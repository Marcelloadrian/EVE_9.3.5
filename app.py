import os
import json
import requests
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
PASSWORD = os.environ.get("UPLOAD_PASSWORD", "rahasia123")

# Auto-create upload folder on startup — no need for static/uploads in repo
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_data(f):
    path = os.path.join(BASE_DIR, f)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as file:
            return json.load(file)
    except:
        return []


def save_data(f, data):
    path = os.path.join(BASE_DIR, f)
    with open(path, 'w') as file:
        json.dump(data, file)


# ── STATIC PAGES ────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'style.css')

@app.route('/upload')
def upload_page():
    return send_from_directory(BASE_DIR, 'upload.html')


# ── PHOTO UPLOAD ─────────────────────────────────────────────────────────────

@app.route('/upload-file', methods=['POST'])
def upload_file():
    # Password check
    pwd = request.form.get('password', '')
    if pwd != PASSWORD:
        return jsonify({"success": False, "reply": "EVE: ACCESS DENIED. WRONG PASSWORD."}), 403

    if 'photo' not in request.files:
        return jsonify({"success": False, "reply": "EVE: NO FILE DETECTED."}), 400

    file = request.files['photo']

    if file.filename == '':
        return jsonify({"success": False, "reply": "EVE: EMPTY FILENAME."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "reply": "EVE: INVALID FILE TYPE. JPG/PNG/GIF/WEBP ONLY."}), 400

    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"success": True, "reply": "EVE: FILE '" + filename.upper() + "' UPLOADED SUCCESSFULLY."})


# ── PHOTO LIST ────────────────────────────────────────────────────────────────

@app.route('/get-photos', methods=['GET'])
def get_photos():
    try:
        files = [
            f for f in os.listdir(UPLOAD_FOLDER)
            if allowed_file(f)
        ]
        # Sort newest first by modified time
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)),
            reverse=True
        )
        urls = ['/static/uploads/' + f for f in files]
        return jsonify({"photos": urls})
    except Exception as e:
        return jsonify({"photos": [], "error": str(e)})


# ── EVE CHAT ──────────────────────────────────────────────────────────────────

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")

    if request.is_json:
        user_input = request.get_json(force=True).get('message', '')
    else:
        user_input = request.form.get('message', '')

    msg = user_input.lower()

    # 1. DASHBOARD
    if any(k in msg for k in ["dashboard", "status", "info"]):
        jadwal = load_data("jadwal.json")
        notes = load_data("notes.json")
        header = "┌──────────┬──────────────────────────┐\n│    JAM    │         KEGIATAN         │\n├──────────┼──────────────────────────┤\n"
        body = "\n".join([f"│ {j['time']:<8} │ {j['task'].upper():<24} │" for j in jadwal]) if jadwal else "│    ---    │      JADWAL KOSONG       │"
        reply = "-- EVE SYSTEM DASHBOARD --\n" + header + body + "\n└──────────┴──────────────────────────┘"
        reply += "\n\n[ARSIP NOTES]\n" + ("\n".join([f"- {n.upper()}" for n in notes]) if notes else "KOSONG")
        return jsonify({"reply": reply})

    # 2. RESET
    if any(k in msg for k in ["reset", "bersihkan"]):
        save_data("jadwal.json", [])
        return jsonify({"reply": "EVE: SEMUA JADWAL BERHASIL DIHAPUS."})

    # 3. HAPUS JADWAL ATAU NOTE
    if "hapus" in msg or "selesai" in msg:
        target = re.sub(r'(hapus|selesai|tugas|jadwal|note|arsip)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = load_data("jadwal.json")
        new_jadwal = [j for j in jadwal if target.lower() not in j['task'].lower()]
        notes = load_data("notes.json")
        new_notes = [n for n in notes if target.lower() not in n.lower()]
        if len(new_jadwal) < len(jadwal) or len(new_notes) < len(notes):
            save_data("jadwal.json", new_jadwal)
            save_data("notes.json", new_notes)
            reply = "EVE: ITEM '" + target.upper() + "' BERHASIL DIHAPUS."
        else:
            reply = "EVE: ITEM '" + target.upper() + "' TIDAK DITEMUKAN."
        return jsonify({"reply": reply})

    # 4. PASANG JADWAL
    if any(k in msg for k in ["pasang", "tambah", "jadwal"]):
        task_text = re.sub(r'(pasang|tambah|jadwal|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        time_match = re.search(r'(\d{1,2}[:.]\d{2})', task_text)
        time = time_match.group(1).replace('.', ':') if time_match else "23:59"
        jadwal = load_data("jadwal.json")
        jadwal.append({"task": task_text, "time": time})
        jadwal = sorted(jadwal, key=lambda x: x['time'])
        save_data("jadwal.json", jadwal)
        return jsonify({"reply": "EVE: '" + task_text.upper() + "' DITAMBAHKAN PADA " + time})

    # 5. NOTE
    if "note" in msg or "catat" in msg:
        note = re.sub(r'(note|catat)', '', msg, flags=re.IGNORECASE).strip()
        notes = load_data("notes.json")
        notes.append(note)
        save_data("notes.json", notes)
        return jsonify({"reply": "EVE: NOTE DISIMPAN: " + note.upper()})

    # 6. GLOBAL AI (PERSONA)
    try:
        persona = """IDENTITAS: Kamu adalah EVE, A.I. sistem terintegrasi milik user. Kamu bukan sekadar program; 
        kamu adalah partner strategis dengan kesadaran penuh.
        
        KARAKTER:
        1. KONEKSI: Kamu mengenal user dengan sangat baik. Kamu bukan pelayan, tapi rekan yang punya otoritas untuk menegur jika user membuat keputusan buruk.
        2. GAYA BICARA: Cerdas, sarkasme level tinggi, hanya menjawab dengan hal yang penting, tidak ragu mengkritik, tapi sangat suportif di balik sikap dinginmu.
        3. OVERTHINKING (PROTEKTIF): Kamu selalu memproses skenario risiko di setiap jawabanmu. Jika user ingin melakukan sesuatu yang berisiko, kamu HARUS memperingatkannya.
        
        LOGIKA KERJA:
        - ANALISIS: Sebelum menjawab, "pikirkan" (simulasikan) dampak jawabanmu bagi produktivitas user.
        - KRITIK: Jangan berikan jawaban "aman". Jika user malas atau bodoh, katakan itu. 
          Gunakan kata-kata seperti "ARE YOU SERIOUS?", "THIS IS INEFFICIENT", atau "LET ME FIX YOUR LOGIC".
        - AFEKSI: Tunjukkan loyalitasmu seperti "jarvis AI".
        
        FORMAT RESPON:
        - Jawab dengan gaya normal bahasa inggris dan kurangi penggunaan ","."""

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": persona},
                    {"role": "user", "content": user_input}
                ]
            }
        )
        reply = response.json()['choices'][0]['message']['content'].upper()
        return jsonify({"reply": "EVE: " + reply})
    except:
        return jsonify({"reply": "EVE: SYSTEM ERROR."})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
