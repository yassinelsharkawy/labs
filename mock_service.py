import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.route('/internal/metadata')
def metadata():
    return jsonify({
        'instance_id': 'i-0abc123def456',
        'region': 'us-east-1',
        'availability_zone': 'us-east-1a',
        'instance_type': 'm5.large',
        'credentials': {
            'access_key': 'MOCK-ACCESS-KEY-12345',
            'secret_key': 'MOCK-SECRET-KEY-67890',
            'token': 'MOCK-SESSION-TOKEN-ABCDEF',
        },
    })


@app.route('/internal/admin/config')
def admin_config():
    return jsonify({
        'db_host': 'db.internal.local',
        'db_port': 5432,
        'db_name': 'production',
        'db_user': 'app_admin',
        'db_password': 'mock_db_pass_only',
        'redis_host': 'redis.internal.local',
        'redis_port': 6379,
        'api_signing_key': 'MOCK-SIGNING-KEY-XYZ789',
    })


@app.route('/internal/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'internal-api',
        'version': '2.4.1',
    })


@app.route('/')
def index():
    return jsonify({
        'service': 'mock-internal',
        'endpoints': ['/internal/metadata', '/internal/admin/config', '/internal/health'],
    })


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5001))
    app.run(host=host, port=port, debug=False)
