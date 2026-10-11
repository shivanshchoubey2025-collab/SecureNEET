"""Unit and integration tests for authentication, authorization, and RBAC."""

import pytest
import db
from auth import verify_password

def test_student_registration_success(client):
    """Test successful student registration with state and gender."""
    resp = client.post('/auth/register', data={
        'full_name': 'New Aspirant',
        'email': 'aspirant@example.com',
        'password': 'StrongPassword123',
        'confirm_password': 'StrongPassword123',
        'state': 'Gujarat',
        'gender': 'Female'
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    user = db.query_one("SELECT * FROM users WHERE email = %s", ('aspirant@example.com',))
    assert user is not None
    assert user['full_name'] == 'New Aspirant'
    assert user['role'] == 'student'
    assert user['state'] == 'Gujarat'
    assert user['gender'] == 'Female'
    assert user['password_hash'] != 'StrongPassword123'
    assert verify_password(user['password_hash'], 'StrongPassword123')

def test_duplicate_email_registration_rejected(client, seed_users):
    """Test that duplicate email registration is rejected."""
    resp = client.post('/auth/register', data={
        'full_name': 'Duplicate User',
        'email': 'alpha@test.com',
        'password': 'Password123',
        'confirm_password': 'Password123',
        'state': 'Delhi',
        'gender': 'Male'
    }, follow_redirects=True)
    
    assert b"An account with this email address already exists" in resp.data

def test_login_valid_credentials(client, seed_users):
    """Test login with valid email and password."""
    resp = client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    assert b"Welcome back, Student Alpha!" in resp.data
    assert b"Candidate Dashboard" in resp.data

def test_login_invalid_password(client, seed_users):
    """Test login rejection on incorrect password."""
    resp = client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'WrongPassword999'
    }, follow_redirects=True)
    
    assert b"Invalid email or password" in resp.data

def test_deactivated_account_rejected(client, seed_users):
    """Test that deactivated accounts cannot log in."""
    db.execute("UPDATE users SET is_active = 0 WHERE email = 'alpha@test.com'")
    resp = client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    }, follow_redirects=True)
    
    assert b"This account has been deactivated" in resp.data

def test_logout_terminates_session(client, seed_users):
    """Test that logout terminates the authenticated session."""
    client.post('/auth/login', data={
        'email': 'alpha@test.com',
        'password': 'StudentPass123'
    })
    
    logout_resp = client.get('/auth/logout', follow_redirects=True)
    assert b"You have been signed out safely" in logout_resp.data
    
    # Attempt to access student dashboard after logout
    dash_resp = client.get('/student/dashboard', follow_redirects=True)
    assert b"Please sign in to access this page" in dash_resp.data
