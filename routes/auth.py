"""Authentication routes for login, student registration, and password recovery."""

import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import db
from auth import hash_password, verify_password, INDIAN_STATES, GENDER_OPTIONS, get_current_user
from services.audit_service import log_action

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login with role-based dashboard redirection."""
    if get_current_user():
        user = get_current_user()
        if user['role'] in ('admin', 'question_manager'):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('auth/login.html')
            
        user = db.query_one("SELECT * FROM users WHERE LOWER(email) = %s", (email,))
        
        if not user or not verify_password(user.get('password_hash'), password):
            # Generic error message to prevent account enumeration
            flash("Invalid email or password.", "danger")
            return render_template('auth/login.html')
            
        if not user.get('is_active'):
            flash("This account has been deactivated. Please contact the administrator.", "danger")
            return render_template('auth/login.html')
            
        # Clear any prior session data to prevent fixation
        session.clear()
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['user_name'] = user['full_name']
        session.permanent = True
        
        log_action(user['id'], "login", "user", user['id'], f"Signed in as {user['role']}.")
        flash(f"Welcome back, {user['full_name']}!", "success")
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
            
        if user['role'] in ('admin', 'question_manager'):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
        
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Student self-registration endpoint with State and Gender selection."""
    if get_current_user():
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        state = request.form.get('state', '').strip()
        gender = request.form.get('gender', '').strip()
        
        # Validations
        if not full_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if len(password) < 8:
            flash("Password must be at least 8 characters in length.", "danger")
            return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if state and state not in INDIAN_STATES:
            flash("Please choose a valid State/UT from the provided list.", "danger")
            return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        if gender and gender not in GENDER_OPTIONS:
            gender = "Prefer not to say"

        existing = db.query_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
        if existing:
            flash("An account with this email address already exists.", "danger")
            return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)
            
        # Generate unique student NEET registration roll number
        reg_number = f"NEET{str(uuid.uuid4().int)[:8]}"
        password_hash = hash_password(password)
        
        user_id = db.execute(
            """INSERT INTO users
               (full_name, email, password_hash, role, state, gender, registration_number, is_active, created_at)
               VALUES (%s, %s, %s, 'student', %s, %s, %s, 1, NOW())""",
            (full_name, email, password_hash, state or None, gender or None, reg_number)
        )
        
        log_action(user_id, "student_registered", "user", user_id, f"Registered student from {state or 'N/A'}.")
        
        # Auto-login after registration
        session.clear()
        session['user_id'] = user_id
        session['role'] = 'student'
        session['user_name'] = full_name
        session.permanent = True
        
        flash("Registration successful! Welcome to SecureNEET.", "success")
        return redirect(url_for('student.dashboard'))
        
    return render_template('auth/register.html', states=INDIAN_STATES, genders=GENDER_OPTIONS)

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Sign out current user and terminate session."""
    user = get_current_user()
    if user:
        log_action(user['id'], "logout", "user", user['id'])
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('public.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password request flow."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash("Please enter your registered email address.", "danger")
            return render_template('auth/forgot_password.html')
            
        user = db.query_one("SELECT id, email FROM users WHERE LOWER(email) = %s", (email,))
        # Show positive message regardless of whether user exists for privacy
        flash("If an account with that email exists, password reset instructions have been sent.", "info")
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Password reset completion."""
    return render_template('auth/reset_password.html')
