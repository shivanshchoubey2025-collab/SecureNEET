"""SecureNEET — Production Application Entrypoint and Factory."""

from datetime import datetime
from flask import Flask, render_template, jsonify
from config import Config
import db
from auth import get_current_user

def create_app(config_class=Config):
    """Application factory for SecureNEET."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Database Schema if needed
    with app.app_context():
        try:
            db.init_db()
        except Exception as e:
            app.logger.warning(f"Database initialization deferred or already created: {e}")

    # Register Blueprints
    from routes.public import public_bp
    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.exam import exam_bp
    from routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(exam_bp, url_prefix='/exam')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Global Context Processor
    @app.context_processor
    def inject_globals():
        return {
            'current_user': get_current_user(),
            'app_name': Config.APP_NAME,
            'app_version': Config.APP_VERSION,
            'current_year': datetime.now().year
        }

    # Security Headers Middleware
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Health Check Endpoint
    @app.route('/health')
    def health_check():
        db_mode = db.determine_db_mode()
        return jsonify({
            'status': 'healthy',
            'app': Config.APP_NAME,
            'version': Config.APP_VERSION,
            'db_mode': db_mode
        }), 200

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
