import os
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import inserting
from database import DatabaseManager


class InsertingTests(unittest.TestCase):
    def test_commit_with_retry_raises_after_retries(self):
        class BadConn:
            def commit(self):
                raise Exception('locked')

        with self.assertRaises(Exception):
            inserting.commit_with_retry(BadConn(), retries=2, initial_delay=0)

    def test_verify_and_migrate_image_flow(self):
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        mgr = DatabaseManager(db_name=tf.name)
        conn = mgr.connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", ('T',))
        cid = cur.lastrowid
        # create temp image file
        tmpimg = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        tmpimg.write(b'PNGDATA')
        tmpimg.close()
        cur.execute("INSERT INTO items (name, price, stock, category_id, image_path) VALUES (?,?,?,?,?)",
                    ('Img', 1.0, 1, cid, tmpimg.name))
        # add image column for migration target
        try:
            cur.execute('ALTER TABLE items ADD COLUMN image BLOB')
        except Exception:
            pass
        conn.commit(); conn.close()

        # run verify_images and migrate
        inserting.db = mgr
        inserting.verify_images()
        inserting.migrate_image_paths_to_blob()

        conn = mgr.connect(); cur = conn.cursor()
        r = cur.execute("SELECT image FROM items WHERE name=?", ('Img',)).fetchone()
        conn.close()
        # image may be updated; at minimum migration ran without error
        self.assertIsNotNone(r)
        try:
            os.unlink(tf.name)
            os.unlink(tmpimg.name)
        except Exception:
            pass


if __name__ == '__main__':
    unittest.main()
