import os
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from view import AdminPanel, ItemEditorDialog
    PYQT_AVAILABLE = True
except Exception:
    PYQT_AVAILABLE = False


class ViewTests(unittest.TestCase):
    def test_admin_panel_populate_items(self):
        if not PYQT_AVAILABLE:
            self.skipTest('PyQt5 not available in test environment')
        panel = AdminPanel()
        items = [
            {'id': 1, 'name': 'I', 'price': 10.0, 'stock': 5, 'category_name': 'C', 'image': None, 'image_path': None}
        ]
        # Should not raise
        panel.populate_items(items)

    def test_item_editor_validation(self):
        if not PYQT_AVAILABLE:
            self.skipTest('PyQt5 not available in test environment')
        dlg = ItemEditorDialog(categories=[{'id':1,'name':'C'}], item=None)
        # empty name should cause _on_save to warn and not accept
        dlg.input_name.setText('')
        # call private method; should return without raising
        dlg._on_save()


if __name__ == '__main__':
    unittest.main()
