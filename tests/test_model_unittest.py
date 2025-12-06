import os
import time
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model import ReceiptGenerator, VAT_RATE


class ModelTests(unittest.TestCase):
    def test_vat_rate_constant(self):
        self.assertAlmostEqual(VAT_RATE, 0.12)

    def test_generate_receipt_creates_file(self):
        order = {
            'order_number': f'unittest-{int(time.time())}',
            'order_datetime': '2025-12-06 12:00:00',
            'subtotal': 100.0,
            'total_amount': 112.0,
            'payment_method': 'cash',
            'cash_given': 200.0,
        }
        items = [
            {'name': 'Test Item', 'quantity': 1, 'unit_price': 100.0, 'line_total': 100.0}
        ]
        png = ReceiptGenerator.generate(order, items)
        self.assertTrue(isinstance(png, str))
        self.assertTrue(os.path.exists(png))
        try:
            os.remove(png)
        except Exception:
            pass


if __name__ == '__main__':
    unittest.main()
