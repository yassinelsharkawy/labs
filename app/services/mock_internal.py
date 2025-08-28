import os
from flask import Flask, jsonify


def create_internal_app():
    app = Flask(__name__)

    @app.route('/internal/metadata')
    def metadata():
        return jsonify({
            'instance_id': 'i-0abc123',
            'region': 'us-east-1',
            'credentials': {
                'access_key': 'MOCK-ACCESS-KEY-12345',
                'secret_key': 'MOCK-SECRET-KEY-67890',
            },
        })

    @app.route('/internal/admin/config')
    def admin_config():
        return jsonify({
            'db_host': 'db.internal.local',
            'db_password': 'mock_db_pass_only',
            'redis_host': 'redis.internal.local',
        })

    @app.route('/internal/health')
    def health():
        return jsonify({
            'status': 'ok',
            'service': 'internal-api',
        })

    return app


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5001))
    app = create_internal_app()
    app.run(host=host, port=port, debug=False)
