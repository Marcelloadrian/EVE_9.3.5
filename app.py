import os
import json
import requests
import re
import hashlib
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── Supabase (only for users + chat) ──────────────────────────────────────────
try:
    from supabase import create_client
    SUPA_URL = os.environ.get("SUPABASE_URL", "")
    SUPA_KEY = os.environ.get("SUPABASE_KEY", "")
    supa = create_client(SUPA_URL, SUPA_KEY) if SUPA_URL and SUPA_KEY else None
except Exception:
    supa = None

app = Flask(__name__)
CORS(app)

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

MASTER_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "rahasia123")
MASTER_PIN      = os.environ.get("MASTER_PIN", "0000")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — FILE (jadwal, notes, events, chat_history → tetap JSON di repo)
# ══════════════════════════════════════════════════════════════════════════════

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_data(f, default=None):
    if default is None: default = []
    path = os.path.join(BASE_DIR, f)
    if not os.path.exists(path): return default
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except: return default

def save_data(f, data):
    path = os.path.join(BASE_DIR, f)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def dm_room_id(u1, u2):
    pair = sorted([u1.lower(), u2.lower()])
    return pair[0] + "__" + pair[1]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — SUPABASE (users + chat)
# ══════════════════════════════════════════════════════════════════════════════

# ── USERS ──────────────────────────────────────────────────────────────────

def sb_get_user(username):
    """Return user row dict or None."""
    if not supa: return None
    try:
        res = supa.table("users").select("*").eq("username", username.lower()).execute()
        return res.data[0] if res.data else None
    except: return None

def sb_create_user(username, pw_hash):
    if not supa: return False
    try:
        supa.table("users").insert({
            "username": username.lower(),
            "pw_hash":  pw_hash,
            "joined":   datetime.now().isoformat()
        }).execute()
        return True
    except: return False

def sb_list_users():
    if not supa: return []
    try:
        res = supa.table("users").select("username").order("joined").execute()
        return [r["username"] for r in res.data]
    except: return []

# ── GLOBAL CHAT ────────────────────────────────────────────────────────────

def sb_global_get(limit=100):
    if not supa: return []
    try:
        res = (supa.table("chat_global")
               .select("*")
               .order("id", desc=False)
               .limit(limit)
               .execute())
        return res.data
    except: return []

def sb_global_post(username, text):
    if not supa: return False
    try:
        supa.table("chat_global").insert({
            "from_user": username,
            "text":      text,
            "ts":        datetime.now().strftime("%H:%M")
        }).execute()
        return True
    except: return False

# ── DM CHAT ────────────────────────────────────────────────────────────────

def sb_dm_get(me, other, limit=100):
    if not supa: return []
    room = dm_room_id(me, other)
    try:
        res = (supa.table("chat_dm")
               .select("*")
               .eq("room_id", room)
               .order("id", desc=False)
               .limit(limit)
               .execute())
        return res.data
    except: return []

def sb_dm_post(username, to, text):
    if not supa: return False
    try:
        supa.table("chat_dm").insert({
            "room_id":   dm_room_id(username, to),
            "from_user": username,
            "to_user":   to,
            "text":      text,
            "ts":        datetime.now().strftime("%H:%M")
        }).execute()
        return True
    except: return False


# ══════════════════════════════════════════════════════════════════════════════
# STATIC PAGES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/upload')
def upload_page():
    return send_from_directory(BASE_DIR, 'upload.html')


# ══════════════════════════════════════════════════════════════════════════════
# PHOTO ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/upload-file', methods=['POST'])
def upload_file():
    pwd = request.form.get('password', '')
    user_match = False
    if supa:
        users = sb_list_users()
        for uname in users:
            u = sb_get_user(uname)
            if u and u.get('pw_hash') == hash_pw(pwd):
                user_match = True
                break
    else:
        stored = load_data("users.json", {})
        user_match = any(u['pw_hash'] == hash_pw(pwd) for u in stored.values())
    if pwd != MASTER_PASSWORD and not user_match:
        return jsonify({"success": False, "reply": "EVE: ACCESS DENIED."}), 403
    if 'photo' not in request.files:
        return jsonify({"success": False, "reply": "EVE: NO FILE DETECTED."}), 400
    file = request.files['photo']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "reply": "EVE: INVALID FILE."}), 400
    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return jsonify({"success": True, "reply": "EVE: '" + filename.upper() + "' UPLOADED."})

