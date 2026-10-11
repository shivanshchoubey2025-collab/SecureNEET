import os
import secrets

class Config:
    """SecureNEET Application Configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    
    # Database Configuration (MySQL as primary)
    DB_TYPE = os.environ.get("DB_TYPE", "mysql").lower()
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "secureneet")
    
    # SQLite local path (used when DB_TYPE=sqlite or fallback)
    SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "secureneet.db"))
    
    # Session Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME_SECONDS", 7200)) # 2 hours
    
    # Examination Rules & Limits
    EXAM_GRACE_PERIOD_SECONDS = int(os.environ.get("EXAM_GRACE_PERIOD_SECONDS", 30))
    MAX_ATTEMPTS_PER_EXAM = int(os.environ.get("MAX_ATTEMPTS_PER_EXAM", 1))
    
    # Application Info
    APP_NAME = "SecureNEET"
    APP_VERSION = "1.0.0"
