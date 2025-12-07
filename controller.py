from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QDialog,
    QLabel,
    QInputDialog,
    QLineEdit,
)
from PyQt5.QtCore import QTimer, Qt
from view import AttractScreen, KioskMain, PaymentDialog, VizPanel, AdminLoginDialog, AdminPanel
from database import db
from model import ReceiptGenerator
from datetime import datetime, timedelta
import copy
import sound as sfx
import sqlite3

class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dale Kiosk")
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
        
        # Idle Timer (3 minutes)
        # Centralized timeout value (milliseconds) so it's easy to adjust
        # Set to 180000 ms (3 minutes) to avoid premature auto-closing
        self.idle_timeout_ms = 180000
        self.idle_timer = QTimer()
        self.idle_timer.setInterval(self.idle_timeout_ms)
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
        # VizPanel has Back/Exit signals to return to kiosk or return to attract
        try:
            self.viz.back_clicked.connect(lambda: self.stack.setCurrentWidget(self.kiosk))
            # Do NOT quit application on Insights exit; return to attract screen instead
            self.viz.exit_clicked.connect(self.reset_to_attract)
        except Exception:
            pass
        self.kiosk.admin_clicked.connect(self.open_admin_login)

        # Undo stack to support undoing cart actions (store action entries)
        self._undo_stack = []
        # Connect clear/undo signals from kiosk
        try:
            self.kiosk.clear_cart_requested.connect(self.clear_cart)
            self.kiosk.undo_requested.connect(self.undo_last_action)
            # disable undo until there's something to undo
            try:
                self.kiosk.btn_undo.setEnabled(False)
            except Exception:
                pass
        except Exception:
            pass
        
        # Global Event Filter for Idle Reset would go here
        
        # Admin PIN protection state
        # PIN: 1188 (user requested). These values are in-memory only.
        self._admin_pin = '1188'
        self._admin_pin_attempts = 0
        self._admin_pin_max_attempts = 5
        self._admin_pin_lockout_until = None  # datetime when lockout expires
        self._admin_pin_lockout_minutes = 5
        # Admin username/password credential attempt tracking
        self._admin_cred_attempts = 0
        self._admin_cred_max_attempts = 5
        self._admin_cred_lockout_until = None
        # Currently authenticated admin (set after successful login)
        self._current_admin = None

        # reuse self._admin_pin_lockout_minutes as lockout duration for creds

        # Initial Load
        self.load_categories()
        self.load_items()
        # Preload sounds (best-effort). Requires Qt event loop to actually play.
        try:
            sfx.load_sounds()
        except Exception:
            pass

    def _write_audit(self, event_type, detail, username=None, role=None, retry=True):
        """Write a row into audit_logs. If table missing, attempt to create schema then retry once."""
        try:
            conn = db.connect()
            try:
                conn.execute("INSERT INTO audit_logs (username, role, event_type, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                             (username, role, event_type, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                try:
                    # If the insights panel is visible, refresh its data so UI reflects latest logs
                    try:
                        self.viz.refresh_charts()
                    except Exception:
                        pass
                except Exception:
                    pass
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if retry and ('no such table' in msg or 'no such column' in msg):
                try:
                    db.check_schema()
                except Exception:
                    pass
                # retry once
                try:
                    conn2 = db.connect()
                    try:
                        conn2.execute("INSERT INTO audit_logs (username, role, event_type, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                                      (username, role, event_type, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn2.commit()
                        try:
                            try:
                                self.viz.refresh_charts()
                            except Exception:
                                pass
                        except Exception:
                            pass
                    finally:
                        conn2.close()
                except Exception:
                    pass
            else:
                pass
        except Exception:
            pass

    def reset_timer(self):
        # Restart using centralized timeout value
        self.idle_timer.start(self.idle_timeout_ms)

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
        # Record previous quantity so undo can restore it
        prev_qty = self.cart.get(item_id, {}).get('qty', 0)
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

        # push undo action (set previous qty)
        try:
            self._undo_stack.append({'type': 'set', 'item_id': item_id, 'prev_qty': prev_qty})
            # enable undo button
            try:
                self.kiosk.btn_undo.setEnabled(True)
            except Exception:
                pass
        except Exception:
            pass

        self.update_cart_ui()

    def update_cart_qty(self, item_id, change):
        self.reset_timer()
        if item_id in self.cart:
            # Save previous qty for undo
            prev_qty = self.cart[item_id]['qty']
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
            # push undo action
            try:
                self._undo_stack.append({'type': 'set', 'item_id': item_id, 'prev_qty': prev_qty})
                try:
                    self.kiosk.btn_undo.setEnabled(True)
                except Exception:
                    pass
            except Exception:
                pass
            self.update_cart_ui()

    def remove_from_cart(self, item_id):
        self.reset_timer()
        if item_id in self.cart:
            # Save previous qty for undo
            prev_qty = self.cart[item_id]['qty']
            del self.cart[item_id]
            # push undo action
            try:
                self._undo_stack.append({'type': 'set', 'item_id': item_id, 'prev_qty': prev_qty})
                try:
                    self.kiosk.btn_undo.setEnabled(True)
                except Exception:
                    pass
            except Exception:
                pass
            self.update_cart_ui()

    def _push_undo_action(self, action):
        try:
            self._undo_stack.append(action)
            if len(self._undo_stack) > 50:
                self._undo_stack.pop(0)
            try:
                self.kiosk.btn_undo.setEnabled(True)
            except Exception:
                pass
        except Exception:
            pass

    def clear_cart(self):
        # Clear cart but allow undo
        if not self.cart:
            self.show_toast("Cart is already empty.")
            return
        # Ask for confirmation before clearing
        resp = QMessageBox.question(self, "Clear Cart", "Are you sure you want to clear the cart?", QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        # push undo action with full previous cart and clear
        try:
            prev = copy.deepcopy(self.cart)
            # Make clear a single undo boundary: discard older actions and keep only this one
            self._undo_stack = [{'type': 'clear', 'prev_cart': prev}]
            try:
                self.kiosk.btn_undo.setEnabled(True)
            except Exception:
                pass
        except Exception:
            pass
        self.cart.clear()
        self.update_cart_ui()
        self.show_toast("Cart cleared. You can undo this action.")

    def undo_last_action(self):
        # Restore last snapshot if available
        if not self._undo_stack:
            try:
                self.kiosk.btn_undo.setEnabled(False)
            except Exception:
                pass
            self.show_toast("Nothing to undo.")
            return
        try:
            action = self._undo_stack.pop()
            atype = action.get('type')
            if atype == 'set':
                iid = action.get('item_id')
                prev = int(action.get('prev_qty') or 0)
                if prev <= 0:
                    # remove item if exists
                    if iid in self.cart:
                        try:
                            del self.cart[iid]
                        except Exception:
                            pass
                else:
                    # restore previous qty; need item data for lookup
                    if iid in self.cart:
                        try:
                            self.cart[iid]['qty'] = prev
                        except Exception:
                            pass
                    else:
                        # attempt to fetch item data from DB to reconstruct entry
                        try:
                            conn = db.connect()
                            row = conn.execute('SELECT * FROM items WHERE id=?', (iid,)).fetchone()
                            conn.close()
                            if row:
                                self.cart[iid] = {'data': row, 'qty': prev}
                        except Exception:
                            pass
            elif atype == 'clear':
                prev_cart = action.get('prev_cart') or {}
                try:
                    self.cart = copy.deepcopy(prev_cart)
                except Exception:
                    self.cart = prev_cart or {}
            else:
                # unknown action type; ignore
                pass

            self.update_cart_ui()
            self.show_toast("Last action undone.")
            # disable undo if nothing left
            if not self._undo_stack:
                try:
                    self.kiosk.btn_undo.setEnabled(False)
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.warning(self, "Undo Failed", f"Could not undo: {e}")

    def show_toast(self, message, duration_ms=2200):
        """Show a temporary non-blocking toast label over the main window."""
        try:
            lbl = QLabel(message, self)
            lbl.setObjectName('ToastLabel')
            lbl.setStyleSheet("""
                QLabel#ToastLabel {
                    background-color: rgba(0,0,0,0.78);
                    color: white;
                    padding: 10px 14px;
                    border-radius: 8px;
                    font-size: 10pt;
                }
            """)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl.adjustSize()
            w = lbl.width()
            h = lbl.height()
            # place above bottom-right, with margin
            margin_x = 20
            margin_y = 100
            x = max(10, self.width() - w - margin_x)
            y = max(10, self.height() - h - margin_y)
            lbl.move(x, y)
            lbl.show()
            lbl.raise_()

            def _hide():
                try:
                    lbl.hide()
                    lbl.deleteLater()
                except Exception:
                    pass

            QTimer.singleShot(duration_ms, _hide)
        except Exception:
            # fallback to messagebox if toast fails
            try:
                QMessageBox.information(self, "Info", message)
            except Exception:
                pass

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
            # positive checkout: play confirmation sound
            try:
                sfx.play('Correct_or_Payment')
            except Exception:
                pass
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
                'total_amount': total,
                # include payment details so receipt can show paid amount and change
                'cash_given': pay_data.get('cash_given'),
                'change': pay_data.get('change')
            }
            png = ReceiptGenerator.generate(order_info, items_for_receipt)

            # Update DB with png path (no PDF)
            cursor.execute("UPDATE orders SET receipt_png_path=? WHERE id=?", (png, order_id))
            conn.commit()

            QMessageBox.information(self, "Success", "Order Placed Successfully!\nPreparing receipt...")

            # Play receipt printing sound (use the specific supplied file if present)
            try:
                sfx.play('Receipt_Printing')
            except Exception:
                pass

            # Show receipt dialog after the print sound finishes (sync visual with audio)
            try:
                from view import ReceiptDialog

                def _show_receipt():
                    try:
                        dlg = ReceiptDialog(png_path=png)
                        dlg.exec_()
                    except Exception:
                        pass

                # Get duration (seconds) of the Receipt_Printing wav if available
                dur = None
                try:
                    dur = sfx.get_duration('Receipt_Printing')
                except Exception:
                    dur = None
                # fallback to a sensible default (0.8s)
                delay_ms = int((dur if dur and dur > 0 else 0.8) * 1000)
                # schedule dialog after delay (non-blocking)
                try:
                    # Show a small transient cue centered on the main window
                    try:
                        cue = QDialog(self)
                        cue.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
                        cue.setAttribute(Qt.WA_TranslucentBackground)
                        cue_lbl = QLabel("Printing receipt...", cue)
                        cue_lbl.setStyleSheet("background-color: rgba(0,0,0,200); color: white; padding: 10px 14px; border-radius: 6px; font-size: 14px;")
                        from PyQt5.QtWidgets import QVBoxLayout
                        l = QVBoxLayout(cue)
                        l.setContentsMargins(0,0,0,0)
                        l.addWidget(cue_lbl)
                        cue.adjustSize()
                        # center on main window
                        try:
                            geo = self.geometry()
                            cx = geo.x() + (geo.width() - cue.width()) // 2
                            cy = geo.y() + (geo.height() - cue.height()) // 2
                            cue.move(cx, cy)
                        except Exception:
                            pass
                        cue.show()
                    except Exception:
                        cue = None

                    def _hide_cue():
                        try:
                            if cue is not None:
                                cue.close()
                        except Exception:
                            pass

                    QTimer.singleShot(delay_ms, _hide_cue)
                    QTimer.singleShot(delay_ms, _show_receipt)
                except Exception:
                    # last resort: show immediately
                    _show_receipt()
            except Exception:
                pass
            
            # Reset
            # clear undo history after a successful transaction
            try:
                self._undo_stack.clear()
            except Exception:
                pass
            self.cart.clear()
            self.update_cart_ui()
            self.load_items() # Refresh stock display
            self.reset_to_attract()
            
        except Exception as e:
            conn.rollback()
            try:
                sfx.play('Wrong')
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Transaction failed: {str(e)}")
        finally:
            conn.close()

    # --- ADMIN / SUPER-ADMIN ---
    def open_admin_login(self):
        # PIN protection: require a correct PIN before showing username/password dialog
        try:
            now = datetime.now()
            if self._admin_pin_lockout_until and now < self._admin_pin_lockout_until:
                remaining = self._admin_pin_lockout_until - now
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                QMessageBox.warning(self, "Locked", f"Admin login locked. Try again in {mins}m {secs}s")
                return

            # Require numeric-only PIN input. Use a masked input dialog that only accepts digits.
            from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton
            from PyQt5.QtGui import QIntValidator

            class MaskedPinDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle('Admin PIN')
                    self.setFixedSize(360, 120)
                    layout = QVBoxLayout()
                    form = QFormLayout()
                    self.input_pin = QLineEdit()
                    self.input_pin.setEchoMode(QLineEdit.Password)
                    self.input_pin.setValidator(QIntValidator(0, 99999999, self))
                    self.input_pin.setMaxLength(4)
                    form.addRow('Enter PIN:', self.input_pin)
                    layout.addLayout(form)
                    btn_row = QHBoxLayout()
                    btn_row.addStretch()
                    btn_ok = QPushButton('OK')
                    btn_cancel = QPushButton('Cancel')
                    btn_ok.clicked.connect(self.accept)
                    btn_cancel.clicked.connect(self.reject)
                    btn_row.addWidget(btn_ok)
                    btn_row.addWidget(btn_cancel)
                    layout.addLayout(btn_row)
                    self.setLayout(layout)

                def pin_text(self):
                    return self.input_pin.text() or ''

            pd = MaskedPinDialog(self)
            if pd.exec_() != QDialog.Accepted:
                return

            pin_val = pd.pin_text().strip()
            # enforce exact 4-digit PIN
            if len(pin_val) != 4:
                # treat as incorrect PIN entry
                self._admin_pin_attempts += 1
                remaining_attempts = self._admin_pin_max_attempts - self._admin_pin_attempts
                if remaining_attempts <= 0:
                    # lockout
                    self._admin_pin_lockout_until = datetime.now() + timedelta(minutes=self._admin_pin_lockout_minutes)
                    self._admin_pin_attempts = 0
                    try:
                        sfx.play('Wrong')
                    except Exception:
                        pass
                    QMessageBox.warning(self, "Locked", f"Too many attempts. Admin login locked for {self._admin_pin_lockout_minutes} minutes.")
                    return
                else:
                    try:
                        sfx.play('Wrong')
                    except Exception:
                        pass
                    QMessageBox.warning(self, "Invalid PIN", f"PIN must be 4 digits. {remaining_attempts} attempts remaining.")
                    return

            if str(pin_val) != str(self._admin_pin):
                # incorrect PIN
                self._admin_pin_attempts += 1
                remaining_attempts = self._admin_pin_max_attempts - self._admin_pin_attempts
                if remaining_attempts <= 0:
                    # lockout
                    self._admin_pin_lockout_until = datetime.now() + timedelta(minutes=self._admin_pin_lockout_minutes)
                    self._admin_pin_attempts = 0
                    try:
                        sfx.play('Wrong')
                    except Exception:
                        pass
                    QMessageBox.warning(self, "Locked", f"Too many attempts. Admin login locked for {self._admin_pin_lockout_minutes} minutes.")
                    return
                else:
                    try:
                        sfx.play('Wrong')
                    except Exception:
                        pass
                    QMessageBox.warning(self, "Invalid PIN", f"Invalid PIN. {remaining_attempts} attempts remaining.")
                    return
            else:
                # successful PIN, reset attempts
                self._admin_pin_attempts = 0
                try:
                    sfx.play('Correct_or_Payment')
                except Exception:
                    pass
        except Exception:
            # If anything goes wrong with PIN prompt, fail closed (deny admin access)
            QMessageBox.warning(self, "Error", "Unable to verify admin PIN")
            return

        dlg = AdminLoginDialog()
        if dlg.exec_() != QDialog.Accepted:
            return

        # Credential lockout check (username/password attempts)
        try:
            now = datetime.now()
            if self._admin_cred_lockout_until and now < self._admin_cred_lockout_until:
                remaining = self._admin_cred_lockout_until - now
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                QMessageBox.warning(self, "Locked", f"Admin credentials locked. Try again in {mins}m {secs}s")
                return
        except Exception:
            pass

        username = dlg.input_user.text().strip()
        password = dlg.input_pass.text().strip()

        conn = db.connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
            if not row:
                try:
                    sfx.play('Wrong')
                except Exception:
                    pass
                QMessageBox.warning(self, "Login Failed", "User not found or inactive")
                return
            # Check per-user persistent lockout (locked_until stored in DB)
            try:
                locked_until_val = None
                try:
                    locked_until_val = row['locked_until']
                except Exception:
                    locked_until_val = None
                if locked_until_val:
                    try:
                        lock_dt = datetime.fromisoformat(locked_until_val)
                    except Exception:
                        try:
                            lock_dt = datetime.strptime(locked_until_val, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            lock_dt = None
                    if lock_dt and datetime.now() < lock_dt:
                        try:
                            sfx.play('Wrong')
                        except Exception:
                            pass
                        remaining = lock_dt - datetime.now()
                        mins = int(remaining.total_seconds() // 60)
                        secs = int(remaining.total_seconds() % 60)
                        QMessageBox.warning(self, "Locked", f"Account locked. Try again in {mins}m {secs}s")
                        return
                    else:
                        # lock expired: reset DB counters
                        try:
                            conn.execute("UPDATE users SET cred_attempts=0, locked_until=NULL WHERE id=?", (row['id'],))
                            conn.commit()
                        except Exception:
                            pass
            except Exception:
                pass
            # Verify password using a CryptContext that supports pbkdf2_sha256 and bcrypt.
            # This allows seeded passwords to use pbkdf2_sha256 while still being
            # able to verify existing bcrypt hashes if present.
            from passlib.context import CryptContext
            pwd_ctx = CryptContext(schemes=['pbkdf2_sha256', 'bcrypt'], default='pbkdf2_sha256', deprecated='auto')
            if not pwd_ctx.verify(password, row['password_hash']):
                # failed credential: update per-user attempt counter in DB and possibly lock
                try:
                    cur_attempts = 0
                    try:
                        cur_attempts = int(row['cred_attempts'] or 0)
                    except Exception:
                        cur_attempts = 0
                    cur_attempts += 1
                    remaining_attempts = self._admin_cred_max_attempts - cur_attempts
                    if cur_attempts >= self._admin_cred_max_attempts:
                        lock_until_dt = datetime.now() + timedelta(minutes=self._admin_pin_lockout_minutes)
                        lock_until_str = lock_until_dt.isoformat(sep=' ')
                        try:
                            conn.execute("UPDATE users SET cred_attempts=0, locked_until=? WHERE id=?", (lock_until_str, row['id']))
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            sfx.play('Wrong')
                        except Exception:
                            pass
                        QMessageBox.warning(self, "Locked", f"Too many failed credential attempts. Account locked for {self._admin_pin_lockout_minutes} minutes.")
                        return
                    else:
                        try:
                            conn.execute("UPDATE users SET cred_attempts=? WHERE id=?", (cur_attempts, row['id']))
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            sfx.play('Wrong')
                        except Exception:
                            pass
                        QMessageBox.warning(self, "Login Failed", f"Invalid credentials. {remaining_attempts} attempts remaining.")
                        return
                except Exception:
                    try:
                        sfx.play('Wrong')
                    except Exception:
                        pass
                    QMessageBox.warning(self, "Login Failed", "Invalid credentials")
                    return

            # Successful credential verification: reset per-user attempt counters in DB
            try:
                try:
                    conn.execute("UPDATE users SET cred_attempts=0, locked_until=NULL WHERE id=?", (row['id'],))
                    conn.commit()
                except Exception:
                    pass
                # also reset in-memory fallback
                try:
                    self._admin_cred_attempts = 0
                    self._admin_cred_lockout_until = None
                except Exception:
                    pass
            except Exception:
                pass

            # Successful credential verification: play correct sound and record audit
            try:
                try:
                    sfx.play('Correct_or_Payment')
                except Exception:
                    pass
                # record successful login in audit_logs
                try:
                    self._write_audit('login_success', 'Admin login successful', username=row['username'], role=row['role'])
                except Exception:
                    pass
                # set current admin context so subsequent admin actions can be attributed
                try:
                    self._current_admin = {'id': row['id'], 'username': row['username'], 'role': row['role']}
                except Exception:
                    self._current_admin = None
            except Exception:
                pass

            # Open admin panel based on role
            role = row['role']
            if role == 'super_admin':
                self.open_admin_panel(role='super_admin')
            elif role == 'admin':
                # admin can only adjust stock
                self.open_admin_panel(role='admin')
            else:
                try:
                    sfx.play('Wrong')
                except Exception:
                    pass
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

        # Connect admin insights button to show viz
        try:
            panel.insights_clicked.connect(lambda: self.stack.setCurrentWidget(self.viz))
        except Exception:
            pass

        # Connect signals
        # Super admin: full access. Admin: only stock adjust.
        if role == 'super_admin':
            panel.add_item.connect(self.admin_create_item)
            panel.edit_item.connect(self.admin_update_item)
            panel.delete_item.connect(self.admin_delete_item)
            # connect search from admin panel to a DB-backed search handler
            try:
                panel.search_query.connect(lambda q, p=panel: self._admin_search_items(q, p))
            except Exception:
                pass
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

        # When the panel is closed (Back or Exit), clear current admin context
        try:
            def _on_panel_closed():
                try:
                    self._current_admin = None
                except Exception:
                    pass
            panel.back_clicked.connect(_on_panel_closed)
            panel.exit_clicked.connect(_on_panel_closed)
        except Exception:
            pass

    def _admin_search_items(self, query, panel):
        """Search items by name (simple LIKE) and populate the provided panel with results."""
        try:
            conn = db.connect()
            if not query:
                rows = conn.execute("SELECT i.*, c.name as category_name FROM items i LEFT JOIN categories c ON i.category_id=c.id WHERE active=1").fetchall()
            else:
                q = "SELECT i.*, c.name as category_name FROM items i LEFT JOIN categories c ON i.category_id=c.id WHERE i.name LIKE ? AND active=1"
                rows = conn.execute(q, (f"%{query}%",)).fetchall()
            items_list = [dict(r) for r in rows]
            conn.close()
            try:
                panel.populate_items(items_list)
            except Exception:
                pass
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

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
            # Prefer storing a relative path in the `image_path` column (schema uses image_path)
            if img_path:
                saved_path, _ = self._save_image_file(img_path)

            cur.execute("INSERT INTO items (name, price, stock, category_id, image_path) VALUES (?,?,?,?,?)",
                        (payload['name'], payload['price'], payload['stock'], payload['category_id'], saved_path))
            conn.commit()
            QMessageBox.information(self, "Success", "Item added")
            # audit log
            try:
                uname = (self._current_admin or {}).get('username')
                self._write_audit('item_create', f"Created item: {payload.get('name')}", username=uname, role=(self._current_admin or {}).get('role'))
            except Exception:
                pass
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

            # audit log for stock adjustment
            try:
                uname = (self._current_admin or {}).get('username')
                self._write_audit('stock_adjust', f"Item {item_id} stock {current} -> {new_stock_val}", username=uname, role=(self._current_admin or {}).get('role'))
            except Exception:
                pass

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
            # Save image file (copy to assets/images) and update image_path column when provided
            if img_path:
                saved_path, _ = self._save_image_file(img_path)

            if saved_path is not None:
                cur.execute("UPDATE items SET name=?, price=?, stock=?, category_id=?, image_path=? WHERE id=?",
                            (payload['name'], payload['price'], payload['stock'], payload['category_id'], saved_path, item_id))
            else:
                cur.execute("UPDATE items SET name=?, price=?, stock=?, category_id=? WHERE id=?",
                            (payload['name'], payload['price'], payload['stock'], payload['category_id'], item_id))
            conn.commit()
            QMessageBox.information(self, "Success", "Item updated")
            # audit log
            try:
                uname = (self._current_admin or {}).get('username')
                self._write_audit('item_update', f"Updated item {item_id}: {payload.get('name')}", username=uname, role=(self._current_admin or {}).get('role'))
            except Exception:
                pass
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
            # audit log for deletion
            try:
                uname = (self._current_admin or {}).get('username')
                self._write_audit('item_delete', f"Deleted item {item_id}", username=uname, role=(self._current_admin or {}).get('role'))
            except Exception:
                pass
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete item: {e}")
        finally:
            conn.close()

    def _save_image_file(self, src_path):
        import os, shutil
        # Ensure assets/images exists inside the project directory (module-relative)
        module_dir = os.path.dirname(__file__)
        dest_dir = os.path.join(module_dir, 'assets', 'images')
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
            # Return a project-relative path for storage so UI code can resolve it reliably
            try:
                rel = os.path.relpath(dest_path, module_dir)
            except Exception:
                rel = dest_path
            return rel.replace('\\', '/'), raw
        except Exception:
            # If we couldn't copy, attempt to read the original path
            try:
                with open(src_path, 'rb') as f:
                    raw = f.read()
                return src_path, raw
            except Exception:
                return src_path, None
