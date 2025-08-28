from flask import Blueprint, request, jsonify, session, render_template, current_app
from app.database.db import get_db

logic_bp = Blueprint('logic', __name__)


def _require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


@logic_bp.route('/logic-01')
def lab16_page():
    return render_template('labs/logic_01.html')


@logic_bp.route('/logic-01/coupons')
def lab16_list_coupons():
    err = _require_login()
    if err:
        return err
    db = get_db()
    coupons = db.execute("SELECT id, code, discount_pct, max_uses, times_used FROM coupons").fetchall()
    db.close()
    return jsonify([dict(c) for c in coupons])


@logic_bp.route('/logic-01/apply-coupon', methods=['POST'])
def lab16_apply_coupon():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    code = data.get('code', '').strip()
    order_amount = data.get('order_amount', 0)

    if not code or not order_amount:
        return jsonify({'error': 'code and order_amount required'}), 400

    try:
        order_amount = float(order_amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid order_amount'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        cur = db.execute(
            "UPDATE coupons SET times_used = times_used + 1 "
            "WHERE code = ? AND times_used < max_uses",
            (code,)
        )
        db.commit()
        if cur.rowcount == 0:
            db.close()
            return jsonify({'error': 'Coupon invalid or fully redeemed'}), 400
        coupon = db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
        db.close()
        discount = order_amount * coupon['discount_pct'] / 100
        return jsonify({
            'status': 'applied',
            'code': code,
            'discount_pct': coupon['discount_pct'],
            'discount_amount': round(discount, 2),
            'final_amount': round(order_amount - discount, 2),
            'times_used': coupon['times_used'],
        })
    else:
        coupon = db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
        if not coupon:
            db.close()
            return jsonify({'error': 'Coupon not found'}), 404

        if coupon['times_used'] >= coupon['max_uses']:
            db.close()
            return jsonify({'error': 'Coupon fully redeemed'}), 400

        discount = order_amount * coupon['discount_pct'] / 100

        db.execute(
            "UPDATE coupons SET times_used = times_used + 1 WHERE id = ?",
            (coupon['id'],)
        )
        db.commit()
        updated = db.execute("SELECT times_used FROM coupons WHERE id = ?", (coupon['id'],)).fetchone()
        db.close()
        return jsonify({
            'status': 'applied',
            'code': code,
            'discount_pct': coupon['discount_pct'],
            'discount_amount': round(discount, 2),
            'final_amount': round(order_amount - discount, 2),
            'times_used': updated['times_used'],
        })


@logic_bp.route('/logic-01/reset', methods=['POST'])
def lab16_reset():
    db = get_db()
    db.execute("UPDATE coupons SET times_used = 0")
    db.commit()
    db.close()
    return jsonify({'status': 'reset'})


@logic_bp.route('/logic-02')
def lab17_page():
    return render_template('labs/logic_02.html')


@logic_bp.route('/logic-02/orders')
def lab17_list_orders():
    err = _require_login()
    if err:
        return err
    db = get_db()
    orders = db.execute("SELECT * FROM orders").fetchall()
    refunds = db.execute("SELECT * FROM refunds").fetchall()
    wallets = db.execute("SELECT * FROM wallets").fetchall()
    db.close()
    return jsonify({
        'orders': [dict(o) for o in orders],
        'refunds': [dict(r) for r in refunds],
        'wallets': [dict(w) for w in wallets],
    })


@logic_bp.route('/logic-02/refund', methods=['POST'])
def lab17_refund():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'error': 'order_id required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order or order['status'] != 'completed':
            db.rollback()
            db.close()
            return jsonify({'error': 'Order not eligible for refund'}), 400
        db.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
        db.execute(
            "INSERT INTO refunds (order_id, amount, status) VALUES (?, ?, 'processed')",
            (order_id, order['amount'])
        )
        db.execute(
            "UPDATE wallets SET balance = balance + ? WHERE user_id = ?",
            (order['amount'], order['user_id'])
        )
        db.commit()
        db.close()
        return jsonify({
            'status': 'refunded',
            'order_id': order_id,
            'amount': order['amount'],
        })
    else:
        order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            db.close()
            return jsonify({'error': 'Order not found'}), 404
        if order['status'] != 'completed':
            db.close()
            return jsonify({'error': 'Order not eligible for refund'}), 400

        db.execute(
            "INSERT INTO refunds (order_id, amount, status) VALUES (?, ?, 'processed')",
            (order_id, order['amount'])
        )
        db.execute(
            "UPDATE wallets SET balance = balance + ? WHERE user_id = ?",
            (order['amount'], order['user_id'])
        )
        db.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
        db.commit()
        db.close()
        return jsonify({
            'status': 'refunded',
            'order_id': order_id,
            'amount': order['amount'],
        })