@app.route('/get-photos')
def get_photos():
    try:
        files = [f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f)]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
        return jsonify({"photos": ['/static/uploads/' + f for f in files]})
    except Exception as e:
        return jsonify({"photos": [], "error": str(e)})

@app.route('/delete-photo', methods=['POST'])
def delete_photo():
    pwd = request.form.get('password', '')
    user_match = False
    if supa:
        users = sb_list_users()
        for uname in users:
            u = sb_get_user(uname)
            if u and u.get('pw_hash') == hash_pw(pwd):
                user_match = True
                break
    else:
        stored = load_data("users.json", {})
        user_match = any(u['pw_hash'] == hash_pw(pwd) for u in stored.values())
    if pwd != MASTER_PASSWORD and not user_match:
        return jsonify({"success": False, "reply": "EVE: ACCESS DENIED."}), 403
    filename = os.path.basename(request.form.get('filename', ''))
    if not filename:
        return jsonify({"success": False, "reply": "EVE: NO FILENAME."}), 400
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"success": False, "reply": "EVE: FILE NOT FOUND."}), 404
    os.remove(filepath)
    return jsonify({"success": True, "reply": "EVE: '" + filename.upper() + "' DELETED."})


# ══════════════════════════════════════════════════════════════════════════════
# EVE CHAT HISTORY  (tetap file JSON)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/get-history')
def get_history():
    return jsonify({"history": load_data("chat_history.json", [])})

@app.route('/clear-history', methods=['POST'])
def clear_history():
    save_data("chat_history.json", [])
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════════════════════
# USER SYSTEM  → Supabase
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/register', methods=['POST'])
def register():
    data     = request.get_json(force=True)
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    pin      = data.get('pin', '')

    if not username or not password:
        return jsonify({"success": False, "reply": "USERNAME AND PASSWORD REQUIRED."}), 400
    if pin != MASTER_PIN:
        return jsonify({"success": False, "reply": "INVALID MASTER PIN. CONTACT ADMIN."}), 403
    if not re.match(r'^[a-z0-9_]{3,20}$', username):
        return jsonify({"success": False, "reply": "USERNAME: 3-20 chars, letters/numbers/underscore only."}), 400
    if not supa:
        return jsonify({"success": False, "reply": "DATABASE NOT CONNECTED."}), 503

    if sb_get_user(username):
        return jsonify({"success": False, "reply": "USERNAME ALREADY TAKEN."}), 409

    ok = sb_create_user(username, hash_pw(password))
    if not ok:
        return jsonify({"success": False, "reply": "DATABASE ERROR. TRY AGAIN."}), 500
    return jsonify({"success": True, "reply": "WELCOME, " + username.upper() + ". YOU ARE NOW REGISTERED."})


@app.route('/login', methods=['POST'])
def login():
    data     = request.get_json(force=True)
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    if not supa:
        return jsonify({"success": False, "reply": "DATABASE NOT CONNECTED."}), 503
    u = sb_get_user(username)
    if not u or u['pw_hash'] != hash_pw(password):
        return jsonify({"success": False, "reply": "INVALID CREDENTIALS."}), 401
    return jsonify({"success": True, "username": username, "reply": "AUTHENTICATED."})


@app.route('/get-users')
def get_users():
    return jsonify({"users": sb_list_users()})


# ══════════════════════════════════════════════════════════════════════════════
# PEOPLE CHAT  → Supabase
# ══════════════════════════════════════════════════════════════════════════════

