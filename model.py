from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

VAT_RATE = 0.12


class ReceiptGenerator:
    @staticmethod
    def _load_font(size, bold=False):
        # Try common system fonts, fallback to default
        candidates = ["arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
        for f in candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def generate(order_data, items_data):
        """Generate a PNG receipt (full details, store-style) and return the png path.
        No PDF is created.
        """
        if not os.path.exists("receipts"):
            os.makedirs("receipts")

        filename = f"receipts/{order_data['order_number']}"
        png_path = f"{filename}.png"

        # Layout: compute height based on number of items
        width = 600
        header_h = 180
        line_h = 28
        footer_h = 160
        items_h = max(200, len(items_data) * line_h + 20)
        height = header_h + items_h + footer_h

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Fonts
        f_head = ReceiptGenerator._load_font(28, bold=True)
        f_sub = ReceiptGenerator._load_font(16)
        f_body = ReceiptGenerator._load_font(14)
        f_mono = ReceiptGenerator._load_font(12)

        x = 40
        y = 30

        # Header
        draw.text((x, y), "QuickStop Convenience", font=f_head, fill=(20, 20, 20))
        y += 36
        draw.text((x, y), "123 Market St., Barangay Central", font=f_sub, fill=(60, 60, 60))
        y += 20
        draw.text((x, y), "Tarlac City | (+63) 912-345-6789", font=f_sub, fill=(60, 60, 60))
        y += 26
        draw.text((x, y), f"Order #: {order_data.get('order_number')}", font=f_body, fill=(0, 0, 0))
        y += 20
        draw.text((x, y), f"Date: {order_data.get('order_datetime')}", font=f_body, fill=(0, 0, 0))
        y += 26

        draw.line((x, y, width - x, y), fill=(200, 200, 200), width=1)
        y += 12

        # Column headers
        draw.text((x, y), "Item", font=f_mono, fill=(0, 0, 0))
        draw.text((x + 320, y), "Qty", font=f_mono, fill=(0, 0, 0))
        draw.text((x + 380, y), "Price", font=f_mono, fill=(0, 0, 0))
        draw.text((x + 480, y), "Total", font=f_mono, fill=(0, 0, 0))
        y += 18
        draw.line((x, y, width - x, y), fill=(230, 230, 230), width=1)
        y += 8

        # Items
        for it in items_data:
            name = it.get('name')[:35]
            qty = str(it.get('quantity'))
            price = f"{it.get('unit_price'):.2f}"
            total = f"{it.get('line_total'):.2f}"
            draw.text((x, y), name, font=f_mono, fill=(20, 20, 20))
            draw.text((x + 320, y), qty, font=f_mono, fill=(20, 20, 20))
            draw.text((x + 380, y), price, font=f_mono, fill=(20, 20, 20))
            draw.text((x + 480, y), total, font=f_mono, fill=(20, 20, 20))
            y += line_h

        y += 10
        draw.line((x, y, width - x, y), fill=(200, 200, 200), width=1)
        y += 12

        # Totals
        draw.text((x + 340, y), "Subtotal:", font=f_body, fill=(0, 0, 0))
        draw.text((x + 480, y), f"{order_data.get('subtotal'):.2f}", font=f_body, fill=(0, 0, 0))
        y += 24
        draw.text((x + 340, y), f"VAT ({int(VAT_RATE*100)}%):", font=f_body, fill=(0, 0, 0))
        draw.text((x + 480, y), f"{order_data.get('vat_amount'):.2f}", font=f_body, fill=(0, 0, 0))
        y += 28
        draw.text((x + 340, y), "TOTAL:", font=f_head, fill=(0, 0, 0))
        draw.text((x + 480, y), f"{order_data.get('total_amount'):.2f}", font=f_head, fill=(0, 100, 0))
        y += 44

        # Payment / Footer
        draw.text((x, y), f"Payment: {order_data.get('payment_method')}", font=f_body, fill=(0, 0, 0))
        y += 22
        draw.text((x, y), "Thank you for shopping at QuickStop!", font=f_sub, fill=(80, 80, 80))
        y += 22
        draw.text((x, y), "Visit again.", font=f_sub, fill=(80, 80, 80))

        # Save PNG
        try:
            img.save(png_path)
        except Exception:
            # Fallback: save smaller image
            img_small = img.resize((int(width * 0.7), int(height * 0.7)))
            img_small.save(png_path)

        return png_path