@logic_bp.route('/logic-02/reset', methods=['POST'])
def lab17_reset():
    db = get_db()
    db.execute("DELETE FROM refunds")
    db.execute("UPDATE orders SET status = 'completed'")
    db.execute("UPDATE wallets SET balance = 100.00 WHERE user_id = 2")
    db.execute("UPDATE wallets SET balance = 50.00 WHERE user_id = 3")
    db.commit()
    db.close()
    return jsonify({'status': 'reset'})


@logic_bp.route('/logic-03')
def lab18_page():
    return render_template('labs/logic_03.html')


@logic_bp.route('/logic-03/seats')
def lab18_seats():
    err = _require_login()
    if err:
        return err
    db = get_db()
    seats = db.execute("SELECT * FROM team_seats").fetchall()
    invitations = db.execute("SELECT * FROM invitations").fetchall()
    db.close()
    return jsonify({
        'seats': [dict(s) for s in seats],
        'invitations': [dict(i) for i in invitations],
    })


@logic_bp.route('/logic-03/accept-invite', methods=['POST'])
def lab18_accept():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    invitation_id = data.get('invitation_id')
    if not invitation_id:
        return jsonify({'error': 'invitation_id required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    invitation = db.execute(
        "SELECT * FROM invitations WHERE id = ? AND accepted = 0",
        (invitation_id,)
    ).fetchone()
    if not invitation:
        db.close()
        return jsonify({'error': 'Invitation not found or already accepted'}), 404

    team_id = invitation['team_id']

    if patched:
        cur = db.execute(
            "UPDATE team_seats SET used_seats = used_seats + 1 "
            "WHERE team_id = ? AND used_seats < max_seats",
            (team_id,)
        )
        db.commit()
        if cur.rowcount == 0:
            db.close()
            return jsonify({'error': 'No seats available'}), 400
        db.execute(
            "UPDATE invitations SET accepted = 1 WHERE id = ?",
            (invitation_id,)
        )
        db.commit()
        db.close()
        return jsonify({'status': 'accepted', 'invitation_id': invitation_id})
    else:
        seats = db.execute(
            "SELECT * FROM team_seats WHERE team_id = ?", (team_id,)
        ).fetchone()
        if not seats:
            db.close()
            return jsonify({'error': 'Team not found'}), 404

        if seats['used_seats'] >= seats['max_seats']:
            db.close()
            return jsonify({'error': 'No seats available'}), 400

        db.execute(
            "UPDATE team_seats SET used_seats = used_seats + 1 WHERE team_id = ?",
            (team_id,)
        )
        db.execute(
            "UPDATE invitations SET accepted = 1 WHERE id = ?",
            (invitation_id,)
        )
        db.commit()
        db.close()
        return jsonify({'status': 'accepted', 'invitation_id': invitation_id})


@logic_bp.route('/logic-03/reset', methods=['POST'])
def lab18_reset():
    db = get_db()
    db.execute("DELETE FROM invitations")
    db.execute("UPDATE team_seats SET used_seats = 2 WHERE team_id = 1")
    db.execute("UPDATE team_seats SET used_seats = 2 WHERE team_id = 2")
    db.execute("INSERT INTO invitations (team_id, email, accepted) VALUES (1, 'inv-a@test.local', 0)")
    db.execute("INSERT INTO invitations (team_id, email, accepted) VALUES (1, 'inv-b@test.local', 0)")
    db.execute("INSERT INTO invitations (team_id, email, accepted) VALUES (1, 'inv-c@test.local', 0)")
    db.commit()
    db.close()
    return jsonify({'status': 'reset'})


@logic_bp.route('/logic-04')
def lab19_page():
    return render_template('labs/logic_04.html')


@logic_bp.route('/logic-04/tokens')
def lab19_tokens():
    err = _require_login()
    if err:
        return err
    db = get_db()
    tokens = db.execute(
        "SELECT * FROM verification_tokens WHERE user_id = ?",
        (session['user_id'],)
    ).fetchall()
    wallet = db.execute(
        "SELECT * FROM wallets WHERE user_id = ?",
        (session['user_id'],)
    ).fetchone()
    db.close()
    return jsonify({
        'tokens': [dict(t) for t in tokens],
        'wallet': dict(wallet) if wallet else None,
    })


@logic_bp.route('/logic-04/verify', methods=['POST'])
def lab19_verify():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    token = data.get('token', '').strip()
    if not token:
        return jsonify({'error': 'token required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        cur = db.execute(
            "UPDATE verification_tokens SET used = 1 WHERE token = ? AND used = 0",
            (token,)
        )
        db.commit()
        if cur.rowcount == 0:
            db.close()
            return jsonify({'error': 'Token invalid or already used'}), 400
        vt = db.execute(
            "SELECT user_id FROM verification_tokens WHERE token = ?", (token,)
        ).fetchone()
        db.execute(
            "UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?",
            (vt['user_id'],)
        )
        db.commit()
        wallet = db.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (vt['user_id'],)
        ).fetchone()
        db.close()
        return jsonify({
            'status': 'verified',
            'credit': 10.00,
            'new_balance': wallet['balance'],
        })
    else:
        vt = db.execute(
            "SELECT * FROM verification_tokens WHERE token = ? AND used = 0",
            (token,)
        ).fetchone()
        if not vt:
            db.close()
            return jsonify({'error': 'Token invalid or already used'}), 400

        db.execute(
            "UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?",
            (vt['user_id'],)
        )
        db.execute(
            "UPDATE verification_tokens SET used = 1 WHERE id = ?",
            (vt['id'],)
        )
        db.commit()
        wallet = db.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (vt['user_id'],)
        ).fetchone()
        db.close()
        return jsonify({
            'status': 'verified',
            'credit': 10.00,
            'new_balance': wallet['balance'],
        })