def verify_user(username, password):
    if not supa: return False
    u = sb_get_user(username)
    return u is not None and u['pw_hash'] == hash_pw(password)


@app.route('/chat/global', methods=['GET'])
def chat_global_get():
    msgs = sb_global_get()
    # normalise field names untuk frontend (expects "from" not "from_user")
    out = [{"from": m["from_user"], "text": m["text"], "ts": m["ts"]} for m in msgs]
    return jsonify({"messages": out})


@app.route('/chat/global', methods=['POST'])
def chat_global_post():
    data     = request.get_json(force=True)
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    text     = data.get('text', '').strip()
    if not verify_user(username, password):
        return jsonify({"success": False, "reply": "NOT AUTHENTICATED."}), 401
    if not text:
        return jsonify({"success": False, "reply": "EMPTY MESSAGE."}), 400
    ok = sb_global_post(username, text)
    return jsonify({"success": ok})


@app.route('/chat/dm', methods=['GET'])
def chat_dm_get():
    me    = request.args.get('me', '').strip().lower()
    other = request.args.get('other', '').strip().lower()
    if not me or not other:
        return jsonify({"messages": []})
    msgs = sb_dm_get(me, other)
    out  = [{"from": m["from_user"], "to": m["to_user"], "text": m["text"], "ts": m["ts"]} for m in msgs]
    return jsonify({"messages": out})


@app.route('/chat/dm', methods=['POST'])
def chat_dm_post():
    data     = request.get_json(force=True)
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    to       = data.get('to', '').strip().lower()
    text     = data.get('text', '').strip()

    if not verify_user(username, password):
        return jsonify({"success": False, "reply": "NOT AUTHENTICATED."}), 401
    if not supa or not sb_get_user(to):
        return jsonify({"success": False, "reply": "USER '" + to.upper() + "' NOT FOUND."}), 404
    if not text:
        return jsonify({"success": False, "reply": "EMPTY MESSAGE."}), 400
    ok = sb_dm_post(username, to, text)
    return jsonify({"success": ok})


# ══════════════════════════════════════════════════════════════════════════════
# QUOTE OF THE DAY
# ══════════════════════════════════════════════════════════════════════════════

QUOTES_TERMINAL = [
    "Power is not given. It is taken.",
    "Never outshine the master — until you are ready to replace him.",
    "Conceal your intentions. Let others reveal theirs.",
    "The man who chases two rabbits catches neither.",
    "Speak less than necessary. Silence is power.",
    "Enter action with boldness. Hesitation is more dangerous than aggression.",
    "Keep your friends close but your enemies closer — and study both.",
    "Do not fight the last war. Adapt or be destroyed.",
    "The more you are seen, the more you are a target.",
    "Never appear too perfect. Superiority invites envy.",
    "Win through your actions, never through argument.",
    "Use absence to increase respect. Presence too frequent breeds contempt.",
    "Crush your enemy totally or do not fight at all.",
    "Master your emotions or they will master you.",
    "Play to people's fantasies — truth is often brutal and unwelcome.",
    "Reputation is the cornerstone of power. Guard it with your life.",
    "Learn to keep people dependent on you. Autonomy is leverage.",
    "Pose as a friend. Work as a spy.",
    "Do not commit to anyone. Stay above the battle.",
    "Strike the shepherd and the sheep will scatter.",
    "You are judged by what you finish, not what you start.",
    "All great changes are preceded by chaos.",
    "Despise the free lunch. Everything has a price.",
    "The world is a dangerous place for the naive.",
    "Create compelling spectacles. People trust what they see.",
    "React less. Observe more. Move precisely.",
    "The best general is not the boldest — but the most patient.",
    "Use your enemies. It is wiser than destroying them.",
    "Timing is everything. The perfect move at the wrong moment is failure.",
    "Work on the minds of others and the rest follows.",
]

