from datetime import datetime
from typing import Optional, List

from model import Cart, Item, CartItem, OrderData
from database import DatabaseManager

import qrcode
import os

class QuickStopController:
    def __init__(self, view, db_manager: DatabaseManager):
        self.view = view
        self.db = db_manager
        self.cart = Cart()
        self.last_order_id: Optional[int] = None

        self.view.set_controller(self)
        self._init_categories()
        self.load_items(category="All")
        self._refresh_cart()

    #init 

    def _init_categories(self):
        categories = self.db.get_categories()
        categories = [c or "Others" for c in categories]
        categories = sorted(set(categories))

        if "Others" in categories:
            categories.remove("Others")
            categories.append("Others")

        if "Meals" not in categories:
            categories.append("Meals")
        if "Snacks" not in categories:
            categories.append("Snacks")
        if "Drinks" not in categories:
            categories.append("Drinks")
        if "Desserts" not in categories:
            categories.append("Desserts")

        if "All" not in categories:
            categories.insert(0, "All")
        self.view.build_category_buttons(categories)

    #items / categories

    def load_items(self, category: str = "All", search_text: str = ""):
        rows = self.db.get_items(
            category=None if category == "All" else category,
            search=search_text.strip() or None,
        )
        items: List[Item] = [
            Item(
                id=row["id"],
                name=row["name"],
                price=row["price"],
                stock=row["stock"],
                category=row["category"],
                active=row["active"],
            )
            for row in rows
        ]
        self.view.display_items(items, category)

    def handle_category_selected(self, category: str):
        self.view.set_active_category(category)
        search_text = self.view.get_search_text()
        self.load_items(category, search_text)

    def handle_search(self):
        category = self.view.current_category
        search_text = self.view.get_search_text()
        self.load_items(category, search_text)

    def handle_clear_search(self):
        self.view.clear_search_entry()
        self.load_items(self.view.current_category, "")

    #cart

    def _refresh_cart(self):
        items = self.cart.get_items()
        subtotal, vat_amount, total = self.cart.compute_totals()
        self.view.refresh_cart(items, subtotal, vat_amount, total)

    def handle_add_to_cart(self, item_id: int):
        row = self.db.get_item_by_id(item_id)
        if not row:
            self.view.show_error("Item not found.")
            return

        db_stock = row["stock"]
        current_qty = self.cart.get_item_quantity(item_id)

        if current_qty + 1 > db_stock:
            self.view.show_error("Not enough stock for this item.")
            return

        item = Item(
            id=row["id"],
            name=row["name"],
            price=row["price"],
            stock=row["stock"],
            category=row["category"],
            active=row["active"],
        )
        self.cart.add_item(item, 1)
        self._refresh_cart()

    def handle_cart_increase(self):
        item_id = self.view.get_selected_cart_item_id()
        if item_id is None:
            self.view.show_info("Please select an item from the cart first.")
            return

        row = self.db.get_item_by_id(item_id)
        if not row:
            self.view.show_error("Item not found.")
            return

        db_stock = row["stock"]
        current_qty = self.cart.get_item_quantity(item_id)

        if current_qty + 1 > db_stock:
            self.view.show_error("Not enough stock for this item.")
            return

        self.cart.increase_quantity(item_id, 1)
        self._refresh_cart()

    def handle_cart_decrease(self):
        item_id = self.view.get_selected_cart_item_id()
        if item_id is None:
            self.view.show_info("Please select an item from the cart first.")
            return
        self.cart.decrease_quantity(item_id, 1)
        self._refresh_cart()

    def handle_cart_remove_item(self):
        item_id = self.view.get_selected_cart_item_id()
        if item_id is None:
            self.view.show_info("Please select an item from the cart first.")
            return
        self.cart.remove_item(item_id)
        self._refresh_cart()

    def handle_cart_clear(self):
        if self.cart.is_empty():
            self.view.show_info("Cart is already empty.")
            return
        if self.view.ask_yes_no("Clear Cart", "Remove all items from the cart?"):
            self.cart.clear()
            self._refresh_cart()

    #checkout & payment

    def handle_checkout(self):
        if self.cart.is_empty():
            self.view.show_info("Cart is empty. Add items before checkout.")
            return
        subtotal, vat_amount, total = self.cart.compute_totals()
        self.view.open_payment_window(subtotal, vat_amount, total)

    def process_payment(self, payment_method: str, amount_given_str: str) -> bool:
        if self.cart.is_empty():
            self.view.show_error("Cart is empty.")
            return False

        try:
            amount_given = float(amount_given_str)
        except ValueError:
            self.view.show_error("Amount given must be a numeric value.")
            return False

        if amount_given <= 0:
            self.view.show_error("Amount given must be greater than 0.")
            return False

        subtotal, vat_amount, total = self.cart.compute_totals()
        if amount_given + 1e-6 < total:
            self.view.show_error("Insufficient payment amount.")
            return False

        change = round(amount_given - total, 2)

        items_snapshot = list(self.cart.get_items())
        order_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            order_id = self.db.insert_order(
                subtotal=subtotal,
                vat_amount=vat_amount,
                total_amount=total,
                payment_method=payment_method.upper(),
                cash_given=amount_given,
                change=change,
                order_datetime=order_datetime,
            )
            #Insert order_items and update stock
            for ci in items_snapshot:
                self.db.insert_order_item(
                    order_id=order_id,
                    item_id=ci.item.id,
                    quantity=ci.quantity,
                    unit_price=ci.item.price,
                    line_total=ci.line_total(),
                )

                row = self.db.get_item_by_id(ci.item.id)
                if row:
                    new_stock = max(0, row["stock"] - ci.quantity)
                    self.db.update_item_stock(ci.item.id, new_stock)

        except Exception as exc:
            self.view.show_error(f"Failed to save order: {exc}")
            return False

        self.last_order_id = order_id

        order_data = OrderData(
            id=order_id,
            order_datetime=order_datetime,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total_amount=total,
            payment_method=payment_method.upper(),
            cash_given=amount_given,
            change=change,
            items=items_snapshot,
        )

        qr_path = self.generate_qr_code(order_id)
        order_data.qr_path = qr_path

        self.cart.clear()
        self._refresh_cart()
        #refresh item tiles with updated stock
        self.load_items(self.view.current_category, self.view.get_search_text())

        self.view.show_receipt_window(order_data)
        return True

    #extras 
    def handle_cancel_order(self):
        if self.cart.is_empty():
            self.view.show_info("There is no active order to cancel.")
            return
        if self.view.ask_yes_no(
            "Cancel Order", "Cancel the current order and clear the cart?"
        ):
            self.cart.clear()
            self._refresh_cart()

    def handle_reprint_last_receipt(self):
        order_row, items_rows = self.db.get_last_order_with_items()
        if not order_row:
            self.view.show_info("No previous orders found.")
            return

        cart_items: List[CartItem] = []
        for r in items_rows:
            item = Item(
                id=r["item_id"],
                name=r["name"],
                price=r["unit_price"],
                stock=0,
                category=None,
            )
            cart_items.append(CartItem(item=item, quantity=r["quantity"]))

        order_data = OrderData(
            id=order_row["id"],
            order_datetime=order_row["order_datetime"],
            subtotal=order_row["subtotal"],
            vat_amount=order_row["vat_amount"],
            total_amount=order_row["total_amount"],
            payment_method=order_row["payment_method"],
            cash_given=order_row["cash_given"],
            change=order_row["change"],
            items=cart_items,
        )
        self.view.show_receipt_window(order_data)

    def handle_today_sales_summary(self):
        total = self.db.get_today_sales_total()
        self.view.show_info(f"Today's total sales: ₱ {total:,.2f}")

    def handle_admin_mode(self):
        #placeholder hehe
        self.view.show_info(
            "You can manage items directly in the databases."
        )
    
    def generate_qr_code(self, order_id: int) -> str:
        # Folder to store qr codes
        qr_folder = "qr_codes"
        os.makedirs(qr_folder, exist_ok=True)

        qr_data = f"ORDER_ID:{order_id}"
        file_path = os.path.join(qr_folder, f"receipt_qr_{order_id}.png")

        # Generate QR
        img = qrcode.make(qr_data)
        img.save(file_path)

        return file_path