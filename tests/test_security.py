"""Security tests for RBAC, privilege escalation prevention, and cross-student data isolation."""

import pytest
import db

def test_student_cannot_access_admin_dashboard(client, seed_users):
    """Ensure student is rejected from administrative endpoints."""
    # Log in as Student Alpha
    client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    })

    resp = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Access denied. You lack the required permissions" in resp.data

def test_student_cannot_create_examination(client, seed_users):
    """Ensure student cannot post to exam creation endpoint."""
    client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    })

    resp = client.post('/admin/exams/create', data={
        'title': 'Hacked Exam',
        'code': 'HACK-01'
    }, follow_redirects=True)
    assert b"Access denied" in resp.data

    exam = db.query_one("SELECT id FROM examinations WHERE code = 'HACK-01'")
    assert exam is None

def test_cross_student_result_isolation(client, seed_users):
    """Ensure student Alpha cannot view student Beta's private scorecard."""
    admin_id = seed_users["admin"]["id"]
    beta_id = seed_users["student2"]["id"]
    exam_id = db.execute(
        """INSERT INTO examinations (title, code, is_published, created_by)
           VALUES ('Private Test', 'PRIV-01', 1, %s)""",
        (admin_id,)
    )
    att_beta = db.execute(
        """INSERT INTO examination_attempts
           (examination_id, student_id, start_time, deadline_time, status, total_score)
           VALUES (%s, %s, NOW(), NOW(), 'evaluated', 50.0)""",
        (exam_id, beta_id)
    )

    # Log in as Student Alpha
    client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    })

    # Student Alpha tries to inspect Student Beta's scorecard
    resp = client.get(f'/student/results/{att_beta}')
    assert resp.status_code == 403

def test_cross_student_autosave_tampering_blocked(client, seed_users):
    """Ensure student Alpha cannot modify answers for student Beta's attempt."""
    admin_id = seed_users["admin"]["id"]
    beta_id = seed_users["student2"]["id"]
    exam_id = db.execute(
        """INSERT INTO examinations (title, code, is_published, created_by)
           VALUES ('Tamper Test', 'TAMP-01', 1, %s)""",
        (admin_id,)
    )
    q_id = db.execute(
        """INSERT INTO questions (examination_id, subject, question_text, option_a, option_b, option_c, option_d, correct_option)
           VALUES (%s, 'Physics', 'Q1?', 'A', 'B', 'C', 'D', 'A')""",
        (exam_id,)
    )
    att_beta = db.execute(
        """INSERT INTO examination_attempts
           (examination_id, student_id, start_time, deadline_time, status)
           VALUES (%s, %s, NOW(), NOW(), 'in_progress')""",
        (exam_id, beta_id)
    )

    # Log in as Student Alpha
    client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    })

    # Student Alpha attempts to save answer on Beta's attempt
    resp = client.post(f'/exam/api/attempt/{att_beta}/save-answer', json={
        'question_id': q_id,
        'selected_option': 'B'
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "Unauthorized" in data["error"]
