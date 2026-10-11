"""Audit logging service for security tracking and compliance."""

from flask import request
import db

def log_action(user_id, action, target_type=None, target_id=None, details=None):
    """Record an action in the audit logs."""
    ip_address = None
    try:
        if request:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
    except Exception:
        ip_address = "system"
        
    try:
        db.execute(
            """INSERT INTO audit_logs (user_id, action, target_type, target_id, ip_address, details, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
            (user_id, action, target_type, target_id, ip_address, details)
        )
    except Exception as e:
        # Never break core app flow if an audit log insert encounters an issue
        print(f"Warning: Audit log insertion failed: {e}")
