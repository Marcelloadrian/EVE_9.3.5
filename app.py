import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder='.')

@app.route('/')
def home():
    return render_template('Index.html')

@app.route('/eve', methods=['POST'])
def eve_interface():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return jsonify({"reply": "Error: API Key belum di-set di Render"}), 500
        
    user_data = request.get_json(force=True)
    user_input = user_data.get('message', '')
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": user_input}]
            }
        )
        data = response.json()
        reply = data['choices'][0]['message']['content']
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Error: " + str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
