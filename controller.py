from PyQt5.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QMessageBox, 
    QStackedWidget,  
    QDialog          
)
from PyQt5.QtCore import QTimer
from view import AttractScreen, KioskMain, PaymentDialog, VizPanel, AdminLoginDialog, AdminPanel
from database import db
from model import ReceiptGenerator
from datetime import datetime

class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickStop Kiosk")
        self.resize(1024, 768)
        
        # Data State
        self.cart = {} # {item_id: {data, qty}}
        self.current_cat_id = 0
        self.search_text = ""
        
        # Stack Setup
        self.stack = QStackedWidget()
        self.attract = AttractScreen()
        self.kiosk = KioskMain()
        self.viz = VizPanel()
        
        self.stack.addWidget(self.attract)
        self.stack.addWidget(self.kiosk)
        self.stack.addWidget(self.viz)
        
        self.setCentralWidget(self.stack)
        
        # Idle Timer (30s)
        self.idle_timer = QTimer()
        self.idle_timer.setInterval(30000)
        self.idle_timer.timeout.connect(self.reset_to_attract)
        self.idle_timer.start()
        
        # Connect Signals
        self.attract.start_clicked.connect(self.start_ordering)
        self.kiosk.category_selected.connect(self.filter_category)
        self.kiosk.search_query.connect(self.filter_search)
        self.kiosk.item_added.connect(self.add_to_cart)
        self.kiosk.update_qty.connect(self.update_cart_qty)
        self.kiosk.remove_item.connect(self.remove_from_cart)
        self.kiosk.checkout_requested.connect(self.initiate_checkout)
        self.kiosk.insights_clicked.connect(lambda: self.stack.setCurrentWidget(self.viz))
        # VizPanel has Back/Exit signals to return to kiosk or return to attract
        try:
            self.viz.back_clicked.connect(lambda: self.stack.setCurrentWidget(self.kiosk))
            # Do NOT quit application on Insights exit; return to attract screen instead
            self.viz.exit_clicked.connect(self.reset_to_attract)
        except Exception:
            pass
        self.kiosk.admin_clicked.connect(self.open_admin_login)
        
        # Global Event Filter for Idle Reset would go here
        
        # Initial Load
        self.load_categories()
        self.load_items()

    def reset_timer(self):
        self.idle_timer.start(30000)

    # --- NAV ---
    def reset_to_attract(self):
        self.cart.clear()
        self.update_cart_ui()
        self.stack.setCurrentWidget(self.attract)

    def start_ordering(self):
        self.reset_timer()
        self.stack.setCurrentWidget(self.kiosk)

    # --- DATA ---
    def load_categories(self):
        conn = db.connect()
        cats = conn.execute("SELECT * FROM categories").fetchall()
        self.kiosk.populate_categories(cats)
        conn.close()

    def load_items(self):
        conn = db.connect()
        query = "SELECT * FROM items WHERE active=1"
        params = []
        
        if self.current_cat_id != 0:
            query += " AND category_id = ?"
            params.append(self.current_cat_id)
            
        if self.search_text:
            query += " AND name LIKE ?"
            params.append(f"%{self.search_text}%")
            
        items = conn.execute(query, params).fetchall()
        self.kiosk.update_grid(items)
        conn.close()

    def filter_category(self, cat_id):
        self.current_cat_id = cat_id
        self.load_items()
        self.reset_timer()

    def filter_search(self, text):
        self.search_text = text
        self.load_items()
        self.reset_timer()

    # --- CART LOGIC ---
    def add_to_cart(self, item_id):
        self.reset_timer()
        conn = db.connect()
        item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        conn.close()
        
        current_qty = self.cart.get(item_id, {}).get('qty', 0)
        
        if current_qty + 1 > item['stock']:
            QMessageBox.warning(self, "Stock Limit", "Not enough stock available.")
            return

        if item_id in self.cart:
            self.cart[item_id]['qty'] += 1
        else:
            self.cart[item_id] = {'data': item, 'qty': 1}
            
        self.update_cart_ui()

    def update_cart_qty(self, item_id, change):
        self.reset_timer()
        if item_id in self.cart:
            new_qty = self.cart[item_id]['qty'] + change
            if new_qty <= 0:
                del self.cart[item_id]
            else:
                # Check stock cap
                conn = db.connect()
                stock = conn.execute("SELECT stock FROM items WHERE id=?", (item_id,)).fetchone()['stock']
                conn.close()
                if new_qty > stock:
                    return # Silent fail or warn
                self.cart[item_id]['qty'] = new_qty
            self.update_cart_ui()

    def remove_from_cart(self, item_id):
        self.reset_timer()
        if item_id in self.cart:
            del self.cart[item_id]
            self.update_cart_ui()

    def update_cart_ui(self):
        display_list = []
        subtotal = 0.0
        
        for iid, info in self.cart.items():
            qty = info['qty']
            price = info['data']['price']
            subtotal += price * qty
            display_list.append({
                'id': iid,
                'name': info['data']['name'],
                'price': price,
                'quantity': qty
            })
            
        vat = subtotal * 0.12
        total = subtotal + vat
        
        self.kiosk.update_cart_display(display_list, {'subtotal':subtotal, 'vat':vat, 'total':total})

    # --- CHECKOUT ---
    def initiate_checkout(self):
        self.reset_timer()
        if not self.cart:
            return
            
        # Calc totals
        subtotal = sum(i['data']['price'] * i['qty'] for i in self.cart.values())
        vat = subtotal * 0.12
        total = subtotal + vat

        # Build a readable summary of everything in the cart for confirmation
        lines = []
        for iid, info in self.cart.items():
            name = info['data']['name']
            qty = info['qty']
            price = info['data']['price']
            line_total = price * qty
            lines.append(f"{name} x{qty} @ {price:.2f} = {line_total:.2f}")

        items_text = "\n".join(lines)
        summary = f"Please review your cart before proceeding to payment:\n\n{items_text}\n\nSubtotal: {subtotal:.2f}\nVAT (12%): {vat:.2f}\nTotal: {total:.2f}"

        # Ask for confirmation
        resp = QMessageBox.question(self, "Confirm Order", summary, QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        # Proceed to payment dialog after confirmation
        dlg = PaymentDialog(total)
        if dlg.exec_() == QDialog.Accepted:
            self.process_transaction(dlg.payment_data, subtotal, vat, total)

    def process_transaction(self, pay_data, subtotal, vat, total):
        conn = db.connect()
        try:
            # 1. Create Order
            order_num = f"QS-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp())}"
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (order_number, order_datetime, subtotal, vat_amount, total_amount, payment_method, cash_given, change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_num, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), subtotal, vat, total, pay_data['method'], pay_data['cash_given'], pay_data['change']))
            order_id = cursor.lastrowid
            
            # 2. Insert Items & Update Stock
            items_for_receipt = []
            
            for iid, info in self.cart.items():
                qty = info['qty']
                price = info['data']['price']
                line_total = price * qty
                
                # Add to order_items
                cursor.execute("INSERT INTO order_items (order_id, item_id, quantity, unit_price, line_total) VALUES (?,?,?,?,?)", 
                               (order_id, iid, qty, price, line_total))
                
                # Update Stock
                cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (qty, iid))
                
                # Log Movement
                cursor.execute("INSERT INTO stock_movements (item_id, change, reason, created_at) VALUES (?, ?, 'sale', ?)",
                               (iid, -qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                
                items_for_receipt.append({
                    'name': info['data']['name'],
                    'quantity': qty,
                    'unit_price': price,
                    'line_total': line_total
                })

            conn.commit()
            
            # 3. Generate Receipt (PNG only)
            order_info = {
                'order_number': order_num,
                'order_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'payment_method': pay_data['method'],
                'subtotal': subtotal,
                'vat_amount': vat,
                'total_amount': total
            }
            png = ReceiptGenerator.generate(order_info, items_for_receipt)

            # Update DB with png path (no PDF)
            cursor.execute("UPDATE orders SET receipt_png_path=? WHERE id=?", (png, order_id))
            conn.commit()

            QMessageBox.information(self, "Success", "Order Placed Successfully!\nPreparing receipt...")

            # Show receipt dialog (png preview)
            try:
                from view import ReceiptDialog
                dlg = ReceiptDialog(pdf_path=None, png_path=png)
                dlg.exec_()
            except Exception:
                pass
            
            # Reset
            self.cart.clear()
            self.update_cart_ui()
            self.load_items() # Refresh stock display
            self.reset_to_attract()
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Transaction failed: {str(e)}")
        finally:
            conn.close()

    # --- ADMIN / SUPER-ADMIN ---
    def open_admin_login(self):
        dlg = AdminLoginDialog()
        if dlg.exec_() != QDialog.Accepted:
            return

        username = dlg.input_user.text().strip()
        password = dlg.input_pass.text().strip()

        conn = db.connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
            if not row:
                QMessageBox.warning(self, "Login Failed", "User not found or inactive")
                return
            # Verify password
            from passlib.hash import bcrypt
            if not bcrypt.verify(password, row['password_hash']):
                QMessageBox.warning(self, "Login Failed", "Invalid credentials")
                return

            # Open admin panel based on role
            role = row['role']
            if role == 'super_admin':
                self.open_admin_panel(role='super_admin')
            elif role == 'admin':
                # admin can only adjust stock
                self.open_admin_panel(role='admin')
            else:
                QMessageBox.warning(self, "Unauthorized", "Admin access required")
                return
        finally:
            conn.close()

    def open_admin_panel(self, role='super_admin'):
        panel = AdminPanel()

        # Load categories and items
        conn = db.connect()
        cats = conn.execute("SELECT * FROM categories").fetchall()
        categories = [dict(c) for c in cats]
        panel.load_categories(categories)

        items = conn.execute("SELECT i.*, c.name as category_name FROM items i LEFT JOIN categories c ON i.category_id=c.id").fetchall()
        items_list = [dict(i) for i in items]
        panel.populate_items(items_list)
        conn.close()

        # Connect signals
        # Super admin: full access. Admin: only stock adjust.
        if role == 'super_admin':
            panel.add_item.connect(self.admin_create_item)
            panel.edit_item.connect(self.admin_update_item)
            panel.delete_item.connect(self.admin_delete_item)
        else:
            # hide create/edit/delete controls for limited admin
            try:
                panel.btn_add.hide()
                panel.btn_edit.hide()
                panel.btn_del.hide()
            except Exception:
                pass

        # Both roles can adjust stock via the adjust_stock signal
        panel.adjust_stock.connect(self.admin_adjust_stock)

        # Connect navigation: Back returns to kiosk, Exit quits app
        panel.back_clicked.connect(lambda: self._close_dynamic_panel(panel))
        # Don't quit the whole app; exit should return to attract/reset state and remove panel
        panel.exit_clicked.connect(lambda p=panel: (self._close_dynamic_panel(p), self.reset_to_attract()))

        # Add the admin panel into the main stack so it replaces kiosk view
        self.stack.addWidget(panel)
        self.stack.setCurrentWidget(panel)

    def _close_dynamic_panel(self, panel):
        # Return to kiosk and remove the dynamic panel from the stack
        try:
            self.stack.setCurrentWidget(self.kiosk)
        except Exception:
            pass
        try:
            self.stack.removeWidget(panel)
            panel.deleteLater()
        except Exception:
            pass
        # Refresh items in kiosk
        try:
            self.load_items()
        except Exception:
            pass

    def admin_create_item(self, payload):
        # payload: {name, price, stock, category_id, image_path}
        conn = db.connect()
        cur = conn.cursor()
        try:
            img_path = payload.get('image_path')
            saved_path = None
            raw_bytes = None
            if img_path:
                saved_path, raw_bytes = self._save_image_file(img_path)

            # Insert into items, storing image bytes into the BLOB 'image' column
            cur.execute("INSERT INTO items (name, price, stock, category_id, image) VALUES (?,?,?,?,?)",
                        (payload['name'], payload['price'], payload['stock'], payload['category_id'], raw_bytes))
            conn.commit()
            QMessageBox.information(self, "Success", "Item added")
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to add item: {e}")
        finally:
            conn.close()

    def admin_adjust_stock(self, item_id, new_stock):
        """Set stock for an item to a specific value `new_stock` (typed by admin).
        The method computes the delta (new - current) and records that change.
        """
        try:
            conn = db.connect()
            cur = conn.cursor()
            row = conn.execute("SELECT stock FROM items WHERE id=?", (item_id,)).fetchone()
            if not row:
                QMessageBox.warning(self, "Not Found", "Item not found")
                return

            current = int(row['stock'])
            try:
                new_stock_val = int(new_stock)
            except Exception:
                QMessageBox.warning(self, "Invalid Value", "Please enter a valid integer for stock")
                return

            if new_stock_val < 0:
                new_stock_val = 0

            delta = new_stock_val - current

            cur.execute("UPDATE items SET stock=? WHERE id=?", (new_stock_val, item_id))
            cur.execute(
                "INSERT INTO stock_movements (item_id, change, reason, created_at) VALUES (?, ?, ?, ?)",
                (item_id, delta, 'manual_adjust', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            QMessageBox.information(self, "Success", f"Stock updated: {current} -> {new_stock_val}")

            # Refresh kiosk display
            try:
                self.load_items()
            except Exception:
                pass
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to update stock: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def admin_update_item(self, item_id, payload):
        conn = db.connect()
        cur = conn.cursor()
        try:
            img_path = payload.get('image_path')
            saved_path = None
            raw_bytes = None
            if img_path:
                saved_path, raw_bytes = self._save_image_file(img_path)

            if raw_bytes is not None:
                cur.execute("UPDATE items SET name=?, price=?, stock=?, category_id=?, image=? WHERE id=?",
                            (payload['name'], payload['price'], payload['stock'], payload['category_id'], raw_bytes, item_id))
            else:
                cur.execute("UPDATE items SET name=?, price=?, stock=?, category_id=? WHERE id=?",
                            (payload['name'], payload['price'], payload['stock'], payload['category_id'], item_id))
            conn.commit()
            QMessageBox.information(self, "Success", "Item updated")
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update item: {e}")
        finally:
            conn.close()

    def admin_delete_item(self, item_id):
        conn = db.connect()
        try:
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            conn.commit()
            QMessageBox.information(self, "Deleted", "Item deleted")
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete item: {e}")
        finally:
            conn.close()

    def _save_image_file(self, src_path):
        import os, shutil
        # Ensure assets/images exists
        dest_dir = os.path.join('assets', 'images')
        os.makedirs(dest_dir, exist_ok=True)
        try:
            basename = os.path.basename(src_path)
            dest_path = os.path.join(dest_dir, basename)
            shutil.copy(src_path, dest_path)
            # Read raw bytes to store in the DB blob column
            try:
                with open(dest_path, 'rb') as f:
                    raw = f.read()
            except Exception:
                raw = None
            return dest_path, raw
        except Exception:
            # If we couldn't copy, attempt to read the original path
            try:
                with open(src_path, 'rb') as f:
                    raw = f.read()
                return src_path, raw
            except Exception:
                return src_path, None
