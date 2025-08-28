import secrets

from flask import Blueprint, request, jsonify, session, render_template, current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.database.db import get_db

auth_bp = Blueprint('auth', __name__)


def _require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


@auth_bp.route('/auth-01')
def lab06_page():
    return render_template('labs/auth_01.html')


@auth_bp.route('/auth-01/login', methods=['POST'])
def lab06_primary_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user['password_hash'], password):
        db.close()
        return jsonify({'error': 'Invalid credentials'}), 401

    if user['mfa_enabled']:
        mfa_code = data.get('mfa_code', '')
        if mfa_code != '123456':
            db.close()
            return jsonify({
                'error': 'MFA verification required',
                'mfa_required': True,
            }), 403

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (user_id, session_token) VALUES (?, ?)",
        (user['id'], token),
    )
    db.commit()
    db.close()
    return jsonify({'token': token, 'username': user['username'], 'role': user['role']})


@auth_bp.route('/auth-01/api/v1/login', methods=['POST'])
def lab06_legacy_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    patched = current_app.config.get('PATCHED_MODE', False)

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user['password_hash'], password):
        db.close()
        return jsonify({'error': 'Invalid credentials'}), 401

    if patched and user['mfa_enabled']:
        mfa_code = data.get('mfa_code', '')
        if mfa_code != '123456':
            db.close()
            return jsonify({
                'error': 'MFA verification required',
                'mfa_required': True,
            }), 403

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (user_id, session_token) VALUES (?, ?)",
        (user['id'], token),
    )
    db.commit()
    db.close()
    return jsonify({'token': token, 'username': user['username'], 'role': user['role']})


@auth_bp.route('/auth-01/profile')
def lab06_profile():
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    db = get_db()
    row = db.execute(
        "SELECT s.user_id, u.username, u.email, u.role FROM sessions s "
        "JOIN users u ON s.user_id = u.id WHERE s.session_token = ? AND s.revoked = 0",
        (token,),
    ).fetchone()
    db.close()
    if not row:
        return jsonify({'error': 'Invalid or revoked token'}), 401
    return jsonify(dict(row))


@auth_bp.route('/auth-02')
def lab07_page():
    return render_template('labs/auth_02.html')


@auth_bp.route('/auth-02/request-reset', methods=['POST'])
def lab07_request_reset():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        db.close()
        return jsonify({'error': 'User not found'}), 404

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO password_reset_tokens (user_id, token) VALUES (?, ?)",
        (user['id'], token),
    )
    db.commit()
    db.close()
    return jsonify({'reset_token': token, 'message': 'Reset token generated (normally sent via email)'})


@auth_bp.route('/auth-02/reset', methods=['POST'])
def lab07_reset_password():
    data = request.get_json(silent=True) or request.form
    token = (data.get('token') or '').strip()
    new_password = data.get('new_password', '')

    if not token or not new_password:
        return jsonify({'error': 'Token and new_password are required'}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0",
        (token,),
    ).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Invalid or already-used token'}), 400

    new_hash = generate_password_hash(new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row['user_id']))
    db.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (row['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'Password reset successful'})


@auth_bp.route('/auth-02/change-password', methods=['POST'])
def lab07_change_password():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or request.form
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    patched = current_app.config.get('PATCHED_MODE', False)

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not check_password_hash(user['password_hash'], current_password):
        db.close()
        return jsonify({'error': 'Current password incorrect'}), 403

    new_hash = generate_password_hash(new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user['id']))

    if patched:
        db.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
            (user['id'],),
        )

    db.commit()
    db.close()
    return jsonify({'message': 'Password changed successfully'})


@auth_bp.route('/auth-03')
def lab08_page():
    return render_template('labs/auth_03.html')


@auth_bp.route('/auth-03/login', methods=['POST'])
def lab08_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], password):
        db.close()
        return jsonify({'error': 'Invalid credentials'}), 401

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (user_id, session_token) VALUES (?, ?)",
        (user['id'], token),
    )
    db.commit()
    db.close()
    return jsonify({'session_token': token, 'user_id': user['id'], 'username': user['username']})


@auth_bp.route('/auth-03/change-password', methods=['POST'])
def lab08_change_password():
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    db = get_db()
    sess = db.execute(
        "SELECT * FROM sessions WHERE session_token = ? AND revoked = 0", (token,)
    ).fetchone()
    if not sess:
        db.close()
        return jsonify({'error': 'Invalid or revoked session'}), 401

    data = request.get_json(silent=True) or request.form
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    user = db.execute("SELECT * FROM users WHERE id = ?", (sess['user_id'],)).fetchone()
    if not check_password_hash(user['password_hash'], current_password):
        db.close()
        return jsonify({'error': 'Current password incorrect'}), 403

    patched = current_app.config.get('PATCHED_MODE', False)

    new_hash = generate_password_hash(new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user['id']))

    if patched:
        db.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ? AND session_token != ?",
            (user['id'], token),
        )

    db.commit()
    db.close()
    return jsonify({'message': 'Password changed'})


