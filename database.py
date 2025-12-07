import sqlite3
import os

# Use a DB file located next to this module so the application uses a consistent
# database file regardless of the current working directory when launched.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "sales_management.db")

class DatabaseManager:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.check_schema()

    def connect(self):
        # Increase timeout to wait for locks and allow faster concurrent reads/writes.
        # Keep default check_same_thread (True) to avoid unsafe cross-thread use.
        conn = sqlite3.connect(self.db_name, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def check_schema(self):
        conn = self.connect()
        c = conn.cursor()
        # Improve concurrency: enable WAL journal mode and set busy timeout
        try:
            c.execute('PRAGMA journal_mode=WAL')
        except Exception:
            pass
        try:
            # busy_timeout in milliseconds
            c.execute('PRAGMA busy_timeout = 30000')
        except Exception:
            pass
        
        # Categories
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_path TEXT
        )''')

        # Items
        c.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            image_path TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )''')

        # Users
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )''')
        # Ensure persistent lockout/attempt columns exist so lockout can survive restarts
        try:
            existing = [r[1] for r in c.execute("PRAGMA table_info('users')").fetchall()]
            if 'cred_attempts' not in existing:
                try:
                    c.execute('ALTER TABLE users ADD COLUMN cred_attempts INTEGER DEFAULT 0')
                except Exception:
                    pass
            if 'locked_until' not in existing:
                try:
                    c.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")
                except Exception:
                    pass
        except Exception:
            pass

        # Orders
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL UNIQUE,
            order_datetime TEXT NOT NULL,
            subtotal REAL NOT NULL,
            vat_amount REAL NOT NULL,
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            cash_given REAL,
            change REAL,
            receipt_pdf_path TEXT,
            receipt_png_path TEXT,
            voided INTEGER DEFAULT 0,
            void_reason TEXT
        )''')

        # Order Items
        c.execute('''CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(item_id) REFERENCES items(id)
        )''')

        # Stock Movements
        c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            change INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES items(id)
        )''')

        # Audit logs for admin actions and login events
        c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            event_type TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )''')

        conn.commit()
        conn.close()

db = DatabaseManager()
