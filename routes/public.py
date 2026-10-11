"""Publicly accessible website routes for SecureNEET."""

from flask import Blueprint, render_template, request
import db
from services.leaderboard_service import get_overall_leaderboard, get_state_toppers, get_gender_toppers

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """SecureNEET Landing Page."""
    # Fetch public statistics
    stats = {
        'total_exams': db.query_one("SELECT COUNT(*) AS c FROM examinations WHERE is_published = 1")['c'],
        'total_students': db.query_one("SELECT COUNT(*) AS c FROM users WHERE role = 'student' AND is_active = 1")['c'],
        'total_attempts': db.query_one("SELECT COUNT(*) AS c FROM examination_attempts WHERE status IN ('evaluated', 'submitted')")['c']
    }
    
    # Recent published examinations
    recent_exams = db.query_all(
        """SELECT id, title, description, code, duration_minutes, total_marks,
                  positive_marks, negative_marks, start_time, end_time
           FROM examinations
           WHERE is_published = 1
           ORDER BY id DESC LIMIT 3"""
    )
    
    # Top 3 overall toppers for hero showcase
    top_performers = get_overall_leaderboard(limit=3)
    
    return render_template('public/index.html', stats=stats, exams=recent_exams, toppers=top_performers)

@public_bp.route('/about')
def about():
    """About SecureNEET page explaining security architecture and examination integrity."""
    return render_template('public/about.html')

@public_bp.route('/exams')
def exams():
    """Public catalogue of published examinations."""
    published_exams = db.query_all(
        """SELECT e.*, 
                  (SELECT COUNT(*) FROM questions q WHERE q.examination_id = e.id) AS question_count,
                  (SELECT COUNT(*) FROM examination_attempts ea WHERE ea.examination_id = e.id AND ea.status IN ('evaluated', 'submitted')) AS attempts_count
           FROM examinations e
           WHERE e.is_published = 1
           ORDER BY e.id DESC"""
    )
    return render_template('public/exams.html', exams=published_exams)

@public_bp.route('/leaderboards')
def leaderboards():
    """Overall examination leaderboard page."""
    exam_id = request.args.get('exam_id', type=int)
    
    # Get all published examinations for filter dropdown
    exams_list = db.query_all("SELECT id, title, code FROM examinations WHERE is_published = 1 ORDER BY id DESC")
    
    # Fetch overall rankings
    rankings = get_overall_leaderboard(exam_id=exam_id, limit=100)
    
    selected_exam = None
    if exam_id:
        selected_exam = db.query_one("SELECT id, title, total_marks FROM examinations WHERE id = %s", (exam_id,))

    return render_template('public/leaderboards.html',
                           rankings=rankings,
                           exams=exams_list,
                           selected_exam_id=exam_id,
                           selected_exam=selected_exam)

@public_bp.route('/leaderboards/state')
def state_toppers():
    """State Topper leaderboard."""
    exam_id = request.args.get('exam_id', type=int)
    selected_state = request.args.get('state', '').strip()
    
    exams_list = db.query_all("SELECT id, title, code FROM examinations WHERE is_published = 1 ORDER BY id DESC")
    
    data = get_state_toppers(exam_id=exam_id, selected_state=selected_state)
    
    selected_exam = None
    if exam_id:
        selected_exam = db.query_one("SELECT id, title, total_marks FROM examinations WHERE id = %s", (exam_id,))

    return render_template('public/state_toppers.html',
                           state_toppers=data['state_toppers'],
                           selected_leaderboard=data['selected_leaderboard'],
                           available_states=data['available_states'],
                           selected_state=selected_state,
                           exams=exams_list,
                           selected_exam_id=exam_id,
                           selected_exam=selected_exam)

@public_bp.route('/leaderboards/gender')
def gender_toppers():
    """Gender Topper leaderboard."""
    exam_id = request.args.get('exam_id', type=int)
    selected_gender = request.args.get('gender', '').strip()
    
    exams_list = db.query_all("SELECT id, title, code FROM examinations WHERE is_published = 1 ORDER BY id DESC")
    
    data = get_gender_toppers(exam_id=exam_id, selected_gender=selected_gender)
    
    selected_exam = None
    if exam_id:
        selected_exam = db.query_one("SELECT id, title, total_marks FROM examinations WHERE id = %s", (exam_id,))

    return render_template('public/gender_toppers.html',
                           gender_toppers=data['gender_toppers'],
                           selected_leaderboard=data['selected_leaderboard'],
                           available_genders=data['available_genders'],
                           selected_gender=selected_gender,
                           exams=exams_list,
                           selected_exam_id=exam_id,
                           selected_exam=selected_exam)

@public_bp.route('/privacy')
def privacy():
    """Privacy Policy page."""
    return render_template('public/privacy.html')

@public_bp.route('/terms')
def terms():
    """Terms and Conditions page."""
    return render_template('public/terms.html')