@auth_bp.route('/auth-03/profile')
def lab08_profile():
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    db = get_db()
    row = db.execute(
        "SELECT s.user_id, u.username, u.email, u.role FROM sessions s "
        "JOIN users u ON s.user_id = u.id WHERE s.session_token = ? AND s.revoked = 0",
        (token,),
    ).fetchone()
    db.close()
    if not row:
        return jsonify({'error': 'Invalid or revoked session'}), 401
    return jsonify(dict(row))


@auth_bp.route('/auth-04')
def lab09_page():
    return render_template('labs/auth_04.html')


@auth_bp.route('/auth-04/send-otp', methods=['POST'])
def lab09_send_otp():
    err = _require_login()
    if err:
        return err

    otp = f"{secrets.randbelow(1000000):06d}"
    db = get_db()
    db.execute(
        "INSERT INTO verification_tokens (user_id, token, used) VALUES (?, ?, 0)",
        (session['user_id'], otp),
    )
    db.commit()
    db.close()
    return jsonify({'message': 'OTP sent (simulated)', 'otp': otp})


@auth_bp.route('/auth-04/verify-otp', methods=['POST'])
def lab09_verify_otp():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or request.form
    otp_code = (data.get('otp_code') or '').strip()
    patched = current_app.config.get('PATCHED_MODE', False)

    db = get_db()
    row = db.execute(
        "SELECT * FROM verification_tokens WHERE user_id = ? AND token = ? AND used = 0",
        (session['user_id'], otp_code),
    ).fetchone()

    if not row:
        db.close()
        return jsonify({'error': 'Invalid or already-used OTP'}), 400

    if patched:
        db.execute("UPDATE verification_tokens SET used = 1 WHERE id = ?", (row['id'],))
        db.commit()

    db.close()
    return jsonify({'message': 'OTP verified successfully', 'verified': True})


@auth_bp.route('/auth-05')
def lab10_page():
    return render_template('labs/auth_05.html')


@auth_bp.route('/auth-05/oauth/authorize', methods=['POST'])
def lab10_oauth_authorize():
    err = _require_login()
    if err:
        return err

    state = secrets.token_urlsafe(32)
    patched = current_app.config.get('PATCHED_MODE', False)

    db = get_db()
    if patched:
        db.execute(
            "INSERT INTO oauth_states (state_token, user_id, provider) VALUES (?, ?, ?)",
            (state, session['user_id'], 'example-provider'),
        )
    else:
        db.execute(
            "INSERT INTO oauth_states (state_token, provider) VALUES (?, ?)",
            (state, 'example-provider'),
        )
    db.commit()
    db.close()

    redirect_url = f"/lab/auth/auth-05/oauth/callback?code=simulated_auth_code&state={state}"
    return jsonify({
        'state': state,
        'authorization_url': redirect_url,
        'message': 'Redirect user to authorization URL',
    })


@auth_bp.route('/auth-05/oauth/callback')
def lab10_oauth_callback():
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    patched = current_app.config.get('PATCHED_MODE', False)

    if not state or not code:
        return jsonify({'error': 'Missing state or code parameter'}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM oauth_states WHERE state_token = ? AND used = 0",
        (state,),
    ).fetchone()

    if not row:
        db.close()
        return jsonify({'error': 'Invalid or replayed state token'}), 400

    if patched:
        if 'user_id' not in session or row['user_id'] != session['user_id']:
            db.close()
            return jsonify({'error': 'State token does not belong to current session'}), 403

    db.execute("UPDATE oauth_states SET used = 1 WHERE id = ?", (row['id'],))

    linked_user_id = row['user_id'] or (session.get('user_id'))
    token = secrets.token_urlsafe(32)
    if linked_user_id:
        db.execute(
            "INSERT INTO sessions (user_id, session_token) VALUES (?, ?)",
            (linked_user_id, token),
        )

    db.commit()

    user = None
    if linked_user_id:
        user = db.execute("SELECT username, email, role FROM users WHERE id = ?", (linked_user_id,)).fetchone()
    db.close()

    return jsonify({
        'message': 'OAuth flow completed — account linked',
        'session_token': token,
        'user': dict(user) if user else None,
    })
