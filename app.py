import os
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# Mengambil lokasi folder saat ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def home():
    # Mengirim file Index.html langsung dari folder root
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    # Kita tes dulu: kalau request diterima, kirim balik pesannya
    data = request.get_json(force=True)
    return jsonify({"reply": "Server menerima: " + str(data.get('message', ''))})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
