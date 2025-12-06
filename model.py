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
        # Ensure receipts are stored inside the project directory under 'receipts' (plural)
        module_dir = os.path.dirname(__file__)
        receipts_dir = os.path.join(module_dir, 'receipts')
        legacy_dir = os.path.join(module_dir, 'receipt')

        # If an old 'receipt' folder exists, try to migrate it to 'receipts'
        if os.path.exists(legacy_dir) and not os.path.exists(receipts_dir):
            try:
                os.rename(legacy_dir, receipts_dir)
            except Exception:
                try:
                    os.makedirs(receipts_dir, exist_ok=True)
                    for fn in os.listdir(legacy_dir):
                        src = os.path.join(legacy_dir, fn)
                        dst = os.path.join(receipts_dir, fn)
                        try:
                            if os.path.isfile(src):
                                os.replace(src, dst)
                        except Exception:
                            # ignore individual file move errors
                            pass
                except Exception:
                    pass

        if not os.path.exists(receipts_dir):
            os.makedirs(receipts_dir)

        png_path = os.path.join(receipts_dir, f"{order_data['order_number']}.png")

        # Layout: compute height based on number of items
        width = 800
        header_h = 200
        line_h = 28
        footer_h = 160

        # Use a temporary draw object to measure wrapping
        tmp_img = Image.new('RGB', (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)

        # Robust text measurement helper (works across Pillow versions)
        def text_size(draw_obj, text, font):
            try:
                # preferred in newer Pillow: textbbox
                bbox = draw_obj.textbbox((0, 0), text, font=font)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            except Exception:
                try:
                    return draw_obj.textsize(text, font=font)
                except Exception:
                    try:
                        return font.getsize(text)
                    except Exception:
                        # fallback guess
                        return (len(text) * 6, 12)


        # Helper: wrap text to fit within max_width using the provided font
        def wrap_text(draw_obj, text, font, max_w):
            words = (text or '').split()
            if not words:
                return ['']
            lines = []
            cur = words[0]
            for w in words[1:]:
                tw, th = text_size(draw_obj, cur + ' ' + w, font)
                if tw <= max_w:
                    cur = cur + ' ' + w
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines

        # Fonts
        f_head = ReceiptGenerator._load_font(28, bold=True)
        f_sub = ReceiptGenerator._load_font(16)
        f_body = ReceiptGenerator._load_font(14)
        f_mono = ReceiptGenerator._load_font(12)

        x = 40
        y = 30

        # Prepare item wrapping measurements now that fonts and x are known
        # Column positions used for wrapping/measurement
        right_boundary = width - x
        value_x = right_boundary - 20
        col_total_right = value_x
        col_price_right = value_x - 120
        col_qty_center = col_price_right - 60
        # item column starts at x and ends before qty column
        item_col_w = max(80, int(col_qty_center - x) - 12)

        # Precompute wrapped lines for each item so we can calculate exact height
        prepared_items = []
        total_items_height = 0
        for it in items_data:
            name = str(it.get('name') or '')
            lines = wrap_text(tmp_draw, name, f_mono, item_col_w)
            # ensure at least one line
            lines = lines if lines else ['']
            # height for this item = number of lines * line_h + separator spacing
            h = len(lines) * line_h + 6
            total_items_height += h
            prepared_items.append({
                'lines': lines,
                'quantity': str(it.get('quantity')),
                'price': f"{float(it.get('unit_price') or 0):.2f}",
                'total': f"{float(it.get('line_total') or 0):.2f}",
                'block_h': h
            })

        items_h = max(200, total_items_height + 20)
        height = header_h + items_h + footer_h

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Optional logo (left of header text). Try project assets first, then cwd.
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'images', 'DaleT.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.getcwd(), 'assets', 'images', 'DaleT.png')

        logo_drawn = False
        logo_w = logo_h = 0
        try:
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert('RGBA')
                # scale logo to fit header height
                max_logo_h = 80
                scale = min(1.0, max_logo_h / float(logo.height))
                logo_w = int(logo.width * scale)
                logo_h = int(logo.height * scale)
                logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
                img.paste(logo, (x, y), logo)
                logo_drawn = True
        except Exception:
            logo_drawn = False

        # Shift text right if logo drawn
        if logo_drawn:
            x = x + logo_w + 14

        # Header
        draw.text((x, y), "Dale Convenience", font=f_head, fill=(20, 20, 20))
        y += 36
        draw.text((x, y), "123 Market St., Barangay Central", font=f_sub, fill=(60, 60, 60))
        y += 20
        draw.text((x, y), "Nasugbu City | (+63) 912-345-6789", font=f_sub, fill=(60, 60, 60))
        y += 26
        # Make Order # more prominent
        try:
            order_font = ReceiptGenerator._load_font(18)
        except Exception:
            order_font = f_body
        draw.text((x, y), f"Order #: {order_data.get('order_number')}", font=order_font, fill=(0, 0, 0))
        y += 20
        draw.text((x, y), f"Date: {order_data.get('order_datetime')}", font=f_body, fill=(0, 0, 0))
        y += 26

        draw.line((x, y, width - x, y), fill=(200, 200, 200), width=1)
        y += 12

        # Column headers (positions adjusted for wider receipt)
        # right boundary for totals (we will right-align amounts here)
        right_boundary = width - x
        value_x = right_boundary - 20
        col_total_right = value_x
        col_price_right = value_x - 120
        col_qty_center = col_price_right - 60
        # item column starts at x and ends before qty column
        draw.text((x, y), "Item", font=f_mono, fill=(0, 0, 0))
        # center the Qty header
        tw_q, _ = text_size(draw, "Qty", f_mono)
        draw.text((col_qty_center - tw_q / 2, y), "Qty", font=f_mono, fill=(0, 0, 0))
        # price header right-aligned to price column
        tw_p, _ = text_size(draw, "Price", f_mono)
        draw.text((col_price_right - tw_p, y), "Price", font=f_mono, fill=(0, 0, 0))
        # total header
        tw_t, _ = text_size(draw, "Total", f_mono)
        draw.text((col_total_right - tw_t, y), "Total", font=f_mono, fill=(0, 0, 0))
        y += 18
        draw.line((x, y, width - x, y), fill=(230, 230, 230), width=1)
        y += 8

        # Items: render using prepared_items so spacing matches items_h
        for itm in prepared_items:
            lines = itm['lines']
            qty = itm['quantity']
            price = itm['price']
            total = itm['total']
            first_line = True
            for ln in lines:
                draw.text((x, y), ln, font=f_mono, fill=(20, 20, 20))
                if first_line:
                    # draw qty centered in its column
                    qw, qh = text_size(draw, qty, f_mono)
                    draw.text((col_qty_center - qw / 2, y), qty, font=f_mono, fill=(20, 20, 20))
                    # draw price right-aligned within price column
                    pw, ph = text_size(draw, price, f_mono)
                    draw.text((col_price_right - pw, y), price, font=f_mono, fill=(20, 20, 20))
                    # right-align total against right boundary
                    tw_item, th_item = text_size(draw, total, f_mono)
                    draw.text((col_total_right - tw_item, y), total, font=f_mono, fill=(20, 20, 20))
                    first_line = False
                y += line_h

            # draw a subtle separator every item for readability
            draw.line((x, y, width - x, y), fill=(245, 245, 245), width=1)
            y += 6

        # Totals: subtotal / VAT / total (compute from items if order does not provide)
        try:
            subtotal = float(order_data.get('subtotal') if order_data.get('subtotal') is not None else sum(float(it.get('line_total') or 0) for it in items_data))
        except Exception:
            subtotal = sum(float(it.get('line_total') or 0) for it in items_data)
        vat = subtotal * VAT_RATE
        try:
            total_amt = float(order_data.get('total_amount') if order_data.get('total_amount') is not None else subtotal + vat)
        except Exception:
            total_amt = subtotal + vat

        # draw subtotal, VAT, and grand total right-aligned
        lines_to_draw = [
            (f"Subtotal: ₱ {subtotal:,.2f}", 0),
            (f"VAT ({int(VAT_RATE*100)}%): ₱ {vat:,.2f}", line_h),
            (f"Total: ₱ {total_amt:,.2f}", line_h * 2)
        ]
        for txt, offset in lines_to_draw:
            twt, tht = text_size(draw, txt, f_body)
            draw.text((value_x - twt, y + offset), txt, font=f_body, fill=(0, 100, 0) if 'Total' in txt else (0, 0, 0))
        y += line_h * 3 + 12

        # (Footer content is drawn later; skip drawing payment here to avoid duplication)

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
                    tw, th = text_size(qd, txt, ft)
                    qd.text(((qr_size - tw) / 2, (qr_size - th) / 2), txt, font=ft, fill=(0, 0, 0))
            except Exception:
                qr_img = None

        # Place QR in the upper-right header area so it doesn't overlap the item list
        if qr_img is not None:
            try:
                px = width - qr_size - qr_margin
                # choose a top offset inside the header area
                header_qr_top_max = max(10, header_h - qr_size - 10)
                py = min(30, header_qr_top_max)
                img.paste(qr_img, (px, py))
            except Exception:
                pass

        # Payment info: show paid amount and change if provided
        try:
            payment_method = order_data.get('payment_method', '')
            cash_given = order_data.get('cash_given') or order_data.get('paid_amount') or None
            change_amount = order_data.get('change') or order_data.get('cash_change') or None
            # compute change if cash_given provided but change not supplied
            try:
                total_amt = float(order_data.get('total_amount') or 0.0)
            except Exception:
                total_amt = 0.0
            if cash_given is not None:
                try:
                    cash_val = float(cash_given)
                    if change_amount is None:
                        change_amount = cash_val - total_amt
                except Exception:
                    pass
        except Exception:
            payment_method = order_data.get('payment_method', '')
            cash_given = None
            change_amount = None

        # Draw payment section (placed inside the footer area)
        # compute footer top (start of footer area) so payment info is positioned reliably
        try:
            footer_top = header_h + items_h
        except Exception:
            footer_top = y + 20
        try:
            pay_x = x
            # ensure payment block is below totals area
            pay_y = max(footer_top + 16, y + 8)
            draw.line((x, pay_y - 8, width - x, pay_y - 8), fill=(230, 230, 230), width=1)

            # align payment labels to the same right-aligned columns used for totals
            right_boundary = width - x
            p_label_x = right_boundary - 240
            p_value_x = right_boundary - 20

            draw.text((p_label_x, pay_y), f"Payment: {payment_method}", font=f_body, fill=(0, 0, 0))
            # Paid (right-aligned)
            if cash_given is not None:
                paid_txt = f"Paid: ₱ {float(cash_given):,.2f}"
                pw, ph = text_size(draw, paid_txt, f_body)
                draw.text((p_value_x - pw, pay_y), paid_txt, font=f_body, fill=(0, 0, 0))
            # Change on next line (right-aligned)
            if change_amount is not None:
                ch_txt = f"Change: ₱ {float(change_amount):,.2f}"
                ch_w, ch_h = text_size(draw, ch_txt, f_body)
                draw.text((p_value_x - ch_w, pay_y + line_h), ch_txt, font=f_body, fill=(0, 100, 0))

            # Footer thank you lines below payment
            try:
                ty = pay_y + line_h * 2 + 6
                draw.text((x, ty), "Thank you for shopping at Dale!", font=f_sub, fill=(80, 80, 80))
                draw.text((x, ty + 20), "Visit again.", font=f_sub, fill=(80, 80, 80))
            except Exception:
                pass
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