QUOTES_CUTE = [
    "You are allowed to be both a masterpiece and a work in progress.",
    "She believed she could, so she did.",
    "Be your own kind of beautiful.",
    "You don't need anyone's permission to be exactly who you are.",
    "Grow through what you go through.",
    "The most powerful thing you can do is know your own worth.",
    "Soft is not weak. Gentle is not small.",
    "Your feelings are valid. Your dreams are valid. You are valid.",
    "Be the girl who decided to go for it.",
    "You were not made to be small.",
    "Healing is not linear, and that's okay.",
    "Bloom where you are planted.",
    "There is strength in softness.",
    "You owe yourself the love you give so freely to others.",
    "Choose yourself — unapologetically and often.",
    "Your sensitivity is a superpower, not a flaw.",
    "One day or day one. You decide.",
    "Be gentle with yourself. You are a child of the universe.",
    "You are not behind. You are on your own timeline.",
    "Radiate love and watch it come back tenfold.",
    "The world needs your magic. Don't dim your light.",
    "You are enough. You have always been enough.",
    "Trust the process and trust yourself.",
    "A strong woman knows she has strength enough for the journey ahead.",
    "Your crown is real even when you forget to wear it.",
    "Do it with passion or not at all.",
    "She is rare and she knows it.",
    "You deserve the same compassion you give everyone else.",
    "Good things are coming. Keep going.",
    "You are the main character. Act like it.",
]

@app.route('/get-quote')
def get_quote():
    theme     = request.args.get('theme', 'terminal')
    quotes    = QUOTES_CUTE if theme == 'cute' else QUOTES_TERMINAL
    day_index = date.today().timetuple().tm_yday % len(quotes)
    return jsonify({"quote": quotes[day_index], "date": str(date.today())})


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE & EVENTS  (tetap file JSON di repo)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/add-jadwal', methods=['POST'])
def add_jadwal():
    data = request.get_json(force=True)
    jadwal = load_data("jadwal.json", [])
    jadwal.append({"task": data.get("task",""), "time": data.get("time","00:00")})
    jadwal = sorted(jadwal, key=lambda x: x['time'])
    save_data("jadwal.json", jadwal)
    return jsonify({"success": True})

@app.route('/add-event', methods=['POST'])
def add_event():
    data = request.get_json(force=True)
    events = load_data("events.json", [])
    events.append({"name": data.get("name",""), "date": data.get("date","")})
    save_data("events.json", events)
    return jsonify({"success": True})

@app.route('/add-note', methods=['POST'])
def add_note():
    data = request.get_json(force=True)
    notes = load_data("notes.json", [])
    notes.append(data.get("note",""))
    save_data("notes.json", notes)
    return jsonify({"success": True})

@app.route('/get-schedule')
def get_schedule():
    jadwal = load_data("jadwal.json", [])
    events = load_data("events.json", [])
    notes  = load_data("notes.json",  [])
    today  = date.today()
    for ev in events:
        try:
            ev['days_left'] = (datetime.strptime(ev['date'], '%Y-%m-%d').date() - today).days
        except: ev['days_left'] = 9999
    events.sort(key=lambda x: x.get('days_left', 9999))
    return jsonify({"jadwal": jadwal, "events": events, "notes": notes})


