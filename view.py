import os
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk
from tkinter import messagebox

from model import Item, CartItem, OrderData

#Optional libraries for export
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas
except ImportError:
    pdf_canvas = None

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


class QuickStopView(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("QuickStop")
        self.geometry("1200x700")

        self.controller = None
        self.current_category: str = "All"
        self._selected_cart_item_id: Optional[int] = None

        self.search_var = ctk.StringVar()

        self._build_layout()

    #wiring 

    def set_controller(self, controller):
        self.controller = controller

    #layout

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        #Left: categories + items
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)

        #Right: cart + checkout
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)

        #search bar
        search_frame = ctk.CTkFrame(self.left_frame)
        search_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        search_frame.grid_columnconfigure(0, weight=1)

        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="Search item name...",
            font=ctk.CTkFont(size=16),
        )
        search_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        search_btn = ctk.CTkButton(
            search_frame,
            text="Search",
            command=self._on_search_click,
            height=40,
            width=80,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        search_btn.grid(row=0, column=1, padx=5, pady=5)

        clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            command=self._on_clear_search_click,
            height=40,
            width=80,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        clear_btn.grid(row=0, column=2, padx=5, pady=5)

        #category buttons
        self.category_frame = ctk.CTkFrame(self.left_frame)
        self.category_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.category_frame.grid_columnconfigure(0, weight=1)
        self.category_buttons = {}

        #item tiles
        self.items_frame = ctk.CTkScrollableFrame(self.left_frame, label_text="Items")
        self.items_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        #cart header
        cart_header = ctk.CTkLabel(
            self.right_frame,
            text="Cart",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        cart_header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        #cart items 
        self.cart_items_frame = ctk.CTkScrollableFrame(self.right_frame)
        self.cart_items_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        #totals
        totals_frame = ctk.CTkFrame(self.right_frame)
        totals_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        totals_frame.grid_columnconfigure(0, weight=1)

        self.subtotal_label = ctk.CTkLabel(
            totals_frame, text="Subtotal: ₱ 0.00", font=ctk.CTkFont(size=16)
        )
        self.subtotal_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.vat_label = ctk.CTkLabel(
            totals_frame, text="VAT (12%): ₱ 0.00", font=ctk.CTkFont(size=16)
        )
        self.vat_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        self.total_label = ctk.CTkLabel(
            totals_frame,
            text="Grand Total: ₱ 0.00",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.total_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)

        #cart buttons
        buttons_frame = ctk.CTkFrame(self.right_frame)
        buttons_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        for i in range(3):
            buttons_frame.grid_columnconfigure(i, weight=1)
        for i in range(3, 6):
            buttons_frame.grid_columnconfigure(i, weight=1)

        self.plus_btn = ctk.CTkButton(
            buttons_frame,
            text="+",
            command=self._on_cart_increase,
            height=45,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.plus_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.minus_btn = ctk.CTkButton(
            buttons_frame,
            text="−",
            command=self._on_cart_decrease,
            height=45,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.minus_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.remove_btn = ctk.CTkButton(
            buttons_frame,
            text="Remove Item",
            command=self._on_cart_remove_item,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.remove_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.clear_btn = ctk.CTkButton(
            buttons_frame,
            text="Clear Cart",
            command=self._on_cart_clear,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.clear_btn.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.checkout_btn = ctk.CTkButton(
            buttons_frame,
            text="Checkout",
            command=self._on_checkout,
            height=45,
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.checkout_btn.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Cancel Order",
            command=self._on_cancel_order,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.cancel_btn.grid(row=1, column=2, padx=5, pady=5, sticky="ew")

        self.reprint_btn = ctk.CTkButton(
            buttons_frame,
            text="Reprint Last Receipt",
            command=self._on_reprint_last,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.reprint_btn.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        self.today_sales_btn = ctk.CTkButton(
            buttons_frame,
            text="Today's Sales",
            command=self._on_today_sales,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.today_sales_btn.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        self.admin_btn = ctk.CTkButton(
            buttons_frame,
            text="Admin",
            command=self._on_admin,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.admin_btn.grid(row=2, column=2, padx=5, pady=5, sticky="ew")

    #category bar & items 

    def build_category_buttons(self, categories: List[str]):
        for w in self.category_frame.winfo_children():
            w.destroy()
        self.category_buttons.clear()

        for i, cat in enumerate(categories):
            btn = ctk.CTkButton(
                self.category_frame,
                text=cat,
                command=lambda c=cat: self._on_category_click(c),
                height=45,
                font=ctk.CTkFont(size=18, weight="bold"),
            )
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            self.category_buttons[cat] = btn

        if categories:
            self.set_active_category(categories[0])

    def set_active_category(self, category: str):
        self.current_category = category
        for cat, btn in self.category_buttons.items():
            if cat == category:
                btn.configure(fg_color="#1f6aa5")
            else:
                btn.configure(fg_color='transparent')

    def display_items(self, items: List[Item], category: str):
        for w in self.items_frame.winfo_children():
            w.destroy()

        columns = 3
        for idx, item in enumerate(items):
            row = idx // columns
            col = idx % columns

            text_lines = [
                item.name,
                f"₱ {item.price:,.2f}",
                f"Stock: {item.stock}",
            ]

            if item.stock == 0:
                text_lines.append("OUT OF STOCK")
            elif 0 < item.stock < 5:
                text_lines.append("LOW STOCK")

            tile_text = "\n".join(text_lines)

            state = "normal"
            fg_color = None
            if item.stock == 0:
                state = "disabled"
                fg_color = "gray"

            btn = ctk.CTkButton(
                self.items_frame,
                text=tile_text,
                width=180,
                height=180,
                state=state,
                font=ctk.CTkFont(size=16),
                command=lambda iid=item.id: self._on_item_tile_click(iid),
            )
            if fg_color is not None:
                btn.configure(fg_color=fg_color)
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    #cart display

    def refresh_cart(
        self,
        cart_items: List[CartItem],
        subtotal: float,
        vat_amount: float,
        total: float,
    ):
        #Keep selection if item still exists
        item_ids = [ci.item.id for ci in cart_items]
        if self._selected_cart_item_id not in item_ids:
            self._selected_cart_item_id = None

        for w in self.cart_items_frame.winfo_children():
            w.destroy()

        for idx, ci in enumerate(cart_items):
            item_id = ci.item.id
            text = (
                f"{ci.item.name} x{ci.quantity}\n"
                f"₱ {ci.item.price:,.2f} ea | Line: ₱ {ci.line_total():,.2f}"
            )

            btn = ctk.CTkButton(
                self.cart_items_frame,
                text=text,
                anchor="w",
                height=60,
                font=ctk.CTkFont(size=15),
                command=lambda iid=item_id: self._on_cart_item_clicked(iid),
            )
            if item_id == self._selected_cart_item_id:
                btn.configure(fg_color="#1f6aa5")
            btn.grid(row=idx, column=0, sticky="ew", padx=5, pady=3)

        self.subtotal_label.configure(text=f"Subtotal: ₱ {subtotal:,.2f}")
        self.vat_label.configure(text=f"VAT (12%): ₱ {vat_amount:,.2f}")
        self.total_label.configure(text=f"Grand Total: ₱ {total:,.2f}")

    def get_selected_cart_item_id(self) -> Optional[int]:
        return self._selected_cart_item_id

    #helper: search

    def get_search_text(self) -> str:
        return self.search_var.get()

    def clear_search_entry(self):
        self.search_var.set("")

    #message helpers

    def show_info(self, message: str, title: str = "Info"):
        messagebox.showinfo(title, message)

    def show_error(self, message: str, title: str = "Error"):
        messagebox.showerror(title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    #payment & receipt

    def open_payment_window(self, subtotal: float, vat_amount: float, total: float):
        PaymentWindow(self, self.controller, subtotal, vat_amount, total)

    def show_receipt_window(self, order_data: OrderData):
        ReceiptWindow(self, order_data)

    #internal callbacks

    def _on_category_click(self, category: str):
        if self.controller:
            self.controller.handle_category_selected(category)

    def _on_search_click(self):
        if self.controller:
            self.controller.handle_search()

    def _on_clear_search_click(self):
        if self.controller:
            self.controller.handle_clear_search()

    def _on_item_tile_click(self, item_id: int):
        if self.controller:
            self.controller.handle_add_to_cart(item_id)

    def _on_cart_item_clicked(self, item_id: int):
        self._selected_cart_item_id = item_id
        #Force redraw to update highlight
        if self.controller:
            self.controller._refresh_cart()

    def _on_cart_increase(self):
        if self.controller:
            self.controller.handle_cart_increase()

    def _on_cart_decrease(self):
        if self.controller:
            self.controller.handle_cart_decrease()

    def _on_cart_remove_item(self):
        if self.controller:
            self.controller.handle_cart_remove_item()

    def _on_cart_clear(self):
        if self.controller:
            self.controller.handle_cart_clear()

    def _on_checkout(self):
        if self.controller:
            self.controller.handle_checkout()

    def _on_cancel_order(self):
        if self.controller:
            self.controller.handle_cancel_order()

    def _on_reprint_last(self):
        if self.controller:
            self.controller.handle_reprint_last_receipt()

    def _on_today_sales(self):
        if self.controller:
            self.controller.handle_today_sales_summary()

    def _on_admin(self):
        if self.controller:
            self.controller.handle_admin_mode()



#Payment window!!!



class PaymentWindow(ctk.CTkToplevel):
    def __init__(
        self,
        master: QuickStopView,
        controller,
        subtotal: float,
        vat_amount: float,
        total: float,
    ):
        super().__init__(master)
        self.title("QuickStop – Payment")
        self.geometry("500x420")
        self.resizable(False, False)

        self.master: QuickStopView = master
        self.controller = controller

        self.subtotal = subtotal
        self.vat_amount = vat_amount
        self.total = total

        self.payment_method = ctk.StringVar(value="CASH")
        self.amount_var = ctk.StringVar()

        self._build_ui()
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        padding = {"padx": 15, "pady": 8}

        title_lbl = ctk.CTkLabel(
            self,
            text="Payment",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title_lbl.grid(row=0, column=0, columnspan=2, **padding)

        subtotal_lbl = ctk.CTkLabel(
            self,
            text=f"Subtotal: ₱ {self.subtotal:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        subtotal_lbl.grid(row=1, column=0, columnspan=2, sticky="w", **padding)

        vat_lbl = ctk.CTkLabel(
            self,
            text=f"VAT (12%): ₱ {self.vat_amount:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        vat_lbl.grid(row=2, column=0, columnspan=2, sticky="w", **padding)

        total_lbl = ctk.CTkLabel(
            self,
            text=f"Grand Total: ₱ {self.total:,.2f}",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        total_lbl.grid(row=3, column=0, columnspan=2, sticky="w", **padding)

        #payment method
        pm_frame = ctk.CTkFrame(self)
        pm_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **padding)

        cash_rb = ctk.CTkRadioButton(
            pm_frame,
            text="Cash",
            variable=self.payment_method,
            value="CASH",
            font=ctk.CTkFont(size=16),
        )
        cash_rb.grid(row=0, column=0, padx=10, pady=5)

        cashless_rb = ctk.CTkRadioButton(
            pm_frame,
            text="Cashless (Wallet)",
            variable=self.payment_method,
            value="CASHLESS",
            font=ctk.CTkFont(size=16),
        )
        cashless_rb.grid(row=0, column=1, padx=10, pady=5)

        #amount to pay
        amount_lbl = ctk.CTkLabel(
            self,
            text="Amount Given (₱):",
            font=ctk.CTkFont(size=16),
        )
        amount_lbl.grid(row=5, column=0, sticky="e", **padding)

        amount_entry = ctk.CTkEntry(
            self,
            textvariable=self.amount_var,
            font=ctk.CTkFont(size=18),
        )
        amount_entry.grid(row=5, column=1, sticky="w", **padding)

        self.change_label = ctk.CTkLabel(
            self,
            text="Change: ₱ 0.00",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.change_label.grid(row=6, column=0, columnspan=2, sticky="w", **padding)

        #buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="ew", **padding)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Confirm Payment",
            command=self._on_confirm,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        confirm_btn.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            height=45,
            font=ctk.CTkFont(size=16),
        )
        cancel_btn.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

    def _on_confirm(self):
        amount_str = self.amount_var.get().strip()
        try:
            amount = float(amount_str)
        except ValueError:
            self.master.show_error("Please enter a valid numeric amount.")
            return

        if amount <= 0:
            self.master.show_error("Amount must be greater than 0.")
            return

        if amount + 1e-6 < self.total:
            self.master.show_error("Amount given is not enough.")
            return

        change = round(amount - self.total, 2)
        self.change_label.configure(text=f"Change: ₱ {change:,.2f}")

        success = self.controller.process_payment(
            self.payment_method.get(), amount_str
        )
        if success:
            self.destroy()



#Receipt window na hehe



class ReceiptWindow(ctk.CTkToplevel):
    def __init__(self, master: QuickStopView, order_data: OrderData):
        super().__init__(master)
        self.title("QuickStop – Official Receipt")
        self.geometry("600x700")
        self.resizable(False, False)

        self.master = master
        self.order_data = order_data

        self._build_ui()
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        padding = {"padx": 15, "pady": 5}

        title_lbl = ctk.CTkLabel(
            self,
            text="QuickStop – Official Receipt",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title_lbl.grid(row=0, column=0, columnspan=2, **padding)

        order_lbl = ctk.CTkLabel(
            self,
            text=f"Order ID: {self.order_data.id}",
            font=ctk.CTkFont(size=16),
        )
        order_lbl.grid(row=1, column=0, sticky="w", **padding)

        dt_lbl = ctk.CTkLabel(
            self,
            text=f"Date & Time: {self.order_data.order_datetime}",
            font=ctk.CTkFont(size=16),
        )
        dt_lbl.grid(row=2, column=0, sticky="w", **padding)

        pm_lbl = ctk.CTkLabel(
            self,
            text=f"Payment Method: {self.order_data.payment_method}",
            font=ctk.CTkFont(size=16),
        )
        pm_lbl.grid(row=3, column=0, sticky="w", **padding)

        # Items list
        items_frame = ctk.CTkScrollableFrame(self, label_text="Items")
        items_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=15, pady=10)
        self.grid_rowconfigure(4, weight=1)
        items_frame.grid_columnconfigure(0, weight=1)

        for idx, ci in enumerate(self.order_data.items):
            text = (
                f"{ci.item.name} x{ci.quantity} "
                f"(₱ {ci.item.price:,.2f} ea)  "
                f"Line: ₱ {ci.line_total():,.2f}"
            )
            lbl = ctk.CTkLabel(
                items_frame, text=text, anchor="w", font=ctk.CTkFont(size=15)
            )
            lbl.grid(row=idx, column=0, sticky="w", padx=5, pady=2)

        #totals
        totals_frame = ctk.CTkFrame(self)
        totals_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        totals_frame.grid_columnconfigure(0, weight=1)

        subtotal_lbl = ctk.CTkLabel(
            totals_frame,
            text=f"Subtotal: ₱ {self.order_data.subtotal:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        subtotal_lbl.grid(row=0, column=0, sticky="w", pady=2)

        vat_lbl = ctk.CTkLabel(
            totals_frame,
            text=f"VAT (12%): ₱ {self.order_data.vat_amount:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        vat_lbl.grid(row=1, column=0, sticky="w", pady=2)

        total_lbl = ctk.CTkLabel(
            totals_frame,
            text=f"Grand Total: ₱ {self.order_data.total_amount:,.2f}",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        total_lbl.grid(row=2, column=0, sticky="w", pady=4)

        paid_lbl = ctk.CTkLabel(
            totals_frame,
            text=f"Amount Paid: ₱ {self.order_data.cash_given:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        paid_lbl.grid(row=3, column=0, sticky="w", pady=2)

        change_lbl = ctk.CTkLabel(
            totals_frame,
            text=f"Change: ₱ {self.order_data.change:,.2f}",
            font=ctk.CTkFont(size=16),
        )
        change_lbl.grid(row=4, column=0, sticky="w", pady=2)

        # QR CODE DISPLAY
        if hasattr(self.order_data, "qr_path") and os.path.exists(self.order_data.qr_path):
            qr_img = Image.open(self.order_data.qr_path)
            qr_img = qr_img.resize((180, 180))

            qr_photo = ctk.CTkImage(light_image=qr_img, size=(180, 180))

            qr_label = ctk.CTkLabel(self, image=qr_photo, text="")
            qr_label.grid(row=6, column=0, columnspan=2, pady=10)

        thanks_lbl = ctk.CTkLabel(
            self,
            text="Thank you for shopping at QuickStop!",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        thanks_lbl.grid(row=7, column=0, columnspan=2, **padding)

        #Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=15, pady=10)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        pdf_btn = ctk.CTkButton(
            btn_frame,
            text="Save as PDF",
            command=self._save_as_pdf,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        pdf_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        png_btn = ctk.CTkButton(
            btn_frame,
            text="Save as PNG",
            command=self._save_as_png,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        png_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self.destroy,
            height=45,
            font=ctk.CTkFont(size=14),
        )
        close_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

    #export helpers

    def _ensure_receipts_dir(self) -> Path:
        p = Path("receipts")
        p.mkdir(exist_ok=True)
        return p

    def _save_as_pdf(self):
        if pdf_canvas is None:
            self.master.show_error(
                "reportlab is not installed.\nInstall it with:\n\npip install reportlab"
            )
            return

        directory = self._ensure_receipts_dir()
        filename = directory / f"receipt_{self.order_data.id}.pdf"

        c = pdf_canvas.Canvas(str(filename), pagesize=A4)
        width, height = A4
        y = height - 40

        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, y, "QuickStop – Official Receipt")
        y -= 30

        c.setFont("Helvetica", 12)
        c.drawString(40, y, f"Order ID: {self.order_data.id}")
        y -= 18
        c.drawString(40, y, f"Date & Time: {self.order_data.order_datetime}")
        y -= 18
        c.drawString(40, y, f"Payment Method: {self.order_data.payment_method}")
        y -= 30

        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Items:")
        y -= 18
        c.setFont("Helvetica", 11)

        for ci in self.order_data.items:
            line = (
                f"{ci.item.name} x{ci.quantity} "
                f"(₱ {ci.item.price:,.2f} ea)  "
                f"Line: ₱ {ci.line_total():,.2f}"
            )
            c.drawString(40, y, line)
            y -= 16
            if y < 80:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 11)

        y -= 10
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"Subtotal: ₱ {self.order_data.subtotal:,.2f}")
        y -= 16
        c.drawString(40, y, f"VAT (12%): ₱ {self.order_data.vat_amount:,.2f}")
        y -= 16
        c.drawString(40, y, f"Grand Total: ₱ {self.order_data.total_amount:,.2f}")
        y -= 16
        c.drawString(40, y, f"Amount Paid: ₱ {self.order_data.cash_given:,.2f}")
        y -= 16
        c.drawString(40, y, f"Change: ₱ {self.order_data.change:,.2f}")
        y -= 30
        c.drawString(40, y, "Thank you for shopping at QuickStop!")
        c.save()

        self.master.show_info(f"Receipt saved as PDF:\n{filename}")

    def _save_as_png(self):
        if Image is None:
            self.master.show_error(
                "Pillow (PIL) is not installed.\nInstall it with:\n\npip install pillow"
            )
            return

        directory = self._ensure_receipts_dir()
        filename = directory / f"receipt_{self.order_data.id}.png"

        #Simple text-only image
        img_width, img_height = 800, 1000
        img = Image.new("RGB", (img_width, img_height), "white")
        draw = ImageDraw.Draw(img)

        y = 20
        line_height = 22

        def draw_line(text: str, bold: bool = False):
            nonlocal y
            draw.text((20, y), text, fill="black")
            y += line_height

        draw_line("QuickStop – Official Receipt", bold=True)
        y += 10
        draw_line(f"Order ID: {self.order_data.id}")
        draw_line(f"Date & Time: {self.order_data.order_datetime}")
        draw_line(f"Payment Method: {self.order_data.payment_method}")
        y += 10
        draw_line("Items:", bold=True)

        for ci in self.order_data.items:
            line = (
                f"{ci.item.name} x{ci.quantity} "
                f"(₱ {ci.item.price:,.2f} ea)  "
                f"Line: ₱ {ci.line_total():,.2f}"
            )
            draw_line(line)

        y += 10
        draw_line(f"Subtotal: ₱ {self.order_data.subtotal:,.2f}")
        draw_line(f"VAT (12%): ₱ {self.order_data.vat_amount:,.2f}")
        draw_line(f"Grand Total: ₱ {self.order_data.total_amount:,.2f}")
        draw_line(f"Amount Paid: ₱ {self.order_data.cash_given:,.2f}")
        draw_line(f"Change: ₱ {self.order_data.change:,.2f}")
        y += 10
        draw_line("Thank you for shopping at QuickStop!", bold=True)

        img.save(filename)
        self.master.show_info(f"Receipt saved as PNG:\n{filename}")
