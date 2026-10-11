"""Authentication and authorization utilities for SecureNEET."""

from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
import db

# Standard Indian States and Union Territories for NEET State Topper classification
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]

GENDER_OPTIONS = [
    "Male",
    "Female",
    "Other",
    "Prefer not to say"
]

def hash_password(password: str) -> str:
    """Generate secure password hash using PBKDF2."""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(stored_hash: str, password: str) -> bool:
    """Verify plaintext password against stored hash."""
    if not stored_hash or not password:
        return False
    return check_password_hash(stored_hash, password)

def get_current_user():
    """Retrieve currently authenticated user from session, cached on Flask 'g'."""
    if hasattr(g, '_current_user'):
        return g._current_user
    
    user_id = session.get('user_id')
    if not user_id:
        g._current_user = None
        return None
    
    user = db.query_one(
        "SELECT id, full_name, email, role, state, gender, registration_number, is_active FROM users WHERE id = %s",
        (user_id,)
    )
    if not user or not user.get('is_active'):
        session.clear()
        g._current_user = None
        return None
        
    g._current_user = user
    return user

def login_required(f):
    """Decorator requiring an active authenticated session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorator requiring the authenticated user to hold one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.path))
            
            user_role = user.get('role')
            if user_role not in allowed_roles:
                flash("Access denied. You lack the required permissions for this action.", "danger")
                if user_role == 'student':
                    return redirect(url_for('student.dashboard'))
                elif user_role in ('admin', 'question_manager'):
                    return redirect(url_for('admin.dashboard'))
                return redirect(url_for('public.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
