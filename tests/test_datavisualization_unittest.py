import os
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datavisualization import VizPanel
from database import DatabaseManager


class VizTests(unittest.TestCase):
    def test_refresh_charts_no_data(self):
        # Create temp DB with no orders to exercise 'no data' branches
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.close()
        mgr = DatabaseManager(db_name=tf.name)
        try:
            # Some environments require a QApplication for QWidget usage
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance() or QApplication([])
            except Exception:
                app = None

            vp = VizPanel()
            # set date range wide but DB empty
            vp.date_from.setDate(vp.date_from.date())
            vp.date_to.setDate(vp.date_to.date())
            # should not raise
            vp.refresh_charts()
        finally:
            try:
                os.unlink(tf.name)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
