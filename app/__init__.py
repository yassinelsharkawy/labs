import os
from flask import Flask


def create_app(config=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY', 'lab-secret-key-not-for-production')

    app.config['SESSION_COOKIE_HTTPONLY'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PATCHED_MODE'] = os.environ.get('PATCHED_MODE', '0') == '1'

    if config:
        app.config.update(config)

    from app.database.db import init_db
    with app.app_context():
        init_db()

    from app.routes.main import main_bp
    from app.routes.bac import bac_bp
    from app.routes.auth_labs import auth_bp
    from app.routes.injection import injection_bp
    from app.routes.logic import logic_bp
    from app.routes.ssrf import ssrf_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(bac_bp, url_prefix='/lab/bac')
    app.register_blueprint(auth_bp, url_prefix='/lab/auth')
    app.register_blueprint(injection_bp, url_prefix='/lab/injection')
    app.register_blueprint(logic_bp, url_prefix='/lab/logic')
    app.register_blueprint(ssrf_bp, url_prefix='/lab/ssrf')

    return app
