"""Admin and Question Manager routes for platform management."""

import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
import db
from auth import login_required, role_required, get_current_user, INDIAN_STATES
from services.audit_service import log_action

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@role_required('admin', 'question_manager')
def dashboard():
    """Administrative dashboard showing system metrics and quick management links."""
    user = get_current_user()
    
    # Platform statistics
    stats = {
        'total_students': db.query_one("SELECT COUNT(*) AS c FROM users WHERE role = 'student'")['c'],
        'active_students': db.query_one("SELECT COUNT(*) AS c FROM users WHERE role = 'student' AND is_active = 1")['c'],
        'total_exams': db.query_one("SELECT COUNT(*) AS c FROM examinations")['c'],
        'published_exams': db.query_one("SELECT COUNT(*) AS c FROM examinations WHERE is_published = 1")['c'],
        'total_questions': db.query_one("SELECT COUNT(*) AS c FROM questions")['c'],
        'total_attempts': db.query_one("SELECT COUNT(*) AS c FROM examination_attempts")['c'],
        'completed_attempts': db.query_one("SELECT COUNT(*) AS c FROM examination_attempts WHERE status IN ('evaluated', 'submitted')")['c']
    }

    # Recent student attempts
    recent_attempts = db.query_all(
        """SELECT ea.id, ea.total_score, ea.percentage, ea.status, ea.submitted_at,
                  u.full_name, u.state, u.registration_number,
                  e.title AS exam_title
           FROM examination_attempts ea
           JOIN users u ON ea.student_id = u.id
           JOIN examinations e ON ea.examination_id = e.id
           ORDER BY ea.id DESC LIMIT 6"""
    )

    # Recent examinations
    recent_exams = db.query_all(
        """SELECT e.*, 
                  (SELECT COUNT(*) FROM questions q WHERE q.examination_id = e.id) AS question_count
           FROM examinations e
           ORDER BY e.id DESC LIMIT 5"""
    )

    # Recent audit logs
    recent_logs = db.query_all(
        """SELECT al.*, u.full_name
           FROM audit_logs al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.id DESC LIMIT 8"""
    )

    return render_template('admin/dashboard.html',
                           user=user,
                           stats=stats,
                           recent_attempts=recent_attempts,
                           recent_exams=recent_exams,
                           recent_logs=recent_logs)

# -------------------------------------------------------------
# STUDENT MANAGEMENT
# -------------------------------------------------------------

