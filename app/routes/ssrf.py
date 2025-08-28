from flask import Blueprint, request, jsonify, session, render_template, current_app, redirect
from app.database.db import get_db
import requests as http_requests
import os
import socket
import ipaddress
from urllib.parse import urlparse

ssrf_bp = Blueprint('ssrf', __name__)

INTERNAL_SERVICE_URL = os.environ.get('INTERNAL_SERVICE_URL', 'http://mock-internal:5001')

BLOCKED_HOSTNAMES = {'mock-internal', 'localhost', '127.0.0.1', '0.0.0.0', 'metadata.internal', 'internal'}


def _require_login():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


def _is_private_ip(ip_str):
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local
    except ValueError:
        return False


def _is_url_safe(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False, 'Invalid URL'

    if parsed.scheme not in ('http', 'https'):
        return False, f'Blocked scheme: {parsed.scheme}'

    hostname = parsed.hostname
    if not hostname:
        return False, 'No hostname'

    if hostname in BLOCKED_HOSTNAMES:
        return False, f'Blocked hostname: {hostname}'

    try:
        results = socket.getaddrinfo(hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
        for family, type_, proto, canonname, sockaddr in results:
            ip = sockaddr[0]
            if _is_private_ip(ip):
                return False, f'Hostname resolves to private IP: {ip}'
    except socket.gaierror:
        return False, f'Cannot resolve hostname: {hostname}'

    return True, 'ok'


def _naive_hostname_check(url):
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        if hostname in BLOCKED_HOSTNAMES:
            return False
        if hostname.startswith('10.') or hostname.startswith('192.168.') or hostname.startswith('172.'):
            return False
        return True
    except Exception:
        return False


def _naive_at_sign_check(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False, 'Blocked scheme'
        netloc = parsed.netloc
        if '@' in netloc:
            host_part = netloc.split('@')[0]
        else:
            host_part = netloc
        hostname = host_part.split(':')[0]
        if hostname in BLOCKED_HOSTNAMES:
            return False, f'Blocked hostname: {hostname}'
        if _is_private_ip(hostname):
            return False, f'Blocked private IP: {hostname}'
        return True, 'ok'
    except Exception:
        return False, 'Parse error'


@ssrf_bp.route('/ssrf-01')
def lab21_page():
    return render_template('labs/ssrf_01.html')


@ssrf_bp.route('/ssrf-01/import-image', methods=['POST'])
def lab21_import_image():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    if patched:
        safe, reason = _is_url_safe(url)
        if not safe:
            return jsonify({'error': f'URL blocked: {reason}'}), 403

    try:
        resp = http_requests.get(url, timeout=5)
        content_type = resp.headers.get('Content-Type', '')
        body = resp.text[:4096]
    except Exception as exc:
        return jsonify({'error': f'Fetch failed: {str(exc)}'}), 502

    db = get_db()
    db.execute(
        "INSERT INTO imported_images (user_id, source_url, stored_data) VALUES (?, ?, ?)",
        (session['user_id'], url, body)
    )
    db.commit()
    db.close()

    return jsonify({
        'status': 'imported',
        'source_url': url,
        'content_type': content_type,
        'body_preview': body[:2048],
    })


@ssrf_bp.route('/ssrf-02')
def lab22_page():
    return render_template('labs/ssrf_02.html')


@ssrf_bp.route('/ssrf-02/test-webhook', methods=['POST'])
def lab22_test_webhook():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    if patched:
        safe, reason = _is_url_safe(url)
        if not safe:
            return jsonify({'error': f'URL blocked: {reason}'}), 403

    try:
        resp = http_requests.get(url, timeout=5)
    except Exception as exc:
        return jsonify({'error': f'Webhook request failed: {str(exc)}'}), 502

    db = get_db()
    db.execute(
        "INSERT INTO webhooks (user_id, url, last_status, last_response) VALUES (?, ?, ?, ?)",
        (session['user_id'], url, resp.status_code, resp.text[:4096])
    )
    db.commit()
    db.close()

    return jsonify({
        'status_code': resp.status_code,
        'response_body': resp.text[:2048],
        'headers': dict(resp.headers),
    })


@ssrf_bp.route('/ssrf-03')
def lab23_page():
    return render_template('labs/ssrf_03.html')


@ssrf_bp.route('/ssrf-03/generate-report', methods=['POST'])
def lab23_generate_report():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    source_url = data.get('source_url', '').strip()
    if not source_url:
        return jsonify({'error': 'source_url is required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)
    if patched:
        safe, reason = _is_url_safe(source_url)
        if not safe:
            return jsonify({'error': f'URL blocked: {reason}'}), 403

    try:
        resp = http_requests.get(source_url, timeout=5)
    except Exception as exc:
        return jsonify({'error': f'Fetch failed: {str(exc)}'}), 502

    report_content = resp.text[:4096]
    return jsonify({
        'status': 'report_generated',
        'source': source_url,
        'report_html': report_content,
    })


@ssrf_bp.route('/ssrf-04')
def lab24_page():
    return render_template('labs/ssrf_04.html')


@ssrf_bp.route('/ssrf-04/redirector')
def lab24_redirector():
    target = request.args.get('target', '/')
    return redirect(target, code=302)


@ssrf_bp.route('/ssrf-04/fetch-preview', methods=['POST'])
def lab24_fetch_preview():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)

    if patched:
        current_url = url
        for _ in range(10):
            safe, reason = _is_url_safe(current_url)
            if not safe:
                return jsonify({'error': f'URL blocked at redirect: {reason}'}), 403
            try:
                resp = http_requests.get(current_url, timeout=5, allow_redirects=False)
            except Exception as exc:
                return jsonify({'error': f'Fetch failed: {str(exc)}'}), 502
            if resp.is_redirect:
                current_url = resp.headers.get('Location', '')
                if not current_url:
                    break
                continue
            return jsonify({
                'status_code': resp.status_code,
                'body_preview': resp.text[:2048],
            })
        return jsonify({'error': 'Too many redirects'}), 502
    else:
        if not _naive_hostname_check(url):
            return jsonify({'error': 'URL blocked'}), 403
        try:
            resp = http_requests.get(url, timeout=5, allow_redirects=True)
        except Exception as exc:
            return jsonify({'error': f'Fetch failed: {str(exc)}'}), 502
        return jsonify({
            'status_code': resp.status_code,
            'body_preview': resp.text[:2048],
        })


@ssrf_bp.route('/ssrf-05')
def lab25_page():
    return render_template('labs/ssrf_05.html')


@ssrf_bp.route('/ssrf-05/fetch-resource', methods=['POST'])
def lab25_fetch_resource():
    err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    patched = current_app.config.get('PATCHED_MODE', False)

    if patched:
        safe, reason = _is_url_safe(url)
        if not safe:
            return jsonify({'error': f'URL blocked: {reason}'}), 403
    else:
        safe, reason = _naive_at_sign_check(url)
        if not safe:
            return jsonify({'error': f'URL blocked: {reason}'}), 403

    try:
        resp = http_requests.get(url, timeout=5)
    except Exception as exc:
        return jsonify({'error': f'Fetch failed: {str(exc)}'}), 502

    return jsonify({
        'status_code': resp.status_code,
        'body': resp.text[:2048],
    })
