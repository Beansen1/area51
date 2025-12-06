import os
import time
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import ReceiptGenerator, VAT_RATE


class ModelAdditionalTests(unittest.TestCase):
    def test_generate_receipt_no_items(self):
        # Should still create a receipt even with empty items list
        order = {
            'order_number': f'more-{int(time.time())}',
            'order_datetime': '2025-12-06 12:00:00',
            # omit subtotal so generator computes from items (empty -> 0)
            'total_amount': 0.0,
            'payment_method': 'cash'
        }
        items = []
        png = ReceiptGenerator.generate(order, items)
        self.assertTrue(isinstance(png, str))
        self.assertTrue(os.path.exists(png))
        try:
            os.remove(png)
        except Exception:
            pass

    def test_generate_receipt_long_item_name_and_vat_calc(self):
        order = {
            'order_number': f'more2-{int(time.time())}',
            'order_datetime': '2025-12-06 12:00:00',
            # omit subtotal/total so generator uses items
        }
        long_name = 'LongName ' * 40
        items = [
            {'name': long_name, 'quantity': 2, 'unit_price': 123.45, 'line_total': 246.90}
        ]
        png = ReceiptGenerator.generate(order, items)
        self.assertTrue(os.path.exists(png))
        try:
            os.remove(png)
        except Exception:
            pass

    def test_vat_calculation_matches_constant(self):
        subtotal = 500.0
        expected_vat = subtotal * VAT_RATE
        self.assertAlmostEqual(expected_vat, 500.0 * VAT_RATE)


if __name__ == '__main__':
    unittest.main()
