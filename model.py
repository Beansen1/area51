from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

VAT_RATE = 0.12

class ReceiptGenerator:
    @staticmethod
    def generate(order_data, items_data):
        # Ensure directory exists
        if not os.path.exists("receipts"):
            os.makedirs("receipts")

        filename = f"receipts/{order_data['order_number']}"
        pdf_path = f"{filename}.pdf"
        png_path = f"{filename}.png"

        # 1. Generate PDF
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "QuickStop - Official Receipt")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, 730, f"Order #: {order_data['order_number']}")
        c.drawString(100, 715, f"Date: {order_data['order_datetime']}")
        c.drawString(100, 700, f"Payment: {order_data['payment_method']}")

        y = 670
        c.drawString(100, y, "Item")
        c.drawString(300, y, "Qty")
        c.drawString(350, y, "Price")
        c.drawString(450, y, "Total")
        y -= 20
        c.line(100, y+15, 500, y+15)

        for item in items_data:
            c.drawString(100, y, item['name'])
            c.drawString(300, y, str(item['quantity']))
            c.drawString(350, y, f"{item['unit_price']:.2f}")
            c.drawString(450, y, f"{item['line_total']:.2f}")
            y -= 20

        y -= 10
        c.line(100, y+15, 500, y+15)
        c.drawString(350, y, "Subtotal:")
        c.drawString(450, y, f"{order_data['subtotal']:.2f}")
        y -= 20
        c.drawString(350, y, "VAT (12%):")
        c.drawString(450, y, f"{order_data['vat_amount']:.2f}")
        y -= 20
        c.setFont("Helvetica-Bold", 14)
        c.drawString(350, y, "TOTAL:")
        c.drawString(450, y, f"PHP {order_data['total_amount']:.2f}")
        
        c.save()

        # 2. Generate PNG (Simple text render for speed)
        img = Image.new('RGB', (400, 600), color='white')
        d = ImageDraw.Draw(img)
        # Assuming default font exists, otherwise load a ttf
        try:
            fnt_head = ImageFont.truetype("arial.ttf", 20)
            fnt_body = ImageFont.truetype("arial.ttf", 12)
        except:
            fnt_head = ImageFont.load_default()
            fnt_body = ImageFont.load_default()

        d.text((10,10), "QuickStop Receipt", font=fnt_head, fill=(0,0,0))
        d.text((10,40), f"Order: {order_data['order_number']}", font=fnt_body, fill=(0,0,0))
        d.text((10,60), f"Total: {order_data['total_amount']:.2f}", font=fnt_head, fill=(0,0,0))
        img.save(png_path)

        return pdf_path, png_path
