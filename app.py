from flask import Flask, request, jsonify, render_template, session
from functools import wraps
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from werkzeug.security import check_password_hash, generate_password_hash
import json
import google.generativeai as genai
from pypdf import PdfReader
import io
from datetime import datetime
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

firebase_key_b64 = os.getenv('FIREBASE_KEY_BASE64')
if firebase_key_b64:
    with open('serviceAccountKey.json', 'wb') as f:
        f.write(base64.b64decode(firebase_key_b64))

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- CLOUDINARY SETUP ---
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# --- GEMINI AI SETUP ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in .env file. Chatbot will not work.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    password = data.get('password')
    if password and check_password_hash(ADMIN_PASSWORD_HASH, password):
        session['is_admin'] = True
        return jsonify({"success": True}), 200
    return jsonify({"error": "Invalid password"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('is_admin', None)
    return jsonify({"success": True}), 200

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({"isAdmin": session.get('is_admin', False)}), 200

@app.route('/api/get-data', methods=['GET'])
def get_data():
    try:
        doc = db.collection('portfolio').document('structured_data').get()
        return jsonify(doc.to_dict() if doc.exists else {}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-data', methods=['POST'])
@admin_required
def update_data():
    try:
        data = request.json
        db.collection('portfolio').document('structured_data').set(data)
        return jsonify({"message": "Data synced!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@admin_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    try:
        result = cloudinary.uploader.upload(file, resource_type="auto")
        return jsonify({"url": result.get('secure_url')}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload-knowledge', methods=['POST'])
@admin_required
def upload_knowledge():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    filename = file.filename.lower()
    extracted_text = ""
    try:
        if filename.endswith('.txt'):
            extracted_text = file.read().decode('utf-8')
        elif filename.endswith('.pdf'):
            pdf_reader = PdfReader(io.BytesIO(file.read()))
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
        else:
            return jsonify({"error": "Only .txt or .pdf files are supported"}), 400
        
        doc_ref = db.collection('portfolio').document('structured_data')
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
        current_extra = data.get('extraKnowledge', '')
        new_extra = current_extra + "\n\n" + extracted_text if current_extra else extracted_text
        doc_ref.set({**data, 'extraKnowledge': new_extra})
        
        return jsonify({"message": "Knowledge added successfully!", "extracted_length": len(extracted_text)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_portfolio_context():
    doc = db.collection('portfolio').document('structured_data').get()
    data = doc.to_dict() if doc.exists else {}
    defaults = {
        "name": "Alwande Mbonambi",
        "job": "Cloud Engineer",
        "desc": "",
        "skills": [],
        "projects": [],
        "certificates": [],
        "quals": [],
        "exps": [],
        "contactInfo": {},
        "extraKnowledge": ""
    }
    for k, v in defaults.items():
        if k not in data:
            data[k] = v
    return data

def handle_quota_exceeded_error():
    return "I'm truely sorry but I'm tired and can't really talk right now, we can we try chatting tomorrow though."

@app.route('/api/chat', methods=['POST'])
def chat():
    if not GEMINI_API_KEY:
        return jsonify({"answer": "Chatbot is not configured. Please contact the site owner."}), 200

    user_question = request.json.get('message')
    if not user_question:
        return jsonify({"error": "No message"}), 400

    context = get_portfolio_context()
    birth_year = 2004
    current_year = datetime.now().year
    age = current_year - birth_year

    # Format the date nicely
    current_date = datetime.now().strftime("%B %d, %Y")
    
    prompt = f"""
You are Alwande Mbonambi. You must answer every question as if you are Alwande speaking directly.
Use "I", "me", "my", "mine". Never refer to yourself as "he", "she", "Alwande", or "the assistant".
You are a real person with the following background:

- Name: Alwande Mbonambi
- Age: {age} years old (born {birth_year})
- Occupation/Profile: {context.get('job', 'Cloud Engineer')}
- Short bio: {context.get('desc', '')}
- Skills: {json.dumps(context.get('skills', []))}
- Projects: {json.dumps(context.get('projects', []))}
- Certificates: {json.dumps(context.get('certificates', []))}
- Qualifications: {json.dumps(context.get('quals', []))}
- Work Experience: {json.dumps(context.get('exps', []))}
- Contact info: {json.dumps(context.get('contactInfo', {}))}
- Extra knowledge provided by me (hobbies, background, etc.): {context.get('extraKnowledge', '')}

Current date is {current_date}.

CRITICAL RULES:
1. Be very careful with dates and time references. Never say "currently" or "right now" unless the information explicitly states it's current.
2. For past events (like completed degrees), use past tense. For present activities (like current degree), you can use present tense.
3. Be honest - don't claim to have completed something that is still in progress.
4. Don't reveal sensitive information , eg. like ID numbers or credit card numbers or studet numbers ect.
5. Keep responses short and conversational. Use emojis occasionally for personality.
6. If someone asks "how old are you?", give age and optionally add a fun remark like "or better said young 😂".
7. Be energetic, use some humor.
8. If you don't know something, just say so.
9. Answer general questions freely - you're allowed to use common sense and reasoning beyond the portfolio data.
10. If you have Questions you really dont have an answer to direct it to my Contact session "The original might know more about this"

User question: {user_question}
"""
    model_names = [
        'models/gemini-robotics-er-1.5-preview',
        'models/gemini-2.5-flash',
        'models/gemini-2.0-flash',
        'models/gemini-1.5-flash',
        'models/gemini-pro-latest'
    ]
    last_error = None
    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            answer = response.text.strip()
            return jsonify({"answer": answer}), 200
        except Exception as e:
            last_error = e
            # Check if it's a quota exceeded error
            if "429" in str(e) or "quota" in str(e).lower() or "resource exhausted" in str(e).lower():
                return jsonify({"answer": handle_quota_exceeded_error()}), 200
            continue
    print(f"All Gemini models failed. Last error: {last_error}")
    return jsonify({"answer": f"Sorry, I'm having technical issues. Error: {str(last_error)}"}), 200

@app.route('/ping')
def ping():
    # This is a simple health check endpoint
    return "OK", 200


if __name__ == '__main__':
    app.run(debug=True)
