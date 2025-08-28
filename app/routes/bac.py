from flask import Blueprint, request, jsonify, session, render_template, current_app
from app.database.db import get_db

bac_bp = Blueprint('bac', __name__)


def _require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


@bac_bp.route('/bac-01')
def lab01_page():
    return render_template('labs/bac_01.html')


@bac_bp.route('/bac-01/invoices')
def lab01_list_invoices():
    err = _require_login()
    if err:
        return err
    db = get_db()
    tenant_id = session['tenant_id']
    invoices = db.execute("SELECT * FROM invoices WHERE tenant_id = ?", (tenant_id,)).fetchall()
    db.close()
    return jsonify([dict(i) for i in invoices])


@bac_bp.route('/bac-01/invoices/<int:invoice_id>')
def lab01_get_invoice(invoice_id):
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND tenant_id = ?",
            (invoice_id, session['tenant_id'])
        ).fetchone()
    else:
        invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()

    db.close()
    if not invoice:
        return jsonify({'error': 'Invoice not found'}), 404
    return jsonify(dict(invoice))


@bac_bp.route('/bac-02')
def lab02_page():
    return render_template('labs/bac_02.html')


@bac_bp.route('/bac-02/documents')
def lab02_list_documents():
    err = _require_login()
    if err:
        return err
    db = get_db()
    uid = str(session['user_id'])
    docs = db.execute(
        "SELECT id, title, owner_id, shared_with FROM documents WHERE deleted = 0 AND (owner_id = ? OR shared_with LIKE ?)",
        (session['user_id'], f'%{uid}%')
    ).fetchall()
    db.close()
    return jsonify([dict(d) for d in docs])


@bac_bp.route('/bac-02/documents/<int:doc_id>', methods=['DELETE'])
def lab02_delete_document(doc_id):
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        result = db.execute(
            "UPDATE documents SET deleted = 1 WHERE id = ? AND owner_id = ?",
            (doc_id, session['user_id'])
        )
    else:
        result = db.execute("UPDATE documents SET deleted = 1 WHERE id = ?", (doc_id,))

    db.commit()
    affected = result.rowcount
    db.close()
    if affected == 0:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify({'status': 'deleted', 'document_id': doc_id})


@bac_bp.route('/bac-03')
def lab03_page():
    return render_template('labs/bac_03.html')


@bac_bp.route('/bac-03/exports')
def lab03_list_exports():
    err = _require_login()
    if err:
        return err
    db = get_db()
    exports = db.execute(
        "SELECT id, file_name, status FROM export_jobs WHERE tenant_id = ?",
        (session['tenant_id'],)
    ).fetchall()
    db.close()
    return jsonify([dict(e) for e in exports])


@bac_bp.route('/bac-03/exports/<int:export_id>/download')
def lab03_download_export(export_id):
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        export = db.execute(
            "SELECT * FROM export_jobs WHERE id = ? AND tenant_id = ?",
            (export_id, session['tenant_id'])
        ).fetchone()
    else:
        export = db.execute("SELECT * FROM export_jobs WHERE id = ?", (export_id,)).fetchone()

    db.close()
    if not export:
        return jsonify({'error': 'Export not found'}), 404
    return jsonify({'file_name': export['file_name'], 'data': export['data']})


@bac_bp.route('/bac-04')
def lab04_page():
    return render_template('labs/bac_04.html')


@bac_bp.route('/bac-04/roles')
def lab04_list_roles():
    err = _require_login()
    if err:
        return err
    db = get_db()
    roles = db.execute(
        "SELECT r.*, u.username FROM roles r JOIN users u ON r.user_id = u.id WHERE r.tenant_id = ?",
        (session['tenant_id'],)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in roles])


@bac_bp.route('/bac-04/roles/bulk-update', methods=['POST'])
def lab04_bulk_update_roles():
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)

    if patched:
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403

    data = request.get_json()
    if not data or 'updates' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    db = get_db()
    updated = []
    for update in data['updates']:
        user_id = update.get('user_id')
        new_role = update.get('role_name')
        new_perms = update.get('permissions', '')
        if user_id and new_role:
            existing = db.execute(
                "SELECT id FROM roles WHERE user_id = ? AND tenant_id = ?",
                (user_id, session['tenant_id'])
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE roles SET role_name = ?, permissions = ? WHERE id = ?",
                    (new_role, new_perms, existing['id'])
                )
            else:
                db.execute(
                    "INSERT INTO roles (tenant_id, user_id, role_name, permissions) VALUES (?, ?, ?, ?)",
                    (session['tenant_id'], user_id, new_role, new_perms)
                )
            updated.append(user_id)
    db.commit()
    db.close()
    return jsonify({'status': 'updated', 'users': updated})


@bac_bp.route('/bac-05')
def lab05_page():
    return render_template('labs/bac_05.html')


@bac_bp.route('/bac-05/team/<int:team_id>/documents')
def lab05_team_documents(team_id):
    err = _require_login()
    if err:
        return err
    patched = current_app.config.get('PATCHED_MODE', False)
    db = get_db()

    if patched:
        membership = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ? AND active = 1",
            (team_id, session['user_id'])
        ).fetchone()
        if not membership:
            db.close()
            return jsonify({'error': 'Access denied — not an active member'}), 403
    else:
        membership = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, session['user_id'])
        ).fetchone()
        if not membership:
            db.close()
            return jsonify({'error': 'Not a team member'}), 403

    docs = db.execute(
        "SELECT d.id, d.title, d.content FROM documents d JOIN users u ON d.owner_id = u.id "
        "JOIN team_members tm ON tm.user_id = u.id AND tm.team_id = ? WHERE d.deleted = 0",
        (team_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(d) for d in docs])
