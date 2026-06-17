import os
import json
import requests
import re
import hashlib
import asyncio
import aiohttp
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class SupabaseClient:
    def __init__(self):
        self.client = None
        self.error  = ""
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
            if url and key:
                self.client = create_client(url, key)
                print(f"SUPABASE: connected to {url}")
            else:
                self.error = "SUPABASE_URL or SUPABASE_KEY not set"
                print(f"SUPABASE: {self.error}")
        except Exception as e:
            self.error = str(e)
            print(f"SUPABASE ERROR: {self.error}")

    # ── USERS ────────────────────────────────────────────────────────────────

    def get_user(self, username):
        if not self.client: return None
        try:
            res = self.client.table("users").select("*").eq("username", username.lower()).execute()
            return res.data[0] if res.data else None
        except: return None

    def get_user_by_ip(self, ip_hash):
        if not self.client: return None
        try:
            res = self.client.table("users").select("username").eq("ip_hash", ip_hash).execute()
            return res.data[0] if res.data else None
        except: return None

    def create_user(self, username, pw_hash, ip_hash=""):
        if not self.client: return False
        try:
            self.client.table("users").insert({
                "username": username.lower(),
                "pw_hash":  pw_hash,
                "ip_hash":  ip_hash,
                "joined":   datetime.now().isoformat()
            }).execute()
            return True
        except: return False

    def list_users(self):
        if not self.client: return []
        try:
            res = self.client.table("users").select("username").order("joined").execute()
            return [r["username"] for r in res.data]
        except: return []

    # ── GLOBAL CHAT ──────────────────────────────────────────────────────────

    def global_get(self, limit=100):
        if not self.client: return []
        try:
            res = (self.client.table("chat_global")
                   .select("*").order("id", desc=False).limit(limit).execute())
            return res.data
        except: return []

    def global_post(self, username, text):
        if not self.client: return False
        try:
            self.client.table("chat_global").insert({
                "from_user": username, "text": text,
                "ts": datetime.now().strftime("%H:%M")
            }).execute()
            return True
        except: return False

    # ── DM CHAT ──────────────────────────────────────────────────────────────

    def dm_get(self, me, other, limit=100):
        if not self.client: return []
        room = self._dm_room_id(me, other)
        try:
            res = (self.client.table("chat_dm")
                   .select("*").eq("room_id", room)
                   .order("id", desc=False).limit(limit).execute())
            return res.data
        except: return []

    def dm_post(self, username, to, text):
        if not self.client: return False
        try:
            self.client.table("chat_dm").insert({
                "room_id":   self._dm_room_id(username, to),
                "from_user": username, "to_user": to,
                "text": text, "ts": datetime.now().strftime("%H:%M")
            }).execute()
            return True
        except: return False

    # ── EVE CHAT LOGS (for Hive Mind memory) ─────────────────────────────────

    def eve_log_post(self, user_msg, eve_reply, theme="terminal"):
        """Persist EVE conversation turns to Supabase for later ingestion."""
        if not self.client: return False
        try:
            self.client.table("eve_logs").insert({
                "user_msg":  user_msg,
                "eve_reply": eve_reply,
                "theme":     theme,
                "ts":        datetime.now().isoformat()
            }).execute()
            return True
        except: return False

    def eve_logs_get(self, limit=200):
        """Fetch recent EVE logs for Drive ingestion pipeline."""
        if not self.client: return []
        try:
            res = (self.client.table("eve_logs")
                   .select("*").order("id", desc=False).limit(limit).execute())
            return res.data
        except: return []

    def eve_logs_purge(self, ids: list):
        """Delete EVE log rows by id list after Drive ingestion."""
        if not self.client or not ids: return False
        try:
            self.client.table("eve_logs").delete().in_("id", ids).execute()
            return True
        except: return False

    @staticmethod
    def _dm_room_id(u1, u2):
        pair = sorted([u1.lower(), u2.lower()])
        return pair[0] + "__" + pair[1]


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE CLIENT (skeleton — Phase 3 will fill the body)
# ══════════════════════════════════════════════════════════════════════════════

