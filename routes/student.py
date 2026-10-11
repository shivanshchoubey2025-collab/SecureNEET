"""Student dashboard and personal performance routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
import db
from auth import login_required, role_required, get_current_user, INDIAN_STATES, GENDER_OPTIONS
from services.audit_service import log_action

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@login_required
@role_required('student')
def dashboard():
    """Personalized student portal."""
    student = get_current_user()
    student_id = student['id']

    # 1. Fetch ongoing attempt if any
    ongoing_attempt = db.query_one(
        """SELECT ea.*, e.title AS exam_title, e.code AS exam_code, e.duration_minutes
           FROM examination_attempts ea
           JOIN examinations e ON ea.examination_id = e.id
           WHERE ea.student_id = %s AND ea.status = 'in_progress'
           ORDER BY ea.id DESC LIMIT 1""",
        (student_id,)
    )

    # 2. Completed examinations & scores
    completed_attempts = db.query_all(
        """SELECT ea.*, e.title AS exam_title, e.code AS exam_code, e.total_marks
           FROM examination_attempts ea
           JOIN examinations e ON ea.examination_id = e.id
           WHERE ea.student_id = %s AND ea.status IN ('evaluated', 'submitted')
           ORDER BY ea.submitted_at DESC, ea.id DESC""",
        (student_id,)
    )

    # 3. Available published examinations not yet attempted
    attempted_exam_ids = [a['examination_id'] for a in completed_attempts]
    if ongoing_attempt:
        attempted_exam_ids.append(ongoing_attempt['examination_id'])

    if attempted_exam_ids:
        placeholders = ','.join(['%s'] * len(attempted_exam_ids))
        available_exams = db.query_all(
            f"""SELECT e.*, 
                       (SELECT COUNT(*) FROM questions q WHERE q.examination_id = e.id) AS question_count
                FROM examinations e
                WHERE e.is_published = 1 AND e.id NOT IN ({placeholders})
                ORDER BY e.id DESC""",
            tuple(attempted_exam_ids)
        )
    else:
        available_exams = db.query_all(
            """SELECT e.*, 
                      (SELECT COUNT(*) FROM questions q WHERE q.examination_id = e.id) AS question_count
               FROM examinations e
               WHERE e.is_published = 1
               ORDER BY e.id DESC"""
        )

    # Performance overview stats
    stats = {
        'total_attempts': len(completed_attempts),
        'best_score': max([float(a['total_score']) for a in completed_attempts], default=0.0),
        'avg_score': round(sum([float(a['total_score']) for a in completed_attempts]) / len(completed_attempts), 2) if completed_attempts else 0.0,
        'best_overall_rank': min([a['overall_rank'] for a in completed_attempts if a['overall_rank']], default=None),
        'best_state_rank': min([a['state_rank'] for a in completed_attempts if a['state_rank']], default=None),
        'best_gender_rank': min([a['gender_rank'] for a in completed_attempts if a['gender_rank']], default=None)
    }

    return render_template('student/dashboard.html',
                           student=student,
                           ongoing_attempt=ongoing_attempt,
                           completed_attempts=completed_attempts,
                           available_exams=available_exams,
                           stats=stats)

@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def profile():
    """Student profile viewing and updating."""
    student = get_current_user()
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        state = request.form.get('state', '').strip()
        gender = request.form.get('gender', '').strip()
        
        if not full_name:
            flash("Full name cannot be blank.", "danger")
            return render_template('student/profile.html', student=student, states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if state and state not in INDIAN_STATES:
            flash("Invalid state selected.", "danger")
            return render_template('student/profile.html', student=student, states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if gender and gender not in GENDER_OPTIONS:
            gender = "Prefer not to say"

        db.execute(
            """UPDATE users
               SET full_name = %s, state = %s, gender = %s, updated_at = NOW()
               WHERE id = %s""",
            (full_name, state or None, gender or None, student['id'])
        )
        
        log_action(student['id'], "update_profile", "user", student['id'], f"Updated state to {state}, gender to {gender}.")
        flash("Profile updated successfully.", "success")
        return redirect(url_for('student.profile'))
        
    return render_template('student/profile.html', student=student, states=INDIAN_STATES, genders=GENDER_OPTIONS)

@student_bp.route('/results/<int:attempt_id>')
@login_required
def result_detail(attempt_id):
    """View detailed examination results and question solutions."""
    user = get_current_user()
    
    # Security: Admins can view any result; students can only view their own
    attempt = db.query_one(
        """SELECT ea.*, e.title AS exam_title, e.code AS exam_code, e.total_marks,
                  e.passing_marks, e.positive_marks, e.negative_marks,
                  u.full_name, u.state, u.gender, u.registration_number
           FROM examination_attempts ea
           JOIN examinations e ON ea.examination_id = e.id
           JOIN users u ON ea.student_id = u.id
           WHERE ea.id = %s""",
        (attempt_id,)
    )
    
    if not attempt:
        abort(404)
        
    if user['role'] == 'student' and attempt['student_id'] != user['id']:
        abort(403)
        
    # Questions with student answers
    question_rows = db.query_all(
        """SELECT q.*, sa.selected_option, sa.is_correct, sa.marks_awarded, sa.is_marked_for_review
           FROM questions q
           LEFT JOIN student_answers sa ON q.id = sa.question_id AND sa.attempt_id = %s
           WHERE q.examination_id = %s
           ORDER BY q.id ASC""",
        (attempt_id, attempt['examination_id'])
    )

    # Subject-wise breakdown
    subject_stats = {}
    for q in question_rows:
        subj = q['subject']
        if subj not in subject_stats:
            subject_stats[subj] = {'total': 0, 'answered': 0, 'correct': 0, 'incorrect': 0, 'score': 0.0}
        subject_stats[subj]['total'] += 1
        if q['selected_option']:
            subject_stats[subj]['answered'] += 1
            if q['is_correct'] == 1:
                subject_stats[subj]['correct'] += 1
                subject_stats[subj]['score'] += float(q['marks_awarded'] or 0.0)
            elif q['is_correct'] == 0:
                subject_stats[subj]['incorrect'] += 1
                subject_stats[subj]['score'] += float(q['marks_awarded'] or 0.0)

    return render_template('student/result_detail.html',
                           attempt=attempt,
                           questions=question_rows,
                           subject_stats=subject_stats)