@logic_bp.route('/logic-04/reset', methods=['POST'])
def lab19_reset():
    db = get_db()
    db.execute("DELETE FROM verification_tokens")
    db.execute(
        "INSERT INTO verification_tokens (user_id, token, used) VALUES (2, 'VERIFY-TOKEN-ALICE-001', 0)"
    )
    db.execute("UPDATE wallets SET balance = 100.00 WHERE user_id = 2")
    db.commit()
    db.close()
    return jsonify({'status': 'reset'})


@logic_bp.route('/logic-05')
def lab20_page():
    return render_template('labs/logic_05.html')


@logic_bp.route('/logic-05/subscriptions')
def lab20_subscriptions():
    err = _require_login()
    if err:
        return err
    db = get_db()
    subs = db.execute("SELECT * FROM subscriptions").fetchall()
    db.close()
    return jsonify([dict(s) for s in subs])


@logic_bp.route('/logic-05/cancel', methods=['POST'])
def lab20_cancel():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    sub_id = data.get('subscription_id')
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    sub = db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
    if not sub:
        db.close()
        return jsonify({'error': 'Subscription not found'}), 404

    if patched:
        db.execute(
            "UPDATE subscriptions SET cancel_requested = 1, plan = 'free' WHERE id = ?",
            (sub_id,)
        )
        db.commit()
        db.close()
        return jsonify({'status': 'cancelled', 'subscription_id': sub_id})
    else:
        db.execute(
            "UPDATE subscriptions SET cancel_requested = 1 WHERE id = ?",
            (sub_id,)
        )
        db.commit()

        db.execute(
            "UPDATE subscriptions SET plan = 'free' WHERE id = ?",
            (sub_id,)
        )
        db.commit()
        db.close()
        return jsonify({'status': 'cancelled', 'subscription_id': sub_id})


@logic_bp.route('/logic-05/use-feature', methods=['POST'])
def lab20_use_feature():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    sub_id = data.get('subscription_id')
    if not sub_id:
        return jsonify({'error': 'subscription_id required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()
    sub = db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
    db.close()

    if not sub:
        return jsonify({'error': 'Subscription not found'}), 404

    if patched:
        if sub['plan'] != 'pro' or sub['cancel_requested'] == 1:
            return jsonify({'error': 'Premium feature not available'}), 403
    else:
        if sub['plan'] != 'pro':
            return jsonify({'error': 'Premium feature not available'}), 403

    return jsonify({
        'status': 'feature_used',
        'subscription_id': sub_id,
        'plan': sub['plan'],
        'feature': 'premium_export',
    })


@logic_bp.route('/logic-05/reset', methods=['POST'])
def lab20_reset():
    db = get_db()
    db.execute(
        "UPDATE subscriptions SET plan = 'pro', status = 'active', cancel_requested = 0 WHERE user_id = 2"
    )
    db.execute(
        "UPDATE subscriptions SET plan = 'free', status = 'active', cancel_requested = 0 WHERE user_id = 3"
    )
    db.commit()
    db.close()
    return jsonify({'status': 'reset'})
