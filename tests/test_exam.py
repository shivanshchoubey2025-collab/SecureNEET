"""Tests for examination lifecycle, server-side timer, autosave, and score evaluation."""

from datetime import datetime, timedelta
import pytest
import db
from services.exam_service import get_or_create_attempt, save_answer, evaluate_attempt

@pytest.fixture
def exam_with_questions(seed_users):
    """Fixture providing a published examination with questions."""
    admin_id = seed_users["admin"]["id"]
    exam_id = db.execute(
        """INSERT INTO examinations
           (title, code, duration_minutes, total_marks, passing_marks, positive_marks, negative_marks, is_published, created_by)
           VALUES ('NEET Mini Test', 'NEET-MINI', 60, 20, 10, 4.0, 1.0, 1, %s)""",
        (admin_id,)
    )

    # 3 questions
    q1 = db.execute(
        """INSERT INTO questions
           (examination_id, subject, topic, question_text, option_a, option_b, option_c, option_d, correct_option, marks, negative_marks)
           VALUES (%s, 'Physics', 'Kinematics', 'Speed unit?', 'm/s', 'kg', 'sec', 'joule', 'A', 4.0, 1.0)""",
        (exam_id,)
    )
    q2 = db.execute(
        """INSERT INTO questions
           (examination_id, subject, topic, question_text, option_a, option_b, option_c, option_d, correct_option, marks, negative_marks)
           VALUES (%s, 'Chemistry', 'Bonds', 'CO2 geometry?', 'Bent', 'Linear', 'Trigonal', 'Octahedral', 'B', 4.0, 1.0)""",
        (exam_id,)
    )
    q3 = db.execute(
        """INSERT INTO questions
           (examination_id, subject, topic, question_text, option_a, option_b, option_c, option_d, correct_option, marks, negative_marks)
           VALUES (%s, 'Botany', 'Cells', 'Primary cell organelle?', 'Nucleus', 'Vacuole', 'Ribosome', 'Wall', 'A', 4.0, 1.0)""",
        (exam_id,)
    )

    return {"exam_id": exam_id, "questions": [q1, q2, q3]}

def test_attempt_initialization_sets_server_deadline(exam_with_questions, seed_users):
    """Test that creating an attempt computes trusted server start and deadline times."""
    student_id = seed_users["student1"]["id"]
    exam_id = exam_with_questions["exam_id"]

    attempt, msg = get_or_create_attempt(student_id, exam_id)
    assert attempt is not None
    assert msg == "created"
    assert attempt["status"] == "in_progress"

    # Deadline must be ~60 minutes after start time
    start = attempt["start_time"]
    deadline = attempt["deadline_time"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline)
    diff = (deadline - start).total_seconds()
    assert 3590 <= diff <= 3610

def test_autosave_and_persistence(exam_with_questions, seed_users):
    """Test that student answers are recorded and persisted in student_answers."""
    student_id = seed_users["student1"]["id"]
    exam_id = exam_with_questions["exam_id"]
    q1 = exam_with_questions["questions"][0]

    attempt, _ = get_or_create_attempt(student_id, exam_id)
    
    # Save Option A
    success, msg = save_answer(attempt["id"], student_id, q1, "A", is_marked_for_review=False)
    assert success is True

    saved = db.query_one("SELECT * FROM student_answers WHERE attempt_id = %s AND question_id = %s", (attempt["id"], q1))
    assert saved is not None
    assert saved["selected_option"] == "A"
    assert saved["is_marked_for_review"] == 0

    # Update to Mark for Review
    success, _ = save_answer(attempt["id"], student_id, q1, "A", is_marked_for_review=True)
    assert success is True
    saved2 = db.query_one("SELECT * FROM student_answers WHERE attempt_id = %s AND question_id = %s", (attempt["id"], q1))
    assert saved2["is_marked_for_review"] == 1

def test_score_calculation_positive_and_negative_marking(exam_with_questions, seed_users):
    """Test that correct answers earn +4, wrong answers incur -1, and unattempted earn 0."""
    student_id = seed_users["student1"]["id"]
    exam_id = exam_with_questions["exam_id"]
    q1, q2, q3 = exam_with_questions["questions"]

    attempt, _ = get_or_create_attempt(student_id, exam_id)

    # Q1: Correct (A) -> +4
    save_answer(attempt["id"], student_id, q1, "A")
    # Q2: Wrong (A instead of B) -> -1
    save_answer(attempt["id"], student_id, q2, "A")
    # Q3: Unanswered -> 0

    success, msg = evaluate_attempt(attempt["id"], status="submitted")
    assert success is True

    evaluated = db.query_one("SELECT * FROM examination_attempts WHERE id = %s", (attempt["id"],))
    assert evaluated["status"] == "evaluated"
    # Total score = 4 - 1 + 0 = 3.0
    assert float(evaluated["total_score"]) == 3.0
    assert evaluated["questions_answered"] == 2
    assert evaluated["correct_answers"] == 1
    assert evaluated["incorrect_answers"] == 1
    assert evaluated["unanswered_count"] == 1

def test_duplicate_submission_prevention(exam_with_questions, seed_users):
    """Test that repeated submission calls do not create duplicate records or modify scores."""
    student_id = seed_users["student1"]["id"]
    exam_id = exam_with_questions["exam_id"]
    q1 = exam_with_questions["questions"][0]

    attempt, _ = get_or_create_attempt(student_id, exam_id)
    save_answer(attempt["id"], student_id, q1, "A")
    evaluate_attempt(attempt["id"], status="submitted")

    # Second evaluation attempt
    success, msg = evaluate_attempt(attempt["id"], status="submitted")
    assert success is True
    assert "already evaluated" in msg

    # Count of attempts must remain 1
    count = db.query_one("SELECT COUNT(*) AS c FROM examination_attempts WHERE student_id = %s", (student_id,))["c"]
    assert count == 1
