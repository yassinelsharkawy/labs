from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from werkzeug.security import check_password_hash
from app.database.db import get_db, reset_db

main_bp = Blueprint('main', __name__)

LABS = [
    {'id': 1, 'class': 1, 'slug': 'bac-01', 'title': 'Cross-Tenant Invoice Access',
     'category': 'Broken Access Control', 'prefix': 'bac'},
    {'id': 2, 'class': 1, 'slug': 'bac-02', 'title': 'Unauthorized Document Deletion via API',
     'category': 'Broken Access Control', 'prefix': 'bac'},
    {'id': 3, 'class': 1, 'slug': 'bac-03', 'title': 'Export Endpoint Authorization Bypass',
     'category': 'Broken Access Control', 'prefix': 'bac'},
    {'id': 4, 'class': 1, 'slug': 'bac-04', 'title': 'Privilege Escalation via Bulk Role Assignment',
     'category': 'Broken Access Control', 'prefix': 'bac'},
    {'id': 5, 'class': 1, 'slug': 'bac-05', 'title': 'Stale Membership Resource Access',
     'category': 'Broken Access Control', 'prefix': 'bac'},

    {'id': 6, 'class': 2, 'slug': 'auth-01', 'title': 'MFA Bypass via Legacy API',
     'category': 'Authentication & Sessions', 'prefix': 'auth'},
    {'id': 7, 'class': 2, 'slug': 'auth-02', 'title': 'Password Reset Token Reuse After Change',
     'category': 'Authentication & Sessions', 'prefix': 'auth'},
    {'id': 8, 'class': 2, 'slug': 'auth-03', 'title': 'Session Persistence After Password Change',
     'category': 'Authentication & Sessions', 'prefix': 'auth'},
    {'id': 9, 'class': 2, 'slug': 'auth-04', 'title': 'OTP Replay and Non-Consumption',
     'category': 'Authentication & Sessions', 'prefix': 'auth'},
    {'id': 10, 'class': 2, 'slug': 'auth-05', 'title': 'OAuth State Parameter Fixation',
     'category': 'Authentication & Sessions', 'prefix': 'auth'},

    {'id': 11, 'class': 3, 'slug': 'inj-01', 'title': 'Stored XSS in User Comments Rendered in Admin Panel',
     'category': 'Injection', 'prefix': 'injection'},
    {'id': 12, 'class': 3, 'slug': 'inj-02', 'title': 'Reflected XSS via Search Redirect Parameter',
     'category': 'Injection', 'prefix': 'injection'},
    {'id': 13, 'class': 3, 'slug': 'inj-03', 'title': 'Stored XSS via Wiki Page Markup',
     'category': 'Injection', 'prefix': 'injection'},
    {'id': 14, 'class': 3, 'slug': 'inj-04', 'title': 'SQL Injection in Product Search Filter',
     'category': 'Injection', 'prefix': 'injection'},
    {'id': 15, 'class': 3, 'slug': 'inj-05', 'title': 'Blind SQL Injection in Audit Log Query',
     'category': 'Injection', 'prefix': 'injection'},

    {'id': 16, 'class': 4, 'slug': 'logic-01', 'title': 'Coupon Code Multiple Redemption',
     'category': 'Business Logic & Race Conditions', 'prefix': 'logic'},
    {'id': 17, 'class': 4, 'slug': 'logic-02', 'title': 'Concurrent Duplicate Refund Processing',
     'category': 'Business Logic & Race Conditions', 'prefix': 'logic'},
    {'id': 18, 'class': 4, 'slug': 'logic-03', 'title': 'Invitation Acceptance Exceeding Seat Limit',
     'category': 'Business Logic & Race Conditions', 'prefix': 'logic'},
    {'id': 19, 'class': 4, 'slug': 'logic-04', 'title': 'Parallel Verification Token Consumption',
     'category': 'Business Logic & Race Conditions', 'prefix': 'logic'},
    {'id': 20, 'class': 4, 'slug': 'logic-05', 'title': 'Subscription Downgrade State Inconsistency',
     'category': 'Business Logic & Race Conditions', 'prefix': 'logic'},

    {'id': 21, 'class': 5, 'slug': 'ssrf-01', 'title': 'Image Importer SSRF to Internal Metadata',
     'category': 'SSRF', 'prefix': 'ssrf'},
    {'id': 22, 'class': 5, 'slug': 'ssrf-02', 'title': 'Webhook Tester SSRF to Internal Services',
     'category': 'SSRF', 'prefix': 'ssrf'},
    {'id': 23, 'class': 5, 'slug': 'ssrf-03', 'title': 'Report Generator SSRF via Document URL',
     'category': 'SSRF', 'prefix': 'ssrf'},
    {'id': 24, 'class': 5, 'slug': 'ssrf-04', 'title': 'SSRF via Redirect Bypass of URL Allowlist',
     'category': 'SSRF', 'prefix': 'ssrf'},
    {'id': 25, 'class': 5, 'slug': 'ssrf-05', 'title': 'SSRF via URL Parsing Inconsistency',
     'category': 'SSRF', 'prefix': 'ssrf'},
]

CLASSES = [
    {'id': 1, 'name': 'Broken Access Control & IDOR', 'labs': [l for l in LABS if l['class'] == 1]},
    {'id': 2, 'name': 'Authentication, Sessions & MFA', 'labs': [l for l in LABS if l['class'] == 2]},
    {'id': 3, 'name': 'Injection (XSS & SQLi)', 'labs': [l for l in LABS if l['class'] == 3]},
    {'id': 4, 'name': 'Business Logic & Race Conditions', 'labs': [l for l in LABS if l['class'] == 4]},
    {'id': 5, 'name': 'Server-Side Request Forgery', 'labs': [l for l in LABS if l['class'] == 5]},
]


@main_bp.route('/')
def index():
    return render_template('index.html', classes=CLASSES, labs=LABS)


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['tenant_id'] = user['tenant_id']
            session['mfa_enabled'] = bool(user['mfa_enabled'])
            session['mfa_verified'] = False
            return redirect(url_for('main.index'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')


@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@main_bp.route('/reset', methods=['POST'])
def reset():
    reset_db()
    session.clear()
    flash('Lab environment has been reset to initial state.', 'info')
    return redirect(url_for('main.index'))


@main_bp.route('/accounts')
def accounts():
    return render_template('accounts.html')
