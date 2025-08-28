import sqlite3
import os

def get_db():
    db_path = os.environ.get('DB_PATH', 'websec_labs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user',
        tenant_id INTEGER DEFAULT 1,
        mfa_secret TEXT,
        mfa_enabled INTEGER DEFAULT 0,
        recovery_code TEXT,
        disabled INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        invoice_number TEXT NOT NULL,
        customer_name TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending',
        pdf_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        shared_with TEXT DEFAULT '',
        deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT DEFAULT 'member',
        active INTEGER DEFAULT 1,
        invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS export_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        requested_by INTEGER NOT NULL,
        file_name TEXT,
        status TEXT DEFAULT 'ready',
        data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role_name TEXT NOT NULL,
        permissions TEXT DEFAULT ''
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_token TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revoked INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        key_value TEXT UNIQUE NOT NULL,
        revoked INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS oauth_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state_token TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        provider TEXT,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT DEFAULT 'post',
        target_id INTEGER DEFAULT 0,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        description TEXT,
        price REAL,
        stock INTEGER DEFAULT 0,
        secret_note TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        detail TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS wiki_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        body TEXT,
        author_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_pct INTEGER DEFAULT 10,
        max_uses INTEGER DEFAULT 1,
        times_used INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        balance REAL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL,
        status TEXT DEFAULT 'pending',
        coupon_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        amount REAL,
        status TEXT DEFAULT 'processed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        accepted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS verification_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan TEXT DEFAULT 'free',
        status TEXT DEFAULT 'active',
        cancel_requested INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS team_seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        max_seats INTEGER DEFAULT 3,
        used_seats INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        last_status INTEGER,
        last_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS imported_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        source_url TEXT,
        stored_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    _seed_data(conn)
    conn.close()


def _seed_data(conn):
    c = conn.cursor()
    existing = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    from werkzeug.security import generate_password_hash
    import secrets

    users_data = [
        ('admin', generate_password_hash('admin123'), 'admin@corp.local', 'admin', 1, None, 0, None),
        ('alice', generate_password_hash('alice123'), 'alice@corp.local', 'user', 1, None, 0, None),
        ('bob', generate_password_hash('bob123'), 'bob@corp.local', 'user', 1, None, 0, None),
        ('carol', generate_password_hash('carol123'), 'carol@corp.local', 'manager', 1, None, 0, None),
        ('dave', generate_password_hash('dave123'), 'dave@corp.local', 'user', 2, None, 0, None),
        ('eve', generate_password_hash('eve123'), 'eve@corp.local', 'user', 2, None, 0, None),
        ('frank', generate_password_hash('frank123'), 'frank@corp.local', 'admin', 2, None, 0, None),
        ('grace', generate_password_hash('grace123'), 'grace@corp.local', 'user', 1, 'JBSWY3DPEHPK3PXP', 1, 'RECOVERY-GRACE-001'),
        ('heidi', generate_password_hash('heidi123'), 'heidi@corp.local', 'user', 1, None, 0, None),
        ('ivan', generate_password_hash('ivan123'), 'ivan@corp.local', 'user', 1, None, 0, None),
    ]
    c.executemany(
        "INSERT INTO users (username, password_hash, email, role, tenant_id, mfa_secret, mfa_enabled, recovery_code) VALUES (?,?,?,?,?,?,?,?)",
        users_data
    )

    invoices_data = [
        (1, 'INV-1001', 'Acme Widget Co', 5200.00, 'paid', '/exports/inv-1001.pdf'),
        (1, 'INV-1002', 'Beta Services', 3100.00, 'pending', '/exports/inv-1002.pdf'),
        (1, 'INV-1003', 'Gamma LLC', 8750.50, 'paid', '/exports/inv-1003.pdf'),
        (2, 'INV-2001', 'Delta Partners', 12400.00, 'paid', '/exports/inv-2001.pdf'),
        (2, 'INV-2002', 'Epsilon Inc', 950.00, 'pending', '/exports/inv-2002.pdf'),
    ]
    c.executemany("INSERT INTO invoices (tenant_id, invoice_number, customer_name, amount, status, pdf_path) VALUES (?,?,?,?,?,?)", invoices_data)

    docs_data = [
        (1, 'Q3 Financial Report', 'Revenue: $2.4M, EBITDA: $800K. Confidential.', '2', 0),
        (2, 'Project Alpha Specs', 'Internal architecture document for Project Alpha.', '', 0),
        (3, 'Meeting Notes Oct', 'Discussed roadmap and hiring plan.', '1,2', 0),
        (4, 'HR Policy Draft', 'New PTO policy for 2025. Manager-only access.', '', 0),
        (1, 'Archived Contract', 'Old vendor contract - archived.', '', 1),
    ]
    c.executemany("INSERT INTO documents (owner_id, title, content, shared_with, deleted) VALUES (?,?,?,?,?)", docs_data)

    team_data = [
        (1, 1, 'owner', 1), (1, 2, 'member', 1), (1, 3, 'member', 1),
        (1, 4, 'member', 0),
        (2, 5, 'owner', 1), (2, 6, 'member', 1),
    ]
    c.executemany("INSERT INTO team_members (team_id, user_id, role, active) VALUES (?,?,?,?)", team_data)

    exports_data = [
        (1, 1, 'tenant1_users_export.csv', 'ready', 'admin,alice,bob,carol - emails and roles'),
        (1, 2, 'tenant1_billing_report.csv', 'ready', 'invoice data for tenant 1'),
        (2, 5, 'tenant2_users_export.csv', 'ready', 'dave,eve,frank - emails and roles'),
    ]
    c.executemany("INSERT INTO export_jobs (tenant_id, requested_by, file_name, status, data) VALUES (?,?,?,?,?)", exports_data)

    roles_data = [
        (1, 1, 'admin', 'read,write,delete,manage_users'),
        (1, 2, 'editor', 'read,write'),
        (1, 3, 'viewer', 'read'),
        (2, 5, 'admin', 'read,write,delete,manage_users'),
    ]
    c.executemany("INSERT INTO roles (tenant_id, user_id, role_name, permissions) VALUES (?,?,?,?)", roles_data)

    api_keys_data = [
        (8, 'apikey-grace-001', 0),
        (2, 'apikey-alice-001', 0),
    ]
    c.executemany("INSERT INTO api_keys (user_id, key_value, revoked) VALUES (?,?,?)", api_keys_data)

    products_data = [
        ('Wireless Keyboard', 'electronics', 'Ergonomic wireless keyboard', 49.99, 150, 'Supplier cost: $12.50'),
        ('USB Hub 7-Port', 'electronics', 'Powered USB 3.0 hub', 29.99, 200, 'Margin: 68%'),
        ('Standing Desk Mat', 'office', 'Anti-fatigue floor mat', 39.99, 80, 'Vendor: internal-supplier-7'),
        ('Monitor Arm', 'office', 'Adjustable dual monitor arm', 89.99, 45, 'Discontinued after Q4'),
        ('Webcam HD', 'electronics', 'Full HD webcam with microphone', 59.99, 120, 'Bulk order pending'),
    ]
    c.executemany("INSERT INTO products (name, category, description, price, stock, secret_note) VALUES (?,?,?,?,?,?)", products_data)

    coupons_data = [
        ('WELCOME10', 10, 1, 0),
        ('SAVE20', 20, 3, 0),
        ('VIP50', 50, 1, 0),
    ]
    c.executemany("INSERT INTO coupons (code, discount_pct, max_uses, times_used) VALUES (?,?,?,?)", coupons_data)

    wallets_data = [(2, 100.00), (3, 50.00), (5, 200.00), (9, 75.00)]
    c.executemany("INSERT INTO wallets (user_id, balance) VALUES (?,?)", wallets_data)

    orders_data = [
        (2, 49.99, 'completed', None),
        (3, 89.99, 'completed', None),
    ]
    c.executemany("INSERT INTO orders (user_id, amount, status, coupon_id) VALUES (?,?,?,?)", orders_data)

    c.execute("INSERT INTO team_seats (team_id, max_seats, used_seats) VALUES (1, 3, 2)")
    c.execute("INSERT INTO team_seats (team_id, max_seats, used_seats) VALUES (2, 5, 2)")

    c.execute("INSERT INTO subscriptions (user_id, plan, status) VALUES (2, 'pro', 'active')")
    c.execute("INSERT INTO subscriptions (user_id, plan, status) VALUES (3, 'free', 'active')")

    wiki_data = [
        ('getting-started', 'Getting Started', '<h2>Welcome</h2><p>This is the getting started guide.</p>', 1),
        ('api-reference', 'API Reference', '<h2>API Docs</h2><p>Endpoints documented here.</p>', 1),
    ]
    c.executemany("INSERT INTO wiki_pages (slug, title, body, author_id) VALUES (?,?,?,?)", wiki_data)

    conn.commit()


def reset_db():
    db_path = os.environ.get('DB_PATH', 'websec_labs.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
