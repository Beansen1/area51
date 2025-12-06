import os
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import DatabaseManager, DB_NAME


class DatabaseTests(unittest.TestCase):
    def test_check_schema_creates_tables(self):
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        try:
            mgr = DatabaseManager(db_name=tf.name)
            conn = mgr.connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            names = {r[0] for r in cur.fetchall()}
            expected = {'categories', 'items', 'users', 'orders', 'order_items', 'stock_movements'}
            self.assertTrue(expected.issubset(names))
            conn.close()
        finally:
            try:
                os.unlink(tf.name)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
