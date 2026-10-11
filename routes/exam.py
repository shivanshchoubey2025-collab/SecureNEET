"""Examination environment routes and real-time APIs."""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
import db
from auth import login_required, role_required, get_current_user
from services.exam_service import (
    get_exam_by_id, get_exam_questions, get_or_create_attempt,
    get_student_answers, save_answer, evaluate_attempt
)
from config import Config

exam_bp = Blueprint('exam', __name__)

@exam_bp.route('/<int:exam_id>/instructions')
@login_required
@role_required('student')
def instructions(exam_id):
    """Pre-examination instructions and rules screen."""
    exam = get_exam_by_id(exam_id)
    if not exam or not exam.get('is_published'):
        flash("Examination is not available.", "danger")
        return redirect(url_for('student.dashboard'))
        
    student = get_current_user()
    
    # Check if student already attempted or has active attempt
    attempt = db.query_one(
        "SELECT * FROM examination_attempts WHERE examination_id = %s AND student_id = %s ORDER BY id DESC LIMIT 1",
        (exam_id, student['id'])
    )
    if attempt:
        if attempt['status'] == 'in_progress':
            return redirect(url_for('exam.portal', attempt_id=attempt['id']))
        else:
            flash("You have already submitted this examination.", "info")
            return redirect(url_for('student.result_detail', attempt_id=attempt['id']))
            
    q_count = db.query_one("SELECT COUNT(*) AS c FROM questions WHERE examination_id = %s", (exam_id,))['c']
    return render_template('exam/instructions.html', exam=exam, question_count=q_count)

@exam_bp.route('/<int:exam_id>/start', methods=['POST'])
@login_required
@role_required('student')
def start_exam(exam_id):
    """Start or resume examination attempt."""
    student = get_current_user()
    attempt, msg = get_or_create_attempt(student['id'], exam_id)
    
    if not attempt:
        flash(f"Cannot start examination: {msg}", "danger")
        return redirect(url_for('student.dashboard'))
        
    if msg == "already_submitted":
        flash("You have already submitted this examination.", "info")
        return redirect(url_for('student.result_detail', attempt_id=attempt['id']))
        
    if msg == "expired":
        flash("Your examination session has expired and was automatically submitted.", "warning")
        return redirect(url_for('student.result_detail', attempt_id=attempt['id']))
        
    return redirect(url_for('exam.portal', attempt_id=attempt['id']))

@exam_bp.route('/attempt/<int:attempt_id>')
@login_required
@role_required('student')
def portal(attempt_id):
    """Live examination interface with Question Palette, Subject Tabs, and Timer."""
    student = get_current_user()
    attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    
    if not attempt or attempt['student_id'] != student['id']:
        abort(403)
        
    if attempt['status'] != 'in_progress':
        flash("This examination attempt has already been finalized.", "info")
        return redirect(url_for('student.result_detail', attempt_id=attempt_id))

    # Calculate remaining time from server clock
    deadline = attempt['deadline_time']
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    
    remaining_seconds = int((deadline - datetime.now()).total_seconds())
    if remaining_seconds <= -Config.EXAM_GRACE_PERIOD_SECONDS:
        evaluate_attempt(attempt_id, status="expired")
        flash("Examination time elapsed. Your answers have been submitted automatically.", "warning")
        return redirect(url_for('student.result_detail', attempt_id=attempt_id))

    remaining_seconds = max(0, remaining_seconds)
    exam = get_exam_by_id(attempt['examination_id'])
    questions = get_exam_questions(attempt['examination_id'], include_correct=False)
    saved_answers = get_student_answers(attempt_id)

    # Group questions by subject
    subjects = ["Physics", "Chemistry", "Botany", "Zoology"]
    by_subject = {s: [] for s in subjects}
    for q in questions:
        s = q.get('subject', 'Physics')
        if s not in by_subject:
            by_subject[s] = []
        by_subject[s].append(q)

    return render_template('exam/portal.html',
                           attempt=attempt,
                           exam=exam,
                           questions=questions,
                           by_subject=by_subject,
                           saved_answers=saved_answers,
                           remaining_seconds=remaining_seconds)

@exam_bp.route('/api/attempt/<int:attempt_id>/save-answer', methods=['POST'])
@login_required
@role_required('student')
def api_save_answer(attempt_id):
    """Asynchronous autosave endpoint."""
    student = get_current_user()
    data = request.get_json(silent=True) or request.form
    
    question_id = data.get('question_id')
    selected_option = data.get('selected_option') # 'A', 'B', 'C', 'D' or None/''
    is_marked = bool(data.get('is_marked_for_review', False))
    
    if not question_id:
        return jsonify({'success': False, 'error': 'Question ID missing.'}), 400
        
    if selected_option == '':
        selected_option = None

    success, msg = save_answer(attempt_id, student['id'], int(question_id), selected_option, is_marked)
    if not success:
        return jsonify({'success': False, 'error': msg}), 400
        
    return jsonify({'success': True, 'message': msg})

@exam_bp.route('/api/attempt/<int:attempt_id>/time')
@login_required
@role_required('student')
def api_remaining_time(attempt_id):
    """Retrieve trusted server-side remaining seconds."""
    student = get_current_user()
    attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    
    if not attempt or attempt['student_id'] != student['id']:
        return jsonify({'error': 'Unauthorized'}), 403
        
    if attempt['status'] != 'in_progress':
        return jsonify({'remaining_seconds': 0, 'status': attempt['status']})

    deadline = attempt['deadline_time']
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    remaining_seconds = int((deadline - datetime.now()).total_seconds())

    if remaining_seconds <= -Config.EXAM_GRACE_PERIOD_SECONDS:
        evaluate_attempt(attempt_id, status="expired")
        return jsonify({'remaining_seconds': 0, 'status': 'expired'})

    return jsonify({'remaining_seconds': max(0, remaining_seconds), 'status': 'in_progress'})

@exam_bp.route('/attempt/<int:attempt_id>/submit', methods=['POST'])
@login_required
@role_required('student')
def submit_exam(attempt_id):
    """Final examination submission."""
    student = get_current_user()
    attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    
    if not attempt or attempt['student_id'] != student['id']:
        abort(403)
        
    if attempt['status'] == 'in_progress':
        evaluate_attempt(attempt_id, status="submitted")
        flash("Examination submitted successfully! Here is your scorecard.", "success")
    else:
        flash("Attempt already finalized.", "info")
        
    return redirect(url_for('student.result_detail', attempt_id=attempt_id))
