"""Examination lifecycle and evaluation service.

Manages exam eligibility, server-authoritative timers, autosave,
automatic submission upon deadline expiration, and reliable scoring.
"""

from datetime import datetime, timedelta
import db
from config import Config
from services.audit_service import log_action

def get_exam_by_id(exam_id):
    """Retrieve examination details by ID."""
    return db.query_one("SELECT * FROM examinations WHERE id = %s", (exam_id,))

def get_exam_questions(exam_id, include_correct=False):
    """Retrieve questions for an examination.
    
    Hides correct options and explanations during live exam attempts.
    """
    if include_correct:
        sql = """SELECT id, examination_id, subject, topic, question_text,
                        option_a, option_b, option_c, option_d,
                        correct_option, marks, negative_marks, explanation
                 FROM questions
                 WHERE examination_id = %s
                 ORDER BY id ASC"""
    else:
        sql = """SELECT id, examination_id, subject, topic, question_text,
                        option_a, option_b, option_c, option_d,
                        marks, negative_marks
                 FROM questions
                 WHERE examination_id = %s
                 ORDER BY id ASC"""
    return db.query_all(sql, (exam_id,))

def get_or_create_attempt(student_id, exam_id):
    """Validate student eligibility and fetch existing or initialize a new attempt."""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return None, "Examination does not exist."
    if not exam.get("is_published"):
        return None, "This examination has not been published yet."
    
    # Check start and end times if configured
    now = datetime.now()
    if exam.get("start_time"):
        start_dt = exam["start_time"]
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
        if now < start_dt:
            return None, f"Examination starts on {start_dt.strftime('%Y-%m-%d %H:%M')}."
            
    if exam.get("end_time"):
        end_dt = exam["end_time"]
        if isinstance(end_dt, str):
            end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
        if now > end_dt:
            return None, "Examination submission deadline has passed."

    # Look for existing attempt
    existing_attempt = db.query_one(
        """SELECT * FROM examination_attempts
           WHERE student_id = %s AND examination_id = %s
           ORDER BY id DESC LIMIT 1""",
        (student_id, exam_id)
    )
    
    if existing_attempt:
        status = existing_attempt["status"]
        if status in ("submitted", "evaluated"):
            return existing_attempt, "already_submitted"
        
        # Check deadline expiration on existing attempt
        deadline = existing_attempt["deadline_time"]
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            
        grace_deadline = deadline + timedelta(seconds=Config.EXAM_GRACE_PERIOD_SECONDS)
        if datetime.now() > grace_deadline:
            # Deadline expired; finalize automatically
            evaluate_attempt(existing_attempt["id"], status="expired")
            updated = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (existing_attempt["id"],))
            return updated, "expired"
            
        return existing_attempt, "in_progress"

    # Create new attempt with server-authoritative start_time and deadline_time
    duration_min = exam.get("duration_minutes", 180)
    start_time = datetime.now()
    deadline_time = start_time + timedelta(minutes=duration_min)
    
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO examination_attempts
               (examination_id, student_id, start_time, deadline_time, status, total_score)
               VALUES (%s, %s, %s, %s, 'in_progress', 0.00)""",
            (exam_id, student_id, start_time, deadline_time)
        )
        attempt_id = cur.lastrowid
        cur.close()
        
    log_action(student_id, "start_examination", "examination", exam_id, f"Attempt #{attempt_id} initiated.")
    new_attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    return new_attempt, "created"

def get_student_answers(attempt_id):
    """Fetch all saved answers for a given attempt."""
    rows = db.query_all(
        """SELECT question_id, selected_option, is_marked_for_review, answered_at
           FROM student_answers WHERE attempt_id = %s""",
        (attempt_id,)
    )
    # Return as dict keyed by question_id for fast lookup
    return {r["question_id"]: r for r in rows}

def save_answer(attempt_id, student_id, question_id, selected_option, is_marked_for_review=False):
    """Save or update an answer with validation."""
    attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    if not attempt:
        return False, "Attempt not found."
    if attempt["student_id"] != student_id:
        return False, "Unauthorized access to attempt."
    if attempt["status"] != "in_progress":
        return False, "Attempt has already been finalized."
        
    # Check server-side deadline
    deadline = attempt["deadline_time"]
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    if datetime.now() > (deadline + timedelta(seconds=Config.EXAM_GRACE_PERIOD_SECONDS)):
        evaluate_attempt(attempt_id, status="expired")
        return False, "Examination deadline reached. Attempt automatically submitted."

    # Validate option choice (A, B, C, D, or None/clear)
    if selected_option and selected_option not in ('A', 'B', 'C', 'D'):
        return False, "Invalid option selection."

    # Insert or update answer
    existing = db.query_one(
        "SELECT id FROM student_answers WHERE attempt_id = %s AND question_id = %s",
        (attempt_id, question_id)
    )
    
    with db.transaction() as conn:
        cur = conn.cursor()
        if existing:
            cur.execute(
                """UPDATE student_answers
                   SET selected_option = %s, is_marked_for_review = %s, answered_at = NOW()
                   WHERE attempt_id = %s AND question_id = %s""",
                (selected_option, 1 if is_marked_for_review else 0, attempt_id, question_id)
            )
        else:
            cur.execute(
                """INSERT INTO student_answers
                   (attempt_id, question_id, selected_option, is_marked_for_review, answered_at)
                   VALUES (%s, %s, %s, %s, NOW())""",
                (attempt_id, question_id, selected_option, 1 if is_marked_for_review else 0)
            )
        cur.close()

    return True, "Answer recorded successfully."

def evaluate_attempt(attempt_id, status="submitted"):
    """Server-side scoring and finalization of an examination attempt.
    
    Evaluates:
      - Positive marks for correct choices
      - Negative marks for wrong choices
      - 0 marks for unattempted
    Recalculates counts and marks atomicity in transaction.
    """
    attempt = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt_id,))
    if not attempt:
        return False, "Attempt not found."
    if attempt["status"] in ("submitted", "evaluated") and status != "re_evaluate":
        return True, "Attempt is already evaluated."

    exam = get_exam_by_id(attempt["examination_id"])
    if not exam:
        return False, "Associated examination not found."

    questions = db.query_all(
        "SELECT id, correct_option, marks, negative_marks FROM questions WHERE examination_id = %s",
        (attempt["examination_id"],)
    )
    saved_answers = {a["question_id"]: a for a in db.query_all(
        "SELECT * FROM student_answers WHERE attempt_id = %s", (attempt_id,)
    )}

    total_score = 0.0
    questions_answered = 0
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0

    now = datetime.now()
    start_dt = attempt["start_time"]
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
    time_taken_seconds = max(1, int((now - start_dt).total_seconds()))
    max_duration_seconds = exam["duration_minutes"] * 60
    if time_taken_seconds > max_duration_seconds:
        time_taken_seconds = max_duration_seconds

    with db.transaction() as conn:
        cur = conn.cursor()
        for q in questions:
            q_id = q["id"]
            correct_opt = q["correct_option"]
            pos_mark = float(q.get("marks") or exam.get("positive_marks") or 4.0)
            neg_mark = float(q.get("negative_marks") or exam.get("negative_marks") or 1.0)
            
            ans = saved_answers.get(q_id)
            selected = ans.get("selected_option") if ans else None
            
            if selected and selected in ('A', 'B', 'C', 'D'):
                questions_answered += 1
                if selected == correct_opt:
                    is_correct = 1
                    marks_awarded = pos_mark
                    correct_count += 1
                    total_score += pos_mark
                else:
                    is_correct = 0
                    marks_awarded = -neg_mark
                    incorrect_count += 1
                    total_score -= neg_mark
                
                # Update answer record with correctness & marks
                cur.execute(
                    """UPDATE student_answers
                       SET is_correct = %s, marks_awarded = %s
                       WHERE attempt_id = %s AND question_id = %s""",
                    (is_correct, marks_awarded, attempt_id, q_id)
                )
            else:
                unanswered_count += 1
                if ans:
                    cur.execute(
                        """UPDATE student_answers
                           SET is_correct = NULL, marks_awarded = 0.00
                           WHERE attempt_id = %s AND question_id = %s""",
                        (attempt_id, q_id)
                    )

        total_exam_marks = float(exam.get("total_marks", 720.0))
        percentage = round((total_score / total_exam_marks * 100.0), 2) if total_exam_marks > 0 else 0.0

        final_status = "evaluated" if status in ("submitted", "re_evaluate") else status

        cur.execute(
            """UPDATE examination_attempts
               SET status = %s,
                   submitted_at = %s,
                   total_score = %s,
                   questions_answered = %s,
                   correct_answers = %s,
                   incorrect_answers = %s,
                   unanswered_count = %s,
                   percentage = %s,
                   time_taken_seconds = %s
               WHERE id = %s""",
            (final_status, now, total_score, questions_answered, correct_count,
             incorrect_count, unanswered_count, percentage, time_taken_seconds, attempt_id)
        )
        cur.close()

    log_action(attempt["student_id"], "submit_examination", "examination_attempt", attempt_id,
               f"Scored {total_score}/{total_exam_marks} ({percentage}%).")

    # Trigger rank recalculation
    from services.leaderboard_service import update_examination_ranks
    try:
        update_examination_ranks(attempt["examination_id"])
    except Exception as e:
        print(f"Warning: rank update failed: {e}")

    return True, "Examination evaluated successfully."
