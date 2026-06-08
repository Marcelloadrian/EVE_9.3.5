import os
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    data = request.get_json(force=True)
    user_input = data.get('message', '')
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": user_input}]
            }
        )
        result = response.json()
        
        # LOGGING: Ini akan muncul di Dashboard Render (Log)
        print("RESPONS DARI GROQ:", result)
        
        if 'choices' in result:
            reply = result['choices'][0]['message']['content']
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": "AI Error: Respons tidak mengandung 'choices'. Cek Log Render."})
            
    except Exception as e:
        return jsonify({"reply": "AI Error: " + str(e)})
