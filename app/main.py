import os
from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from flask_session import Session
from pymongo import MongoClient
import redis
from dotenv import load_dotenv
import requests
import secrets
from datetime import datetime
import google.generativeai as genai

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCL3H5NrFBA4hCMGtJb4tkGOUW8ePk97l4")
if not GEMINI_API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY not set")
genai.configure(api_key=GEMINI_API_KEY)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Session Configuration (Redis, but not required for guest)
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("Environment variable REDIS_URL not set")
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_REDIS"] = redis.from_url(redis_url)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "interview-session"
Session(app)

mongodb_url = os.getenv("MONGODB_URL")
if not mongodb_url:
    raise RuntimeError("Environment variable MONGODB_URL not set")
MONGODB_CLIENT = MongoClient(mongodb_url)
DATABASE = MONGODB_CLIENT["production"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/interview')
def interview():
    return render_template('interview.html')

@app.route('/api/v1/create-interview', methods=['POST'])
def create_interview():
    # Fetch form data from the request
    job_description = request.form.get('job_description')
    resume = request.files.get('resume')
    interview_type = request.form.get('interview_type')
    if interview_type not in ['technical', 'behavioral', 'common-questions']:
        return jsonify({'status': 'error', 'message': 'Invalid interview type, must be one of: technical, behavioral, common-questions'}), 400
    if not job_description or not resume:
        return jsonify({'status': 'error', 'message': 'Job description or resume not provided'}), 400
    # Fetch resume summary via LLM
    model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
    prompt = f"""
    Carefully review the attached resume file. Provide a thorough, structured, and objective detailed summary of the candidate’s background, including:
    - Contact information (if present)
    - Education history (degrees, institutions, graduation years)
    - Work experience (roles, companies, durations, responsibilities, achievements)
    - Technical and soft skills
    - Certifications, awards, or notable projects
    - Any other relevant sections (e.g., publications, languages, interests)
    Present the information in clear, well-organized paragraphs using plain text (no markdown or formatting). Do not omit any details found in the resume. Avoid speculation; only summarize what is explicitly present in the document.
    """
    resume_blob = {
        "mime_type": resume.content_type,
        "data": resume.read()
    }
    response = model.generate_content([prompt, resume_blob])
    resume_summary = response.text
    # Generate interview questions based on resume summary, job description, and interview_type
    if interview_type == 'technical':
        question_prompt = f"""
        Generate 10 technical interview questions for a candidate applying for the following job description:
        {job_description}
        Resume summary:
        {resume_summary}
        The questions should be technical, relevant to the candidate's background, experience, and the job description. The response should be in plain text format (no markdown or formatting). The questions should be clear and concise, and they should cover a range of technical topics related to the candidate's skills and experience. Avoid speculative or ambiguous questions and do not provide any additional information or context.
        Only output the questions, one per line, with no numbering or extra text.
        """
    elif interview_type == 'behavioral':
        question_prompt = f"""
        Generate 10 behavioral interview questions for a candidate applying for the following job description:
        {job_description}
        Resume summary:
        {resume_summary}
        The questions should be behavioral, relevant to the candidate's background, experience, and the job description. The response should be in plain text format (no markdown or formatting). The questions should be clear and concise, and they should cover a range of behavioral topics related to the candidate's experience. Avoid speculative or ambiguous questions and do not provide any additional information or context.
        Only output the questions, one per line, with no numbering or extra text.
        """
    else:
        question_prompt = f"""
        Generate 10 common/basic interview questions for a candidate applying for the following job description:
        {job_description}
        Resume summary:
        {resume_summary}
        The questions should be general, relevant to the candidate's background, experience, and the job description. The response should be in plain text format (no markdown or formatting). The questions should be clear and concise, and they should cover a range of topics related to the candidate's skills and experience. Avoid speculative or ambiguous questions and do not provide any additional information or context.
        Only output the questions, one per line, with no numbering or extra text.
        """
    question_response = model.generate_content([question_prompt])
    questions = question_response.text.split('\n')
    questions = [q for q in questions if q.strip()]

    # Creating a new interview
    interview_identifier = secrets.token_hex(16)
    DATABASE["INTERVIEWS"].insert_one(
        {
            "interview_identifier": interview_identifier,
            "user_id": "guest_user",
            "interview_type": interview_type,
            "job_description": job_description,
            "resume_summary": resume_summary,
            "created_at": datetime.now(),
            "is_active": True,
            "is_completed": False,
            "ai_report": "",
            "questions": questions,
        }
    )
    return redirect(url_for("interview_page", interview_identifier=interview_identifier))

@app.route('/interview/<interview_identifier>', methods=['GET'])
def interview_page(interview_identifier):
    interview = DATABASE["INTERVIEWS"].find_one({"interview_identifier": interview_identifier})
    if interview is None:
        return jsonify({'status': 'error', 'message': 'Interview not found'}), 404
    if interview["is_completed"]:
        return redirect(url_for("interview_results", interview_identifier=interview_identifier))
    return render_template('take-interview.html', interview=interview)

@app.route('/new-mock-interview', methods=['GET'])
def new_mock_interview():
    user_info = DATABASE["USERS"].find_one({"user_id": "guest_user"})
    if user_info is None:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    if not user_info.get("user_info", {}).get("resume_summary"):
        return jsonify({'status': 'error', 'message': 'Resume summary not found'}), 404
    model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
    prompt = f"""
    Generate 10 mock interview questions based on the following resume summary:
    {user_info['user_info']['resume_summary']}
    The questions should be relevant to the candidate's background and experience, and the response should be in plain text format (no markdown or formatting). The questions should be clear and concise, and they should cover a range of topics related to the candidate's skills and experience. Avoid speculative or ambiguous questions and do not provide any additional information or context.
    Always include these two generic questions as the first two and be sure to parraphrase them:
    1. Tell me a bit about yourself.
    2. Walk me through your resume.
    The remaining questions should be tailored to the candidate's resume, covering technical skills, work experience, education, achievements, and other relevant areas. Do not repeat questions. Only output the questions, one per line, with no numbering or extra text.
    """
    response = model.generate_content([prompt])
    questions = response.text.split('\n')
    questions = [q for q in questions if q.strip()]
    mock_interview_identifier = secrets.token_hex(16)
    DATABASE["INTERVIEWS"].insert_one(
        {
            "mock_interview_identifier": mock_interview_identifier,
            "user_id": "guest_user",
            "questions": questions,
            "created_at": datetime.now(),
            "is_active": True,
            "is_completed": False,
            "video_url": "",
            "ai_report": "",
        }
    )
    return render_template('begin_mock_interview.html', mock_interview_identifier=mock_interview_identifier)

@app.route('/mock-interview/<mock_interview_identifier>', methods=['GET'])
def mock_interview(mock_interview_identifier):
    mock_interview = DATABASE["INTERVIEWS"].find_one({"mock_interview_identifier": mock_interview_identifier})
    if mock_interview is None:
        return jsonify({'status': 'error', 'message': 'Mock interview not found'}), 404
    return render_template('mock_interview.html', mock_interview=mock_interview)

@app.route('/api/v1/parse-resume', methods=['POST'])
def parse_resume():
    if 'resume' not in request.files:
        return jsonify({'status': 'error', 'message': 'No resume file part in the request'}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    if file:
        try:
            file_content = file.read()
            mime_type = file.content_type
            if not mime_type:
                return jsonify({'status': 'error', 'message': 'Could not determine file MIME type'}), 400
            resume_blob = {
                "mime_type": mime_type,
                "data": file_content
            }
            model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            prompt = """
            Carefully review the attached resume file. Provide a thorough, structured, and objective summary of the candidate’s background, including:
            - Contact information (if present)
            - Education history (degrees, institutions, graduation years)
            - Work experience (roles, companies, durations, responsibilities, achievements)
            - Technical and soft skills
            - Certifications, awards, or notable projects
            - Any other relevant sections (e.g., publications, languages, interests)
            Present the information in clear, well-organized paragraphs using plain text (no markdown or formatting). Do not omit any details found in the resume. Avoid speculation; only summarize what is explicitly present in the document.
            """
            response = model.generate_content([prompt, resume_blob])
            markdown_description = response.text
            DATABASE["USERS"].update_one(
                {"user_id": "guest_user"},
                {
                    "$set": {
                        "user_info.resume_summary": markdown_description,
                        "account_info.last_login": datetime.now(),
                    }
                },
                upsert=True
            )
            return f'Hey Guest, your resume has been successfully processed. Now you can generate mock interview questions based on your resume summary. <a href="/new-mock-interview">Click here</a> to generate mock interview questions.'
        except Exception as e:
            app.logger.error(f"Error processing resume with Gemini: {e}")
            return jsonify({'status': 'error', 'message': f'Failed to process resume with AI model: {str(e)}'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file provided'}), 400

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/api/v1/history')
def api_history():
    # Show last 20 interviews for guest_user
    interviews = list(DATABASE["INTERVIEWS"].find({"user_id": "guest_user"}).sort("created_at", -1).limit(20))
    for i in interviews:
        i["created_at"] = i["created_at"].isoformat() if "created_at" in i else ''
        i["interview_identifier"] = i.get("interview_identifier", '')
        i["interview_type"] = i.get("interview_type", '')
        i["job_description"] = i.get("job_description", '')
    return jsonify(interviews)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