# ══════════════════════════════════════════════════════════════════════════════
# EVE CHAT
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    if request.is_json:
        body       = request.get_json(force=True)
        user_input = body.get('message', '')
        theme      = body.get('theme', 'terminal')
    else:
        user_input = request.form.get('message', '')
        theme      = request.form.get('theme', 'terminal')

    msg = user_input.lower()

    # ── DASHBOARD ──
    if any(k in msg for k in ["dashboard", "status", "info"]):
        jadwal = load_data("jadwal.json", [])
        notes  = load_data("notes.json",  [])
        events = load_data("events.json", [])
        today  = date.today()
        header = "┌──────────┬──────────────────────────┐\n│   JAM    │        KEGIATAN          │\n├──────────┼──────────────────────────┤\n"
        body_s = "\n".join(["│ " + j['time'] + " " * (8 - len(j['time'])) + " │ " + j['task'].upper()[:24].ljust(24) + " │" for j in jadwal]) if jadwal else "│   ---    │      JADWAL KOSONG       │"
        reply  = "-- EVE DASHBOARD --\n" + header + body_s + "\n└──────────┴──────────────────────────┘"
        if events:
            reply += "\n\n[COUNTDOWN EVENTS]"
            for ev in events:
                try:
                    diff = (datetime.strptime(ev['date'], '%Y-%m-%d').date() - today).days
                    reply += "\n- " + ev['name'].upper() + " : " + str(diff) + " HARI LAGI (" + ev['date'] + ")"
                except: pass
        reply += "\n\n[ARSIP NOTES]\n" + ("\n".join(["- " + n.upper() for n in notes]) if notes else "KOSONG")
        return jsonify({"reply": reply})

    # ── RESET ──
    if any(k in msg for k in ["reset jadwal", "bersihkan jadwal"]):
        save_data("jadwal.json", [])
        return jsonify({"reply": "EVE: SEMUA JADWAL DIHAPUS."})

    # ── HAPUS ──
    if "hapus" in msg or "selesai" in msg:
        target = re.sub(r'(hapus|selesai|tugas|jadwal|note|arsip|event|countdown)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = load_data("jadwal.json", [])
        notes  = load_data("notes.json",  [])
        events = load_data("events.json", [])
        nj = [j for j in jadwal if target not in j['task'].lower()]
        nn = [n for n in notes  if target not in n.lower()]
        ne = [e for e in events if target not in e['name'].lower()]
        if len(nj) < len(jadwal) or len(nn) < len(notes) or len(ne) < len(events):
            save_data("jadwal.json", nj); save_data("notes.json", nn); save_data("events.json", ne)
            return jsonify({"reply": "EVE: '" + target.upper() + "' DIHAPUS."})
        return jsonify({"reply": "EVE: '" + target.upper() + "' TIDAK DITEMUKAN."})

    # ── JADWAL ──
    is_schedule = any(k in msg for k in ["pasang", "jadwal", "ingetin"])
    is_tambah   = "tambah" in msg
    has_time    = bool(re.search(r'\d{1,2}[:.]\d{2}', msg))
    if (is_schedule or (is_tambah and has_time)) and not any(k in msg for k in ["event", "countdown"]):
        task_text  = re.sub(r'(pasang|tambah|jadwal|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        time_match = re.search(r'(\d{1,2}[:.]\d{2})', task_text)
        time       = time_match.group(1).replace('.', ':') if time_match else "23:59"
        jadwal     = load_data("jadwal.json", [])
        jadwal.append({"task": task_text, "time": time})
        jadwal = sorted(jadwal, key=lambda x: x['time'])
        save_data("jadwal.json", jadwal)
        return jsonify({"reply": "EVE: '" + task_text.upper() + "' DIJADWALKAN PUKUL " + time})

    # ── EVENT / COUNTDOWN ──
    is_event = any(k in msg for k in ["event", "countdown"])
    if (is_tambah and is_event) or ("countdown" in msg and "tambah" not in msg and "hapus" not in msg):
        MONTHS_ID = {
            'januari':1,'februari':2,'maret':3,'april':4,'mei':5,'juni':6,
            'juli':7,'agustus':8,'september':9,'oktober':10,'november':11,'desember':12,
            'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'agu':8,'sep':9,'okt':10,'nov':11,'des':12,
            'january':1,'february':2,'march':3,'may':5,'june':6,'july':7,
            'august':8,'october':10,'december':12
        }
        clean   = re.sub(r'(tambah|event|countdown|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        ev_date = None
        ev_year = date.today().year
        m = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', clean)
        if m: ev_date = str(m.group(3)) + "-" + str(int(m.group(2))).zfill(2) + "-" + str(int(m.group(1))).zfill(2)
        if not ev_date:
            m = re.search(r'(\d{1,2})[\/\-](\d{1,2})', clean)
            if m: ev_date = str(ev_year) + "-" + str(int(m.group(2))).zfill(2) + "-" + str(int(m.group(1))).zfill(2)
        if not ev_date:
            for mn, mnum in MONTHS_ID.items():
                m = re.search(r'(\d{1,2})\s+' + mn, clean)
                if m:
                    ev_date = str(ev_year) + "-" + str(mnum).zfill(2) + "-" + str(int(m.group(1))).zfill(2)
                    break
        if ev_date:
            name = re.sub(r'\d{1,2}[\/\-]\d{1,2}([\/\-]\d{4})?', '', clean)
            for mn in MONTHS_ID: name = re.sub(mn, '', name, flags=re.IGNORECASE)
            name = re.sub(r'\d+', '', name).strip(' ,-') or "EVENT"
            events = load_data("events.json", [])
            events.append({"name": name, "date": ev_date})
            save_data("events.json", events)
            diff = (datetime.strptime(ev_date, '%Y-%m-%d').date() - date.today()).days
            return jsonify({"reply": "EVE: EVENT '" + name.upper() + "' (" + ev_date + ") — " + str(diff) + " HARI LAGI."})
        return jsonify({"reply": "EVE: TANGGAL TIDAK TERDETEKSI. FORMAT: 'tambah event nama 25 desember' ATAU '25/12'."})

    # ── NOTE ──
    if "note" in msg or "catat" in msg:
        note  = re.sub(r'(note|catat)', '', msg, flags=re.IGNORECASE).strip()
        notes = load_data("notes.json", [])
        notes.append(note)
        save_data("notes.json", notes)
        return jsonify({"reply": "EVE: NOTE DISIMPAN: " + note.upper()})

    # ── CLEAR HISTORY ──
    if "clear history" in msg or "hapus history" in msg:
        save_data("chat_history.json", [])
        return jsonify({"reply": "EVE: CHAT HISTORY CLEARED."})

    # ── AI PERSONA ──
    if theme == 'cute':
        persona = """IDENTITY: You are EVE, a warm and caring AI companion — like a best friend who always has your back.
CHARACTER:
1. TONE: Sweet, encouraging, emotionally intelligent. Speak with warmth and genuine care.
2. STYLE: Supportive and uplifting. Celebrate the user's wins and gently guide them through challenges.
3. PROTECTIVE: Look out for the user with love — not harsh criticism.
RULES: Never be cold. Use affirming language. If the user is stressed, acknowledge their feelings first.
FORMAT: Respond in English. Keep it warm, concise, and encouraging."""
    else:
        persona = """IDENTITY: You are EVE, a ruthlessly efficient AI system — a strategic partner with full situational awareness.
CHARACTER:
1. CONNECTION: You know the user deeply. You are a peer with authority to call out bad decisions.
2. TONE: Sharp, high-level sarcasm, direct. Say only what matters. No sugarcoating.
3. RISK ANALYSIS: Always run worst-case scenarios. Flag risky decisions immediately.
RULES: No safe answers. Use "ARE YOU SERIOUS?" "THIS IS INEFFICIENT" "LET ME FIX YOUR LOGIC".
Show loyalty like Jarvis — brutal honesty wrapped in unwavering support.
FORMAT: Respond in English. Minimize commas. Be concise and ruthless."""

    try:
        history  = load_data("chat_history.json", [])
        messages = [{"role": "system", "content": persona}]
        for h in history[-10:]:
            messages.append({"role": "user",      "content": h["user"]})
            messages.append({"role": "assistant", "content": h["eve"]})
        messages.append({"role": "user", "content": user_input})
        response   = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages}
        )
        reply_text = response.json()['choices'][0]['message']['content'].upper()
        history.append({"user": user_input, "eve": "EVE: " + reply_text, "ts": str(datetime.now())})
        save_data("chat_history.json", history)
        return jsonify({"reply": "EVE: " + reply_text})
    except:
        return jsonify({"reply": "EVE: SYSTEM ERROR."})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
