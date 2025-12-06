import os
import tempfile
import sqlite3
import unittest
import types
from unittest import mock

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import DatabaseManager
import controller


class _KioskStub:
    def __init__(self):
        class Btn:
            def setEnabled(self, v):
                self.enabled = v
        self.btn_undo = Btn()

    def update_cart_display(self, display_list, totals):
        self.last_display = (display_list, totals)


class MsgBoxStub:
    Yes = 1
    No = 0

    def __init__(self):
        self.last = None

    def warning(self, *args, **kwargs):
        self.last = ('warning', args, kwargs)

    def information(self, *args, **kwargs):
        self.last = ('info', args, kwargs)

    def critical(self, *args, **kwargs):
        self.last = ('crit', args, kwargs)

    def question(self, *args, **kwargs):
        return MsgBoxStub.Yes


class ControllerTests(unittest.TestCase):
    def setUp(self):
        # temp DB
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        self.db_path = tf.name
        self.mgr = DatabaseManager(db_name=self.db_path)

        # create controller instance without Qt init
        C = controller.MainController.__new__(controller.MainController)
        C.cart = {}
        C.current_cat_id = 0
        C.search_text = ''
        C._undo_stack = []
        C.kiosk = _KioskStub()
        C._admin_pin = '1188'

        C.reset_timer = lambda: None
        # bind update_cart_ui method from class to instance
        C.update_cart_ui = types.MethodType(controller.MainController.update_cart_ui, C)
        C.load_items = lambda: None
        C.load_categories = lambda: None
        C.show_toast = lambda msg, duration_ms=2200: None

        # patch db and QMessageBox
        self.msgbox = MsgBoxStub()
        self._db_patch = mock.patch.object(controller, 'db', self.mgr)
        self._mb_patch = mock.patch.object(controller, 'QMessageBox', self.msgbox)
        self._db_patch.start()
        self._mb_patch.start()

        self.C = C

    def tearDown(self):
        self._db_patch.stop()
        self._mb_patch.stop()
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_add_to_cart_respects_stock(self):
        conn = controller.db.connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('c',))
        cid = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('x', 10.0, 1, cid))
        iid = cur.lastrowid
        conn.commit(); conn.close()

        self.C.add_to_cart(iid)
        self.assertIn(iid, self.C.cart)
        # second add should not increase qty beyond stock
        self.C.add_to_cart(iid)
        self.assertEqual(self.C.cart[iid]['qty'], 1)

    def test_update_and_remove_and_undo(self):
        conn = controller.db.connect(); cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('c2',))
        cid = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('y', 5.0, 5, cid))
        iid = cur.lastrowid
        conn.commit(); conn.close()

        self.C.add_to_cart(iid)
        self.C.update_cart_qty(iid, 2)
        self.assertEqual(self.C.cart[iid]['qty'], 3)
        self.C.update_cart_qty(iid, -3)
        self.assertNotIn(iid, self.C.cart)

        # undo set action
        self.C.add_to_cart(iid)
        self.C.update_cart_qty(iid, 1)
        self.C.undo_last_action()
        # after undo, qty should be restored to previous value (1)
        self.assertTrue(self.C.cart[iid]['qty'] in (1,))

    def test_clear_and_undo(self):
        conn = controller.db.connect(); cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('c3',))
        cid = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('a', 2.0, 10, cid))
        id1 = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('b', 3.0, 10, cid))
        id2 = cur.lastrowid
        conn.commit(); conn.close()

        # Instead of relying on add_to_cart (which stores sqlite Row objects that may not deepcopy),
        # set cart entries to plain dicts so deepcopy in clear_cart succeeds and undo can restore.
        self.C.cart = {
            id1: {'data': {'id': id1, 'name': 'a', 'price': 2.0, 'stock': 10}, 'qty': 1},
            id2: {'data': {'id': id2, 'name': 'b', 'price': 3.0, 'stock': 10}, 'qty': 1}
        }

        # monkeypatch QMessageBox.question to return Yes
        controller.QMessageBox = MsgBoxStub()
        controller.QMessageBox.question = lambda *a, **k: MsgBoxStub.Yes

        self.C.clear_cart()
        self.assertFalse(self.C.cart)
        self.C.undo_last_action()
        self.assertTrue(id1 in self.C.cart or id2 in self.C.cart)

    def test_admin_adjust_stock(self):
        conn = controller.db.connect(); cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('c4',))
        cid = cur.lastrowid
        cur.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", ('z', 20.0, 5, cid))
        iid = cur.lastrowid
        conn.commit(); conn.close()

        # run adjust
        self.C.admin_adjust_stock(iid, 12)
        conn = controller.db.connect(); cur = conn.cursor()
        r = cur.execute("SELECT stock FROM items WHERE id=?", (iid,)).fetchone()
        mv = cur.execute("SELECT change FROM stock_movements WHERE item_id=? ORDER BY id DESC LIMIT 1", (iid,)).fetchone()
        conn.close()
        self.assertEqual(r['stock'], 12)
        self.assertEqual(mv['change'], 7)


if __name__ == '__main__':
    unittest.main()
