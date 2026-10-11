"""Pytest configuration and fixtures for SecureNEET test suite."""

import os
import pytest
from app import create_app
import db
from config import Config
from auth import hash_password

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key-for-secureneet"
    DB_TYPE = "sqlite"
    SQLITE_PATH = ":memory:" # In-memory database for isolated fast tests

@pytest.fixture(scope="session")
def app():
    """Create test application instance."""
    app = create_app(TestConfig)
    return app

@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean database schema for each test."""
    db.init_db()
    # Clear all rows
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM student_answers")
        cur.execute("DELETE FROM examination_attempts")
        cur.execute("DELETE FROM questions")
        cur.execute("DELETE FROM examinations")
        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM audit_logs")
        cur.close()
    yield

@pytest.fixture
def client(app):
    """Test HTTP client."""
    return app.test_client()

@pytest.fixture
def seed_users():
    """Seed sample Admin, Question Manager, and Students."""
    admin_id = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active)
           VALUES (%s, %s, %s, 'admin', 'Delhi', 'Male', 'ADMTEST01', 1)""",
        ("Test Admin", "admin@test.com", hash_password("AdminPass123"))
    )

    qm_id = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active)
           VALUES (%s, %s, %s, 'question_manager', 'Karnataka', 'Female', 'QMTEST01', 1)""",
        ("Test QM", "qm@test.com", hash_password("QMPass123"))
    )

    student1_id = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active)
           VALUES (%s, %s, %s, 'student', 'Maharashtra', 'Male', 'STU001', 1)""",
        ("Student Alpha", "alpha@test.com", hash_password("StudentPass123"))
    )

    student2_id = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active)
           VALUES (%s, %s, %s, 'student', 'Maharashtra', 'Female', 'STU002', 1)""",
        ("Student Beta", "beta@test.com", hash_password("StudentPass123"))
    )

    student3_id = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, state, gender, registration_number, is_active)
           VALUES (%s, %s, %s, 'student', 'Delhi', 'Prefer not to say', 'STU003', 1)""",
        ("Student Gamma", "gamma@test.com", hash_password("StudentPass123"))
    )

    return {
        "admin": {"id": admin_id, "email": "admin@test.com", "password": "AdminPass123"},
        "qm": {"id": qm_id, "email": "qm@test.com", "password": "QMPass123"},
        "student1": {"id": student1_id, "email": "alpha@test.com", "password": "StudentPass123"},
        "student2": {"id": student2_id, "email": "beta@test.com", "password": "StudentPass123"},
        "student3": {"id": student3_id, "email": "gamma@test.com", "password": "StudentPass123"}
    }