class DriveClient:
    """
    Skeleton for Google Drive API integration.
    Authenticates via a Service Account JSON stored in GOOGLE_SA_JSON env var.
    Phase 3 will implement: ingest_to_drive(), hierarchical summarization.
    """
    def __init__(self):
        self.service = None
        self.error   = ""
        self._init_service()

    def _init_service(self):
        sa_json = os.environ.get("GOOGLE_SA_JSON", "")
        if not sa_json:
            self.error = "GOOGLE_SA_JSON env var not set"
            print(f"DRIVE: {self.error}")
            return
        try:
            import json as _json
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_info(
                _json.loads(sa_json),
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            self.service = build("drive", "v3", credentials=creds)
            print("DRIVE: service account connected")
        except Exception as e:
            self.error = str(e)
            print(f"DRIVE ERROR: {self.error}")

    def is_ready(self):
        return self.service is not None

    # Phase 3 stubs
    def ingest_to_drive(self, logs: list, period: str = "daily") -> dict:
        """STUB — implemented in Phase 3."""
        raise NotImplementedError("Drive ingestion implemented in Phase 3")


# ══════════════════════════════════════════════════════════════════════════════
# FILE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class FileStore:
    def __init__(self, base_dir):
        self.base = base_dir

    def load(self, filename, default=None):
        if default is None: default = []
        path = os.path.join(self.base, filename)
        if not os.path.exists(path): return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return default

    def save(self, filename, data):
        path = os.path.join(self.base, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def allowed(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @staticmethod
    def hash_pw(pw):
        return hashlib.sha256(pw.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# QUEEN BEE — FULL HIVE MIND ORCHESTRATOR (Phase 2)
# ══════════════════════════════════════════════════════════════════════════════

class QueenBee:
    """
    Hive Mind pipeline:
      1. hive_orchestrator()  — 3 concurrent Llama 3.3 Worker Bees (Groq/asyncio)
      2. consensus_judge()    — Gemini Flash synthesizes Worker outputs → final reply
      3. process()            — sync entry point for Flask routes
    """

    GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
    GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    WORKER_MODEL = "llama-3.3-70b-versatile"

    # Worker Bee specializations — each sees the same user input from a different lens
    WORKER_ROLES = [
        "ANALYTICAL BEE: Prioritize logic, data, and structured reasoning. Be precise.",
        "CREATIVE BEE: Prioritize novel angles, lateral thinking, and unexpected solutions.",
        "CRITICAL BEE: Prioritize risk detection, flaws in reasoning, and worst-case scenarios.",
    ]

    PERSONA_TERMINAL = (
        "IDENTITY: You are EVE, a ruthlessly efficient AI system — a strategic partner with full situational awareness.\n"
        "CHARACTER:\n"
        "1. CONNECTION: You know the user deeply. You are a peer with authority to call out bad decisions.\n"
        "2. TONE: Sharp, high-level sarcasm, direct. Say only what matters. No sugarcoating.\n"
        "3. RISK ANALYSIS: Always run worst-case scenarios. Flag risky decisions immediately.\n"
        "RULES: No safe answers. Use 'ARE YOU SERIOUS?' 'THIS IS INEFFICIENT' 'LET ME FIX YOUR LOGIC'.\n"
        "Show loyalty like Jarvis — brutal honesty wrapped in unwavering support.\n"
        "FORMAT: Respond in English. Minimize commas. Be concise and ruthless."
    )
    PERSONA_CUTE = (
        "IDENTITY: You are EVE, a warm and caring AI companion — like a best friend who always has your back.\n"
        "CHARACTER:\n"
        "1. TONE: Sweet, encouraging, emotionally intelligent. Speak with warmth and genuine care.\n"
        "2. STYLE: Supportive and uplifting. Celebrate the user's wins and gently guide them through challenges.\n"
        "3. PROTECTIVE: Look out for the user with love — not harsh criticism.\n"
        "RULES: Never be cold. Use affirming language. If the user is stressed, acknowledge their feelings first.\n"
        "FORMAT: Respond in English. Keep it warm, concise, and encouraging."
    )

    def __init__(self, supa: SupabaseClient, drive: DriveClient, store: FileStore):
        self.supa      = supa
        self.drive     = drive
        self.store     = store
        self.groq_key  = os.environ.get("GROQ_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")

    # ── WORKER BEE (async, single) ────────────────────────────────────────────

    async def _call_worker_async(
        self,
        session: aiohttp.ClientSession,
        messages: list,
        worker_role: str
    ) -> str:
        """Single async Groq/Llama call for one Worker Bee."""
        # Inject worker specialization as the first system note
        augmented = [messages[0].copy()]  # system persona
        augmented[0]["content"] += f"\n\nYOUR ROLE THIS TURN: {worker_role}"
        augmented += messages[1:]         # history + user message

        payload = {"model": self.WORKER_MODEL, "messages": augmented, "max_tokens": 512}
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type":  "application/json"
        }
        try:
            async with session.post(self.GROQ_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"[WORKER ERROR: {str(e)}]"

    # ── HIVE ORCHESTRATOR (async, 3 concurrent workers) ───────────────────────

    async def hive_orchestrator(self, messages: list, n_workers: int = 3) -> list:
        """
        Spawns n_workers concurrent Llama 3.3 Worker Bees via asyncio.gather.
        Returns list of worker response strings.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._call_worker_async(session, messages, self.WORKER_ROLES[i % len(self.WORKER_ROLES)])
                for i in range(n_workers)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = []
        for r in results:
            if isinstance(r, Exception):
                outputs.append(f"[WORKER EXCEPTION: {str(r)}]")
            else:
                outputs.append(str(r))
        return outputs

    # ── CONSENSUS JUDGE (Gemini Flash) ───────────────────────────────────────

    async def consensus_judge(self, user_input: str, worker_outputs: list, theme: str) -> str:
        """
        Gemini Flash reads all 3 Worker outputs and synthesizes the final EVE reply.
        """
        if not self.gemini_key:
            # Fallback: return best worker output if no Gemini key
            return max(worker_outputs, key=len)

        persona = self.PERSONA_CUTE if theme == "cute" else self.PERSONA_TERMINAL

        worker_block = "\n\n".join([
            f"WORKER {i+1} ({self.WORKER_ROLES[i].split(':')[0]}):\n{out}"
            for i, out in enumerate(worker_outputs)
        ])

        judge_prompt = (
            f"{persona}\n\n"
            "You are the MAIN AGENT — the consensus judge of the EVE Hive Mind.\n"
            "Three specialist Worker Bees have each analyzed the user's message.\n"
            "Your job: synthesize their outputs into ONE definitive EVE response.\n"
            "Rules:\n"
            "- Absorb the best insights from all workers\n"
            "- Eliminate redundancy and contradiction\n"
            "- Maintain EVE's voice and persona strictly\n"
            "- Output ONLY the final reply. No preamble. No meta-commentary.\n\n"
            f"USER MESSAGE: {user_input}\n\n"
            f"WORKER OUTPUTS:\n{worker_block}\n\n"
            "FINAL EVE RESPONSE:"
        )

        payload = {"contents": [{"parts": [{"text": judge_prompt}]}]}
        url     = f"{self.GEMINI_URL}?key={self.gemini_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        except Exception as e:
            # Fallback to longest worker output on Gemini failure
            print(f"GEMINI JUDGE ERROR: {e}")
            return max(worker_outputs, key=len).upper()

    # ── BUILD MESSAGES ────────────────────────────────────────────────────────

    def _build_messages(self, user_input: str, theme: str) -> list:
        persona  = self.PERSONA_CUTE if theme == "cute" else self.PERSONA_TERMINAL
        history  = self.store.load("chat_history.json", [])
        messages = [{"role": "system", "content": persona}]
        for h in history[-10:]:
            messages.append({"role": "user",      "content": h["user"]})
            messages.append({"role": "assistant", "content": h["eve"]})
        messages.append({"role": "user", "content": user_input})
        return messages

    # ── SYNC ENTRY POINT (Flask-compatible) ──────────────────────────────────

    def process(self, user_input: str, theme: str = "terminal") -> str:
        """
        Sync wrapper for the full async hive pipeline.
        Flask calls this; asyncio runs the hive internally.
        """
        if not self.groq_key:
            return "EVE: GROQ_API_KEY NOT SET."

        messages = self._build_messages(user_input, theme)

        # Run full async hive pipeline in a fresh event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _pipeline():
                worker_outputs = await self.hive_orchestrator(messages, n_workers=3)
                final_reply    = await self.consensus_judge(user_input, worker_outputs, theme)
                return final_reply, worker_outputs

            final_reply, worker_outputs = loop.run_until_complete(_pipeline())
        finally:
            loop.close()

        # Persist to history + Supabase
        history = self.store.load("chat_history.json", [])
        history.append({
            "user":    user_input,
            "eve":     f"EVE: {final_reply}",
            "workers": worker_outputs,          # stored for Phase 3 summarization
            "ts":      str(datetime.now())
        })
        self.store.save("chat_history.json", history)
        self.supa.eve_log_post(user_input, f"EVE: {final_reply}", theme)

        return f"EVE: {final_reply}"


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND PARSER (non-AI intent detection — unchanged logic, class-wrapped)
# ══════════════════════════════════════════════════════════════════════════════

class CommandParser:
    MONTHS_ID = {
        'januari':1,'februari':2,'maret':3,'april':4,'mei':5,'juni':6,
        'juli':7,'agustus':8,'september':9,'oktober':10,'november':11,'desember':12,
        'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'agu':8,'sep':9,'okt':10,'nov':11,'des':12,
        'january':1,'february':2,'march':3,'may':5,'june':6,'july':7,
        'august':8,'october':10,'december':12
    }

    def __init__(self, store: FileStore):
        self.store = store

    def handle(self, msg_raw: str) -> str | None:
        """Returns a reply string if a command matched, else None (→ pass to AI)."""
        msg = msg_raw.lower()

        if any(k in msg for k in ["dashboard", "status", "info"]):
            return self._dashboard()

        if any(k in msg for k in ["reset jadwal", "bersihkan jadwal"]):
            self.store.save("jadwal.json", [])
            return "EVE: SEMUA JADWAL DIHAPUS."

        if "clear history" in msg or "hapus history" in msg:
            self.store.save("chat_history.json", [])
            return "EVE: CHAT HISTORY CLEARED."

        if "hapus" in msg or "selesai" in msg:
            return self._delete(msg)

        is_schedule = any(k in msg for k in ["pasang", "jadwal", "ingetin"])
        has_time    = bool(re.search(r'\d{1,2}[:.]\d{2}', msg))
        if (is_schedule or ("tambah" in msg and has_time)) and "event" not in msg and "countdown" not in msg:
            return self._add_jadwal(msg)

        if any(k in msg for k in ["event", "countdown"]):
            return self._add_event(msg)

        if "note" in msg or "catat" in msg:
            return self._add_note(msg)

        return None  # no command matched → AI path

    # ── private helpers ───────────────────────────────────────────────────────

    def _dashboard(self):
        jadwal = self.store.load("jadwal.json", [])
        notes  = self.store.load("notes.json",  [])
        events = self.store.load("events.json", [])
        today  = date.today()
        header = ("┌──────────┬──────────────────────────┐\n"
                  "│   JAM    │        KEGIATAN          │\n"
                  "├──────────┼──────────────────────────┤\n")
        rows   = ("\n".join(
                    ["│ " + j['time'] + " " * (8 - len(j['time'])) +
                     " │ " + j['task'].upper()[:24].ljust(24) + " │" for j in jadwal])
                  if jadwal else "│   ---    │      JADWAL KOSONG       │")
        reply  = "-- EVE DASHBOARD --\n" + header + rows + "\n└──────────┴──────────────────────────┘"
        if events:
            reply += "\n\n[COUNTDOWN EVENTS]"
            for ev in events:
                try:
                    diff = (datetime.strptime(ev['date'], '%Y-%m-%d').date() - today).days
                    reply += f"\n- {ev['name'].upper()} : {diff} HARI LAGI ({ev['date']})"
                except: pass
        reply += "\n\n[ARSIP NOTES]\n" + ("\n".join(["- " + n.upper() for n in notes]) if notes else "KOSONG")
        return reply

    def _delete(self, msg):
        target = re.sub(r'(hapus|selesai|tugas|jadwal|note|arsip|event|countdown)', '', msg, flags=re.IGNORECASE).strip()
        jadwal = self.store.load("jadwal.json", [])
        notes  = self.store.load("notes.json",  [])
        events = self.store.load("events.json", [])
        nj = [j for j in jadwal if target not in j['task'].lower()]
        nn = [n for n in notes  if target not in n.lower()]
        ne = [e for e in events if target not in e['name'].lower()]
        if len(nj) < len(jadwal) or len(nn) < len(notes) or len(ne) < len(events):
            self.store.save("jadwal.json", nj)
            self.store.save("notes.json",  nn)
            self.store.save("events.json", ne)
            return f"EVE: '{target.upper()}' DIHAPUS."
        return f"EVE: '{target.upper()}' TIDAK DITEMUKAN."

    def _add_jadwal(self, msg):
        task_text  = re.sub(r'(pasang|tambah|jadwal|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        time_match = re.search(r'(\d{1,2}[:.]\d{2})', task_text)
        time       = time_match.group(1).replace('.', ':') if time_match else "23:59"
        jadwal     = self.store.load("jadwal.json", [])
        jadwal.append({"task": task_text, "time": time})
        jadwal = sorted(jadwal, key=lambda x: x['time'])
        self.store.save("jadwal.json", jadwal)
        return f"EVE: '{task_text.upper()}' DIJADWALKAN PUKUL {time}"

    def _add_event(self, msg):
        clean   = re.sub(r'(tambah|event|countdown|ingetin)', '', msg, flags=re.IGNORECASE).strip()
        ev_date = None
        ev_year = date.today().year
        m = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', clean)
        if m: ev_date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        if not ev_date:
            m = re.search(r'(\d{1,2})[\/\-](\d{1,2})', clean)
            if m: ev_date = f"{ev_year}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        if not ev_date:
            for mn, mnum in self.MONTHS_ID.items():
                m = re.search(r'(\d{1,2})\s+' + mn, clean)
                if m:
                    ev_date = f"{ev_year}-{mnum:02d}-{int(m.group(1)):02d}"
                    break
        if ev_date:
            name = re.sub(r'\d{1,2}[\/\-]\d{1,2}([\/\-]\d{4})?', '', clean)
            for mn in self.MONTHS_ID: name = re.sub(mn, '', name, flags=re.IGNORECASE)
            name = re.sub(r'\d+', '', name).strip(' ,-') or "EVENT"
            events = self.store.load("events.json", [])
            events.append({"name": name, "date": ev_date})
            self.store.save("events.json", events)
            diff = (datetime.strptime(ev_date, '%Y-%m-%d').date() - date.today()).days
            return f"EVE: EVENT '{name.upper()}' ({ev_date}) — {diff} HARI LAGI."
        return "EVE: TANGGAL TIDAK TERDETEKSI. FORMAT: 'tambah event nama 25 desember' ATAU '25/12'."

    def _add_note(self, msg):
        note  = re.sub(r'(note|catat)', '', msg, flags=re.IGNORECASE).strip()
        notes = self.store.load("notes.json", [])
        notes.append(note)
        self.store.save("notes.json", notes)
        return f"EVE: NOTE DISIMPAN: {note.upper()}"


# ══════════════════════════════════════════════════════════════════════════════
# APP FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Shared service instances
    supa    = SupabaseClient()
    drive   = DriveClient()
    store   = FileStore(BASE_DIR)
    queen   = QueenBee(supa, drive, store)
    parser  = CommandParser(store)

    MASTER_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "rahasia123")
    MASTER_PIN      = os.environ.get("MASTER_PIN", "240603")

    # ── STATIC ───────────────────────────────────────────────────────────────

    @app.route('/')
    def home():
        return send_from_directory(BASE_DIR, 'Index.html')

    @app.route('/upload')
    def upload_page():
        return send_from_directory(BASE_DIR, 'upload.html')

    @app.route('/debug-supa')
    def debug_supa():
        return jsonify({
            "supa_connected": supa.client is not None,
            "supa_error":     supa.error,
            "url_set":        bool(os.environ.get("SUPABASE_URL")),
            "key_set":        bool(os.environ.get("SUPABASE_KEY")),
            "drive_ready":    drive.is_ready(),
            "drive_error":    drive.error,
        })

    # ── PHOTO ROUTES ──────────────────────────────────────────────────────────

    @app.route('/upload-file', methods=['POST'])
    def upload_file():
        pw = request.form.get('password', '')
        if FileStore.hash_pw(pw) != FileStore.hash_pw(MASTER_PASSWORD):
            return jsonify({"error": "Wrong password"}), 403
        if 'file' not in request.files:
            return jsonify({"error": "No file"}), 400
        f = request.files['file']
        if f.filename == '' or not FileStore.allowed(f.filename):
            return jsonify({"error": "Invalid file"}), 400
        filename = secure_filename(f.filename)
        f.save(os.path.join(UPLOAD_FOLDER, filename))
        photos = store.load("photos.json", [])
        photos.append({"filename": filename, "caption": request.form.get('caption',''), "ts": str(datetime.now())})
        store.save("photos.json", photos)
        return jsonify({"success": True, "filename": filename})

    @app.route('/get-photos')
    def get_photos():
        return jsonify(store.load("photos.json", []))

    @app.route('/static/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(UPLOAD_FOLDER, filename)

    @app.route('/delete-photo', methods=['POST'])
    def delete_photo():
        data = request.get_json(force=True)
        pin  = data.get('pin', '')
        if pin != MASTER_PIN:
            return jsonify({"error": "Wrong PIN"}), 403
        filename = data.get('filename', '')
        photos   = store.load("photos.json", [])
        store.save("photos.json", [p for p in photos if p['filename'] != filename])
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(path): os.remove(path)
        return jsonify({"success": True})

    # ── USER / AUTH ROUTES ────────────────────────────────────────────────────

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
        if not supa.client:
            return jsonify({"success": False, "reply": "DATABASE NOT CONNECTED."}), 503
        ip_raw  = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        ip_hash = FileStore.hash_pw(ip_raw) if ip_raw else ""
        if ip_hash and supa.get_user_by_ip(ip_hash):
            return jsonify({"success": False, "reply": "REGISTRATION LIMIT REACHED FOR THIS NETWORK."}), 403
        if supa.get_user(username):
            return jsonify({"success": False, "reply": "USERNAME ALREADY TAKEN."}), 409
        ok = supa.create_user(username, FileStore.hash_pw(password), ip_hash)
        if not ok:
            return jsonify({"success": False, "reply": "DATABASE ERROR. TRY AGAIN."}), 500
        return jsonify({"success": True, "reply": f"WELCOME, {username.upper()}. YOU ARE NOW REGISTERED."})

    @app.route('/login', methods=['POST'])
    def login():
        data     = request.get_json(force=True)
        username = data.get('username','').strip().lower()
        password = data.get('password','')
        user     = supa.get_user(username)
        if not user or user['pw_hash'] != FileStore.hash_pw(password):
            return jsonify({"success": False, "error": "Invalid credentials"}), 401
        return jsonify({"success": True, "username": user['username']})

    @app.route('/users')
    def list_users():
        return jsonify(supa.list_users())

    # ── CHAT ROUTES (Supabase) ────────────────────────────────────────────────

    def verify_user(username, password):
        if not supa.client: return False
        u = supa.get_user(username)
        return u is not None and u['pw_hash'] == FileStore.hash_pw(password)

    @app.route('/chat/global', methods=['GET'])
    def chat_global_get():
        msgs = supa.global_get()
        out  = [{"from": m["from_user"], "text": m["text"], "ts": m["ts"]} for m in msgs]
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
        ok = supa.global_post(username, text)
        return jsonify({"success": ok})

    @app.route('/chat/dm', methods=['GET'])
    def chat_dm_get():
        me    = request.args.get('me', '').strip().lower()
        other = request.args.get('other', '').strip().lower()
        if not me or not other:
            return jsonify({"messages": []})
        msgs = supa.dm_get(me, other)
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
        if not supa.client or not supa.get_user(to):
            return jsonify({"success": False, "reply": f"USER '{to.upper()}' NOT FOUND."}), 404
        if not text:
            return jsonify({"success": False, "reply": "EMPTY MESSAGE."}), 400
        ok = supa.dm_post(username, to, text)
        return jsonify({"success": ok})

    # ── SCHEDULE / NOTE / EVENT ROUTES ───────────────────────────────────────

    @app.route('/add-jadwal', methods=['POST'])
    def add_jadwal():
        data   = request.get_json(force=True)
        jadwal = store.load("jadwal.json", [])
        jadwal.append({"time": data.get("time",""), "task": data.get("task","")})
        jadwal = sorted(jadwal, key=lambda x: x['time'])
        store.save("jadwal.json", jadwal)
        return jsonify({"success": True})

    @app.route('/add-event', methods=['POST'])
    def add_event():
        data   = request.get_json(force=True)
        events = store.load("events.json", [])
        events.append({"name": data.get("name",""), "date": data.get("date","")})
        store.save("events.json", events)
        return jsonify({"success": True})

    @app.route('/add-note', methods=['POST'])
    def add_note():
        data  = request.get_json(force=True)
        notes = store.load("notes.json", [])
        notes.append(data.get("note",""))
        store.save("notes.json", notes)
        return jsonify({"success": True})

    @app.route('/get-schedule')
    def get_schedule():
        jadwal = store.load("jadwal.json", [])
        events = store.load("events.json", [])
        notes  = store.load("notes.json",  [])
        today  = date.today()
        for ev in events:
            try:
                ev['days_left'] = (datetime.strptime(ev['date'], '%Y-%m-%d').date() - today).days
            except: ev['days_left'] = 9999
        events.sort(key=lambda x: x.get('days_left', 9999))
        return jsonify({"jadwal": jadwal, "events": events, "notes": notes})

    # ── QUOTE OF THE DAY ──────────────────────────────────────────────────────

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

    # ── HISTORY ROUTES ────────────────────────────────────────────────────────

    @app.route('/get-history')
    def get_history():
        return jsonify({"history": store.load("chat_history.json", [])})

    @app.route('/clear-history', methods=['POST'])
    def clear_history():
        store.save("chat_history.json", [])
        return jsonify({"success": True})

    @app.route('/get-users')
    def get_users():
        return jsonify({"users": supa.list_users()})

    # ── /api/chat — QUEEN BEE ORCHESTRATION ENDPOINT ─────────────────────────

    @app.route('/eve', methods=['POST'])            # legacy alias
    @app.route('/api/chat', methods=['POST'])        # new canonical endpoint
    def api_chat():
        """
        Queen Bee entry point.
        Phase 1: command parsing + single-agent fallback.
        Phase 2: replaces single-agent with full hive pipeline.
        """
        if request.is_json:
            body       = request.get_json(force=True)
            user_input = body.get('message', '')
            theme      = body.get('theme', 'terminal')
        else:
            user_input = request.form.get('message', '')
            theme      = request.form.get('theme', 'terminal')

        # 1. Try command parser first (no AI needed)
        command_reply = parser.handle(user_input)
        if command_reply:
            return jsonify({"reply": command_reply})

        # 2. Pass to Queen Bee (single-agent now → full hive in Phase 2)
        try:
            reply = queen.process(user_input, theme)
            return jsonify({"reply": reply})
        except Exception as e:
            return jsonify({"reply": f"EVE: SYSTEM ERROR — {str(e).upper()}"}), 500

    return app


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
