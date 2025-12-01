from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

# Optional: use the `qrcode` library if available. If not installed, we'll
# fall back to drawing the order number as text in a box instead of a scannable QR.
try:
    import qrcode
    _HAS_QRCODE = True
except Exception:
    qrcode = None
    _HAS_QRCODE = False

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

        # QR Code: encode the order number so scanning shows the order id
        qr_size = 140
        qr_margin = 20
        qr_img = None
        order_id_text = str(order_data.get('order_number') or '')
        if order_id_text:
            try:
                if _HAS_QRCODE:
                    qr = qrcode.QRCode(box_size=4, border=2)
                    qr.add_data(order_id_text)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
                else:
                    # Fallback: create a simple boxed area with the order id as text
                    qr_img = Image.new('RGB', (qr_size, qr_size), color=(255, 255, 255))
                    qd = ImageDraw.Draw(qr_img)
                    qd.rectangle((0, 0, qr_size - 1, qr_size - 1), outline=(0, 0, 0), width=2)
                    # center the order text
                    ft = ReceiptGenerator._load_font(12)
                    txt = order_id_text
                    tw, th = qd.textsize(txt, font=ft)
                    qd.text(((qr_size - tw) / 2, (qr_size - th) / 2), txt, font=ft, fill=(0, 0, 0))
            except Exception:
                qr_img = None

        if qr_img is not None:
            try:
                # paste QR at bottom-right above footer area
                px = width - qr_size - qr_margin
                py = height - qr_size - qr_margin
                img.paste(qr_img, (px, py))
            except Exception:
                pass

        # Save PNG
        try:
            img.save(png_path)
        except Exception:
            # Fallback: save smaller image
            img_small = img.resize((int(width * 0.7), int(height * 0.7)))
            img_small.save(png_path)

        return png_path
