import re

from flask import (
    Blueprint, request, jsonify, session, render_template, current_app,
)
from markupsafe import Markup, escape as html_escape

from app.database.db import get_db

injection_bp = Blueprint('injection', __name__)


def _require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


@injection_bp.route('/inj-01')
def lab11_page():
    return render_template('labs/inj_01.html')


@injection_bp.route('/inj-01/comments', methods=['GET'])
def lab11_list_comments():
    err = _require_login()
    if err:
        return err
    db = get_db()
    rows = db.execute(
        "SELECT c.id, c.body, c.created_at, u.username "
        "FROM comments c JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC"
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@injection_bp.route('/inj-01/comments', methods=['POST'])
def lab11_create_comment():
    err = _require_login()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()
    if not body:
        return jsonify({'error': 'Comment body is required'}), 400
    db = get_db()
    db.execute(
        "INSERT INTO comments (user_id, target_type, target_id, body) VALUES (?, 'post', 0, ?)",
        (session['user_id'], body),
    )
    db.commit()
    db.close()
    return jsonify({'status': 'created'}), 201


@injection_bp.route('/inj-01/admin-view')
def lab11_admin_view():
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()
    rows = db.execute(
        "SELECT c.id, c.body, c.created_at, u.username "
        "FROM comments c JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC"
    ).fetchall()
    db.close()

    comments = []
    for r in rows:
        d = dict(r)
        if patched:
            d['body_html'] = str(html_escape(d['body']))
        else:
            d['body_html'] = d['body']
        comments.append(d)

    return render_template('labs/inj_01_admin.html', comments=comments)


@injection_bp.route('/inj-02')
def lab12_page():
    return render_template('labs/inj_02.html')


@injection_bp.route('/inj-02/search')
def lab12_search():
    err = _require_login()
    if err:
        return err
    q = request.args.get('q', '')
    redirect_to = request.args.get('redirect_to', '')
    patched = current_app.config.get('PATCHED_MODE', False)

    db = get_db()
    products = db.execute(
        "SELECT id, name, category, price FROM products WHERE name LIKE ?",
        (f'%{q}%',),
    ).fetchall()
    db.close()

    if patched:
        if redirect_to and not redirect_to.startswith('/'):
            redirect_to = ''

    return render_template(
        'labs/inj_02_search.html',
        q=q,
        redirect_to=redirect_to,
        products=[dict(p) for p in products],
    )


@injection_bp.route('/inj-03')
def lab13_page():
    return render_template('labs/inj_03.html')


@injection_bp.route('/inj-03/wiki/<slug>')
def lab13_wiki_view(slug):
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()
    page = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    db.close()
    if not page:
        return jsonify({'error': 'Page not found'}), 404

    page_dict = dict(page)
    if patched:
        body = page_dict['body']
        body = re.sub(r'<\s*script[^>]*>.*?</\s*script\s*>', '', body, flags=re.I | re.S)
        body = re.sub(r'\bon\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', '', body, flags=re.I)
        page_dict['body_html'] = str(html_escape(body))
    else:
        page_dict['body_html'] = page_dict['body']

    return render_template('labs/inj_03_wiki.html', page=page_dict)


@injection_bp.route('/inj-03/wiki/<slug>/edit', methods=['POST'])
def lab13_wiki_edit(slug):
    err = _require_login()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    body = data.get('body', '')
    db = get_db()
    result = db.execute("UPDATE wiki_pages SET body = ? WHERE slug = ?", (body, slug))
    db.commit()
    db.close()
    if result.rowcount == 0:
        return jsonify({'error': 'Page not found'}), 404
    return jsonify({'status': 'updated'})


@injection_bp.route('/inj-04')
def lab14_page():
    return render_template('labs/inj_04.html')


@injection_bp.route('/inj-04/products/search')
def lab14_product_search():
    err = _require_login()
    if err:
        return err
    category = request.args.get('category', '')
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        rows = db.execute(
            "SELECT id, name, category, description, price, stock FROM products WHERE category = ?",
            (category,),
        ).fetchall()
    else:
        query = f"SELECT id, name, category, description, price, stock FROM products WHERE category = '{category}'"
        try:
            rows = db.execute(query).fetchall()
        except Exception:
            rows = []

    db.close()
    return jsonify([dict(r) for r in rows])


@injection_bp.route('/inj-05')
def lab15_page():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    if count == 0:
        seed = [
            (1, 'login', 'admin logged in'),
            (2, 'view_invoice', 'alice viewed INV-1001'),
            (3, 'edit_document', 'bob edited Meeting Notes'),
            (1, 'export', 'admin exported user list'),
            (2, 'login', 'alice logged in'),
        ]
        db.executemany(
            "INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)",
            seed,
        )
        db.commit()
    db.close()
    return render_template('labs/inj_05.html')


@injection_bp.route('/inj-05/audit')
def lab15_audit_search():
    err = _require_login()
    if err:
        return err
    username = request.args.get('username', '')
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        rows = db.execute(
            "SELECT a.id, a.action, a.detail, a.created_at "
            "FROM audit_log a WHERE a.user_id = (SELECT id FROM users WHERE username = ?) "
            "ORDER BY a.created_at DESC",
            (username,),
        ).fetchall()
    else:
        query = (
            "SELECT a.id, a.action, a.detail, a.created_at "
            "FROM audit_log a WHERE a.user_id = "
            f"(SELECT id FROM users WHERE username = '{username}') "
            "ORDER BY a.created_at DESC"
        )
        try:
            rows = db.execute(query).fetchall()
        except Exception:
            rows = []

    db.close()
    return jsonify([dict(r) for r in rows])
