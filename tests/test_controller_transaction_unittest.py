import os
import time
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import DatabaseManager
import controller
from model import ReceiptGenerator


class TransactionTests(unittest.TestCase):
    def setUp(self):
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        self.db_path = tf.name
        self.mgr = DatabaseManager(db_name=self.db_path)

        # Build controller instance minimal
        C = controller.MainController.__new__(controller.MainController)
        C.cart = {}
        C._undo_stack = []
        C.kiosk = type('K', (), {'btn_undo': type('B', (), {'setEnabled': lambda self, v: None})()})()
        C.reset_timer = lambda: None
        C.update_cart_ui = lambda: None
        C.load_items = lambda: None
        C.load_categories = lambda: None
        C.show_toast = lambda *a, **k: None

        # patch db in controller
        controller.db = self.mgr
        # stub QMessageBox to prevent dialog blocking
        class MB:
            def information(self, *a, **k):
                return None
            def critical(self, *a, **k):
                return None
        controller.QMessageBox = MB()

        # stub sfx play
        controller.sfx = type('S', (), {'play': lambda *a, **k: None, 'get_duration': lambda *a, **k: 0.1})()

        self.C = C

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_process_transaction_creates_order_and_updates_stock(self):
        conn = controller.db.connect(); cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('tx',))
        cid = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('P', 50.0, 10, cid))
        iid = cur.lastrowid
        conn.commit(); conn.close()

        # prepare cart
        self.C.cart = {iid: {'data': {'id': iid, 'name': 'P', 'price': 50.0}, 'qty': 2}}

        pay_data = {'method': 'CASH', 'cash_given': 200.0, 'change': 100.0}
        subtotal = 100.0
        vat = subtotal * 0.12
        total = subtotal + vat

        # Monkeypatch ReceiptGenerator.generate to avoid image creation and return dummy path
        orig_gen = ReceiptGenerator.generate
        try:
            ReceiptGenerator.generate = staticmethod(lambda order, items: os.path.join(os.path.dirname(__file__), 'dummy.png'))
            # ensure dummy path exists
            open(os.path.join(os.path.dirname(__file__), 'dummy.png'), 'wb').close()

            self.C.process_transaction(pay_data, subtotal, vat, total)

            # verify order row
            conn = controller.db.connect(); cur = conn.cursor()
            o = cur.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 1').fetchone()
            self.assertIsNotNone(o)
            # stock updated
            it = cur.execute('SELECT stock FROM items WHERE id=?', (iid,)).fetchone()
            self.assertEqual(it['stock'], 8)
            # order_items exist
            oi = cur.execute('SELECT * FROM order_items WHERE item_id=?', (iid,)).fetchone()
            self.assertIsNotNone(oi)
            conn.close()
        finally:
            ReceiptGenerator.generate = orig_gen
            try:
                os.remove(os.path.join(os.path.dirname(__file__), 'dummy.png'))
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