@admin_bp.route('/students')
@login_required
@role_required('admin')
def students():
    """List and filter registered students with pagination."""
    search = request.args.get('search', '').strip()
    state = request.args.get('state', '').strip()
    status = request.args.get('status', '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 20
    offset = (page - 1) * per_page

    where = ["role = 'student'"]
    params = []

    if search:
        where.append("(full_name LIKE %s OR email LIKE %s OR registration_number LIKE %s)")
        search_pat = f"%{search}%"
        params.extend([search_pat, search_pat, search_pat])

    if state:
        where.append("state = %s")
        params.append(state)

    if status == 'active':
        where.append("is_active = 1")
    elif status == 'inactive':
        where.append("is_active = 0")

    where_sql = " AND ".join(where)

    total_count = db.query_one(f"SELECT COUNT(*) AS c FROM users WHERE {where_sql}", tuple(params))['c']

    sql = f"""SELECT u.*,
                     (SELECT COUNT(*) FROM examination_attempts ea WHERE ea.student_id = u.id) AS attempts_count,
                     (SELECT MAX(total_score) FROM examination_attempts ea WHERE ea.student_id = u.id) AS highest_score
              FROM users u
              WHERE {where_sql}
              ORDER BY u.id DESC
              LIMIT %s OFFSET %s"""
    params.extend([per_page, offset])
    student_list = db.query_all(sql, tuple(params))

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template('admin/students.html',
                           students=student_list,
                           search=search,
                           state=state,
                           status=status,
                           page=page,
                           total_pages=total_pages,
                           total_count=total_count,
                           states=INDIAN_STATES)

@admin_bp.route('/students/<int:student_id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def toggle_student_status(student_id):
    """Activate or deactivate a student account."""
    current_admin = get_current_user()
    student = db.query_one("SELECT id, full_name, is_active FROM users WHERE id = %s AND role = 'student'", (student_id,))
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for('admin.students'))

    new_status = 0 if student['is_active'] else 1
    db.execute("UPDATE users SET is_active = %s, updated_at = NOW() WHERE id = %s", (new_status, student_id))
    
    action_text = "Activated" if new_status else "Deactivated"
    log_action(current_admin['id'], "toggle_user_status", "user", student_id, f"{action_text} student {student['full_name']}.")
    flash(f"Student account {action_text.lower()} successfully.", "success")
    return redirect(url_for('admin.students'))

@admin_bp.route('/students/export')
@login_required
@role_required('admin')
def export_students_csv():
    """Export registered students list to CSV format."""
    current_admin = get_current_user()
    students = db.query_all(
        """SELECT id, registration_number, full_name, email, state, gender, is_active, created_at
           FROM users WHERE role = 'student' ORDER BY id ASC"""
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Registration No", "Full Name", "Email", "State", "Gender", "Status", "Joined At"])

    for s in students:
        writer.writerow([
            s["id"],
            s.get("registration_number") or "N/A",
            s["full_name"],
            s["email"],
            s.get("state") or "N/A",
            s.get("gender") or "N/A",
            "Active" if s["is_active"] else "Inactive",
            s["created_at"]
        ])

    log_action(current_admin['id'], "export_students_csv", "system", None, "Exported student roster.")
    
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=secureneet_students.csv"
    return response

# -------------------------------------------------------------
# EXAMINATION MANAGEMENT
# -------------------------------------------------------------

@admin_bp.route('/exams')
@login_required
@role_required('admin', 'question_manager')
def exams():
    """List all examinations with question & attempt counts."""
    exam_list = db.query_all(
        """SELECT e.*, u.full_name AS creator_name,
                  (SELECT COUNT(*) FROM questions q WHERE q.examination_id = e.id) AS question_count,
                  (SELECT COUNT(*) FROM examination_attempts ea WHERE ea.examination_id = e.id) AS total_attempts
           FROM examinations e
           LEFT JOIN users u ON e.created_by = u.id
           ORDER BY e.id DESC"""
    )
    return render_template('admin/exams.html', exams=exam_list)

@admin_bp.route('/exams/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_exam():
    """Create a new NEET examination."""
    admin = get_current_user()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        code = request.form.get('code', '').strip().upper()
        description = request.form.get('description', '').strip()
        duration_minutes = request.form.get('duration_minutes', 180, type=int)
        total_marks = request.form.get('total_marks', 720, type=int)
        passing_marks = request.form.get('passing_marks', 360, type=int)
        positive_marks = request.form.get('positive_marks', 4.0, type=float)
        negative_marks = request.form.get('negative_marks', 1.0, type=float)
        start_time = request.form.get('start_time', '').strip() or None
        end_time = request.form.get('end_time', '').strip() or None
        is_published = 1 if request.form.get('is_published') else 0

        if not title or not code:
            flash("Title and Exam Code are required.", "danger")
            return render_template('admin/exam_form.html', exam=None)

        existing = db.query_one("SELECT id FROM examinations WHERE code = %s", (code,))
        if existing:
            flash("An examination with this code already exists.", "danger")
            return render_template('admin/exam_form.html', exam=None)

        exam_id = db.execute(
            """INSERT INTO examinations
               (title, code, description, duration_minutes, total_marks, passing_marks,
                positive_marks, negative_marks, start_time, end_time, is_published, created_by, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (title, code, description, duration_minutes, total_marks, passing_marks,
             positive_marks, negative_marks, start_time, end_time, is_published, admin['id'])
        )

        log_action(admin['id'], "create_examination", "examination", exam_id, f"Created examination {code}: {title}")
        flash(f"Examination '{title}' created successfully.", "success")
        return redirect(url_for('admin.exams'))

    return render_template('admin/exam_form.html', exam=None)

@admin_bp.route('/exams/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_exam(exam_id):
    """Edit an existing examination."""
    admin = get_current_user()
    exam = db.query_one("SELECT * FROM examinations WHERE id = %s", (exam_id,))
    if not exam:
        flash("Examination not found.", "danger")
        return redirect(url_for('admin.exams'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        code = request.form.get('code', '').strip().upper()
        description = request.form.get('description', '').strip()
        duration_minutes = request.form.get('duration_minutes', 180, type=int)
        total_marks = request.form.get('total_marks', 720, type=int)
        passing_marks = request.form.get('passing_marks', 360, type=int)
        positive_marks = request.form.get('positive_marks', 4.0, type=float)
        negative_marks = request.form.get('negative_marks', 1.0, type=float)
        start_time = request.form.get('start_time', '').strip() or None
        end_time = request.form.get('end_time', '').strip() or None
        is_published = 1 if request.form.get('is_published') else 0

        if not title or not code:
            flash("Title and Exam Code are required.", "danger")
            return render_template('admin/exam_form.html', exam=exam)

        existing = db.query_one("SELECT id FROM examinations WHERE code = %s AND id != %s", (code, exam_id))
        if existing:
            flash("Another examination with this code already exists.", "danger")
            return render_template('admin/exam_form.html', exam=exam)

        db.execute(
            """UPDATE examinations
               SET title = %s, code = %s, description = %s, duration_minutes = %s,
                   total_marks = %s, passing_marks = %s, positive_marks = %s, negative_marks = %s,
                   start_time = %s, end_time = %s, is_published = %s, updated_at = NOW()
               WHERE id = %s""",
            (title, code, description, duration_minutes, total_marks, passing_marks,
             positive_marks, negative_marks, start_time, end_time, is_published, exam_id)
        )

        log_action(admin['id'], "update_examination", "examination", exam_id, f"Updated examination {code}.")
        flash("Examination updated successfully.", "success")
        return redirect(url_for('admin.exams'))

    return render_template('admin/exam_form.html', exam=exam)

@admin_bp.route('/exams/<int:exam_id>/toggle-publish', methods=['POST'])
@login_required
@role_required('admin')
def toggle_publish_exam(exam_id):
    """Publish or unpublish an examination."""
    admin = get_current_user()
    exam = db.query_one("SELECT id, title, is_published FROM examinations WHERE id = %s", (exam_id,))
    if not exam:
        flash("Examination not found.", "danger")
        return redirect(url_for('admin.exams'))

    new_state = 0 if exam['is_published'] else 1
    db.execute("UPDATE examinations SET is_published = %s, updated_at = NOW() WHERE id = %s", (new_state, exam_id))
    
    state_str = "Published" if new_state else "Unpublished"
    log_action(admin['id'], "toggle_publish_examination", "examination", exam_id, f"{state_str} {exam['title']}.")
    flash(f"Examination '{exam['title']}' has been {state_str.lower()}.", "success")
    return redirect(url_for('admin.exams'))

@admin_bp.route('/exams/<int:exam_id>/attempts')
@login_required
@role_required('admin', 'question_manager')
def exam_attempts(exam_id):
    """View all student attempts for a particular examination."""
    exam = db.query_one("SELECT * FROM examinations WHERE id = %s", (exam_id,))
    if not exam:
        flash("Examination not found.", "danger")
        return redirect(url_for('admin.exams'))

    attempts = db.query_all(
        """SELECT ea.*, u.full_name, u.email, u.state, u.gender, u.registration_number
           FROM examination_attempts ea
           JOIN users u ON ea.student_id = u.id
           WHERE ea.examination_id = %s
           ORDER BY ea.total_score DESC, ea.time_taken_seconds ASC""",
        (exam_id,)
    )

    return render_template('admin/attempts.html', exam=exam, attempts=attempts)

# -------------------------------------------------------------
# QUESTION MANAGEMENT
# -------------------------------------------------------------

@admin_bp.route('/questions')
@login_required
@role_required('admin', 'question_manager')
def questions():
    """List questions with exam & subject filters."""
    exam_id = request.args.get('exam_id', type=int)
    subject = request.args.get('subject', '').strip()

    exams_list = db.query_all("SELECT id, title, code FROM examinations ORDER BY id DESC")
    
    where = ["1=1"]
    params = []
    if exam_id:
        where.append("q.examination_id = %s")
        params.append(exam_id)
    if subject:
        where.append("q.subject = %s")
        params.append(subject)

    sql = f"""SELECT q.*, e.title AS exam_title, e.code AS exam_code
              FROM questions q
              JOIN examinations e ON q.examination_id = e.id
              WHERE {' AND '.join(where)}
              ORDER BY q.examination_id DESC, q.subject ASC, q.id ASC"""
    question_list = db.query_all(sql, tuple(params) if params else None)

    return render_template('admin/questions.html',
                           questions=question_list,
                           exams=exams_list,
                           selected_exam_id=exam_id,
                           selected_subject=subject)

@admin_bp.route('/questions/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'question_manager')
def create_question():
    """Create a new multiple choice question."""
    user = get_current_user()
    exams_list = db.query_all("SELECT id, title, code, positive_marks, negative_marks FROM examinations ORDER BY id DESC")

    if request.method == 'POST':
        examination_id = request.form.get('examination_id', type=int)
        subject = request.form.get('subject', '').strip()
        topic = request.form.get('topic', '').strip()
        question_text = request.form.get('question_text', '').strip()
        option_a = request.form.get('option_a', '').strip()
        option_b = request.form.get('option_b', '').strip()
        option_c = request.form.get('option_c', '').strip()
        option_d = request.form.get('option_d', '').strip()
        correct_option = request.form.get('correct_option', '').strip().upper()
        marks = request.form.get('marks', 4.0, type=float)
        negative_marks = request.form.get('negative_marks', 1.0, type=float)
        explanation = request.form.get('explanation', '').strip()

        if not (examination_id and subject and question_text and option_a and option_b and option_c and option_d and correct_option):
            flash("All question fields and four options are mandatory.", "danger")
            return render_template('admin/question_form.html', question=None, exams=exams_list)

        if correct_option not in ('A', 'B', 'C', 'D'):
            flash("Correct option must be A, B, C, or D.", "danger")
            return render_template('admin/question_form.html', question=None, exams=exams_list)

        q_id = db.execute(
            """INSERT INTO questions
               (examination_id, subject, topic, question_text, option_a, option_b, option_c, option_d,
                correct_option, marks, negative_marks, explanation, created_by, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (examination_id, subject, topic or None, question_text, option_a, option_b, option_c, option_d,
             correct_option, marks, negative_marks, explanation or None, user['id'])
        )

        log_action(user['id'], "create_question", "question", q_id, f"Added question to exam #{examination_id} in {subject}.")
        flash("Question created successfully.", "success")
        return redirect(url_for('admin.questions', exam_id=examination_id))

    return render_template('admin/question_form.html', question=None, exams=exams_list)

@admin_bp.route('/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'question_manager')
def edit_question(question_id):
    """Edit an existing question."""
    user = get_current_user()
    question = db.query_one("SELECT * FROM questions WHERE id = %s", (question_id,))
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for('admin.questions'))

    exams_list = db.query_all("SELECT id, title, code FROM examinations ORDER BY id DESC")

    if request.method == 'POST':
        examination_id = request.form.get('examination_id', type=int)
        subject = request.form.get('subject', '').strip()
        topic = request.form.get('topic', '').strip()
        question_text = request.form.get('question_text', '').strip()
        option_a = request.form.get('option_a', '').strip()
        option_b = request.form.get('option_b', '').strip()
        option_c = request.form.get('option_c', '').strip()
        option_d = request.form.get('option_d', '').strip()
        correct_option = request.form.get('correct_option', '').strip().upper()
        marks = request.form.get('marks', 4.0, type=float)
        negative_marks = request.form.get('negative_marks', 1.0, type=float)
        explanation = request.form.get('explanation', '').strip()

        if not (examination_id and subject and question_text and option_a and option_b and option_c and option_d and correct_option):
            flash("All question fields and four options are mandatory.", "danger")
            return render_template('admin/question_form.html', question=question, exams=exams_list)

        db.execute(
            """UPDATE questions
               SET examination_id = %s, subject = %s, topic = %s, question_text = %s,
                   option_a = %s, option_b = %s, option_c = %s, option_d = %s,
                   correct_option = %s, marks = %s, negative_marks = %s, explanation = %s
               WHERE id = %s""",
            (examination_id, subject, topic or None, question_text, option_a, option_b, option_c, option_d,
             correct_option, marks, negative_marks, explanation or None, question_id)
        )

        log_action(user['id'], "update_question", "question", question_id, f"Edited question #{question_id}.")
        flash("Question updated successfully.", "success")
        return redirect(url_for('admin.questions', exam_id=examination_id))

    return render_template('admin/question_form.html', question=question, exams=exams_list)

@admin_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_question(question_id):
    """Safely delete a question."""
    admin = get_current_user()
    question = db.query_one("SELECT id, examination_id FROM questions WHERE id = %s", (question_id,))
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for('admin.questions'))

    db.execute("DELETE FROM questions WHERE id = %s", (question_id,))
    log_action(admin['id'], "delete_question", "question", question_id, f"Deleted question #{question_id}.")
    flash("Question deleted successfully.", "success")
    return redirect(url_for('admin.questions', exam_id=question['examination_id']))

# -------------------------------------------------------------
# AUDIT LOGS
# -------------------------------------------------------------

@admin_bp.route('/audit-logs')
@login_required
@role_required('admin')
def audit_logs():
    """Security audit log browser."""
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 30
    offset = (page - 1) * per_page

    total_logs = db.query_one("SELECT COUNT(*) AS c FROM audit_logs")['c']
    logs = db.query_all(
        """SELECT al.*, u.full_name, u.email, u.role
           FROM audit_logs al
           LEFT JOIN users u ON al.user_id = u.id
           ORDER BY al.id DESC
           LIMIT %s OFFSET %s""",
        (per_page, offset)
    )

    total_pages = max(1, (total_logs + per_page - 1) // per_page)

    return render_template('admin/audit_logs.html',
                           logs=logs,
                           page=page,
                           total_pages=total_pages,
                           total_logs=total_logs)
