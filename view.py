from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QGridLayout, QScrollArea, QFrame, QLineEdit, QListWidget, QListWidgetItem,
    QHeaderView, QTableWidget, QTableWidgetItem, QDialog, QRadioButton,
    QMessageBox, QSplitter, QSizePolicy, QComboBox, QTabWidget, QDateEdit,
    QFileDialog, QSpinBox, QDoubleSpinBox, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QDate, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from datavisualization import VizPanel
import os
import base64

# --- CUSTOM WIDGETS ---

class ProductTile(QFrame):
    clicked = pyqtSignal(int) # emits item_id

    def __init__(self, item_data):
        super().__init__()
        self.setObjectName("ProductTile")
        self.item_id = item_data['id']
        self.stock = item_data['stock']
        # Make tiles a consistent size for a tidy grid
        self.setFixedSize(240, 320)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        # Image Placeholder
        self.img_lbl = QLabel()
        self.img_lbl.setObjectName("ProductImage")
        self.img_lbl.setAlignment(Qt.AlignCenter)
        # start with no placeholder text; image will be loaded from DB if available
        self.img_lbl.setText("")
        # Let image expand vertically but keep reasonable height
        self.img_lbl.setMaximumHeight(160)
        self.img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = None
        
        # Text Info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(10,5,10,10)
        
        name_lbl = QLabel(item_data['name'])
        name_lbl.setObjectName("ProductName")
        name_lbl.setWordWrap(True)
        
        price_lbl = QLabel(f"₱ {item_data['price']:,.2f}")
        price_lbl.setObjectName("ProductPrice")
        
        stock_lbl = QLabel(f"Stock: {self.stock}")
        stock_lbl.setObjectName("ProductStock")
        
        info_layout.addWidget(name_lbl)
        info_layout.addWidget(price_lbl)
        info_layout.addWidget(stock_lbl)
        
        layout.addWidget(self.img_lbl)
        layout.addLayout(info_layout)
        self.setLayout(layout)

        # Load image if provided. Support: filesystem path, data-uri/base64 text, or BLOB bytes.
        img_pix = None

        def _get_field(src, key):
            # Support sqlite3.Row and dict-like objects
            try:
                return src[key]
            except Exception:
                try:
                    return src.get(key)
                except Exception:
                    return None

        # Try a text/path field first (common names)
        img_path = _get_field(item_data, 'image_path')
        if not img_path:
            # some schemas use different names
            img_path = _get_field(item_data, 'image_path_text') or _get_field(item_data, 'img_path')

        if isinstance(img_path, str) and img_path:
            # Data URI (data:image/...) -> base64
            try:
                if img_path.strip().startswith('data:'):
                    header, b64 = img_path.split(',', 1)
                    raw = base64.b64decode(b64)
                    pix = QPixmap()
                    if pix.loadFromData(raw):
                        img_pix = pix
                # Heuristic: long base64 string stored in text
                elif len(img_path) > 256 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r" for c in img_path[:512]):
                    try:
                        raw = base64.b64decode(img_path)
                        pix = QPixmap()
                        if pix.loadFromData(raw):
                            img_pix = pix
                    except Exception:
                        pass
                else:
                    # Treat as filesystem path
                    if os.path.exists(img_path):
                        pix = QPixmap(img_path)
                        if not pix.isNull():
                            img_pix = pix
                    else:
                        alt = os.path.join('assets', 'images', os.path.basename(img_path))
                        if os.path.exists(alt):
                            pix = QPixmap(alt)
                            if not pix.isNull():
                                img_pix = pix
            except Exception:
                pass

        # If still no image, check BLOB-like fields
        if img_pix is None:
            for key in ('image', 'image_blob', 'blob', 'img_data', 'image_data'):
                data = _get_field(item_data, key)
                if not data:
                    continue
                try:
                    if isinstance(data, memoryview):
                        raw = data.tobytes()
                    elif isinstance(data, (bytes, bytearray)):
                        raw = bytes(data)
                    elif isinstance(data, str):
                        # base64 text
                        try:
                            raw = base64.b64decode(data)
                        except Exception:
                            raw = None
                    else:
                        raw = None

                    if raw:
                        pix = QPixmap()
                        if pix.loadFromData(raw):
                            img_pix = pix
                            break
                except Exception:
                    continue

        if img_pix is not None:
            self._pixmap = img_pix
            try:
                scaled = img_pix.scaled(self.img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img_lbl.setPixmap(scaled)
                self.img_lbl.setText("")
            except Exception:
                pass

        if self.stock <= 0:
            self.setEnabled(False)
            stock_lbl.setText("OUT OF STOCK")
            stock_lbl.setStyleSheet("color: red;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Rescale pixmap to new label size for responsive images
        if hasattr(self, '_pixmap') and self._pixmap is not None and not self._pixmap.isNull():
            try:
                scaled = self._pixmap.scaled(self.img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img_lbl.setPixmap(scaled)
            except Exception:
                pass

    def mousePressEvent(self, event):
        if self.stock > 0:
            self.clicked.emit(self.item_id)

# --- SCREENS ---

class AttractScreen(QWidget):
    start_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setObjectName("AttractScreen")
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("QuickStop")
        title.setObjectName("AttractTitle")
        title.setAlignment(Qt.AlignCenter)
        
        sub = QLabel("Freshness at your fingertips")
        sub.setStyleSheet("color: #BDC3C7; font-size: 24pt;")
        sub.setAlignment(Qt.AlignCenter)
        
        btn = QPushButton("TAP TO START ORDER")
        btn.setObjectName("AttractBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.start_clicked.emit)
        
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(50)
        layout.addWidget(btn)
        self.setLayout(layout)

class KioskMain(QWidget):
    # Signals to Controller
    category_selected = pyqtSignal(int) # cat_id
    item_added = pyqtSignal(int) # item_id
    checkout_requested = pyqtSignal()
    admin_clicked = pyqtSignal()
    insights_clicked = pyqtSignal()
    search_query = pyqtSignal(str)
    # Cart signals
    remove_item = pyqtSignal(int)
    update_qty = pyqtSignal(int, int) # item_id, change (+1/-1)
    
    def __init__(self):
        super().__init__()
        self.setObjectName("KioskMain")
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        
        # 1. Top Bar
        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search items...")
        self.search_input.setMinimumHeight(50)
        self.search_input.textChanged.connect(self.search_query.emit)
        
        btn_insights = QPushButton("Insights")
        btn_insights.clicked.connect(self.insights_clicked.emit)
        
        btn_admin = QPushButton("Admin")
        btn_admin.clicked.connect(self.admin_clicked.emit)
        
        top_layout.addWidget(QLabel("<b>QuickStop</b>"))
        top_layout.addWidget(self.search_input, 1)
        top_layout.addWidget(btn_insights)
        top_layout.addWidget(btn_admin)
        top_bar.setLayout(top_layout)
        
        # 2. Content Area (Splitter: Cats+Grid | Cart)
        content_layout = QHBoxLayout()
        
        # Left Side: Categories + Item Grid
        left_panel = QWidget()
        left_vbox = QVBoxLayout()
        
        # Category Bar
        self.cat_layout = QHBoxLayout()
        # (Categories populated dynamically)
        
        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_widget = QWidget()
        cat_widget.setLayout(self.cat_layout)
        cat_scroll.setWidget(cat_widget)
        cat_scroll.setFixedHeight(90)
        
        # Item Grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        
        grid_widget = QWidget()
        grid_widget.setLayout(self.grid_layout)
        grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        grid_scroll = QScrollArea()
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setWidget(grid_widget)
        
        left_vbox.addWidget(cat_scroll)
        left_vbox.addWidget(grid_scroll)
        left_panel.setLayout(left_vbox)
        
        # Right Side: Cart
        self.cart_panel = QWidget()
        self.cart_panel.setObjectName("CartPanel")
        # Make cart panel wide enough to avoid cutting off action buttons
        self.cart_panel.setMinimumWidth(420)
        self.cart_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        cart_layout = QVBoxLayout()
        
        lbl_cart = QLabel("My Cart")
        lbl_cart.setFont(QFont("Segoe UI", 18, QFont.Bold))
        
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(4)
        self.cart_table.setHorizontalHeaderLabels(["Item", "Qty", "Price", "Action"])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        # Ensure the Action column has enough room for the remove button
        self.cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(3, 80)
        # Prevent the table from shrinking too small
        self.cart_table.setMinimumWidth(380)
        self.cart_table.verticalHeader().setVisible(False)
        
        # Totals
        self.lbl_subtotal = QLabel("Subtotal: ₱ 0.00")
        self.lbl_vat = QLabel("VAT (12%): ₱ 0.00")
        self.lbl_total = QLabel("Total: ₱ 0.00")
        self.lbl_total.setStyleSheet("font-size: 20pt; font-weight: bold; color: #27AE60;")
        
        self.btn_checkout = QPushButton("CHECKOUT")
        self.btn_checkout.setObjectName("CheckoutBtn")
        self.btn_checkout.clicked.connect(self.checkout_requested.emit)
        
        cart_layout.addWidget(lbl_cart)
        cart_layout.addWidget(self.cart_table)
        cart_layout.addWidget(self.lbl_subtotal)
        cart_layout.addWidget(self.lbl_vat)
        cart_layout.addWidget(self.lbl_total)
        cart_layout.addWidget(self.btn_checkout)
        self.cart_panel.setLayout(cart_layout)
        
        content_layout.addWidget(left_panel, 1) # Expand left area
        content_layout.addWidget(self.cart_panel, 0)
        
        main_layout.addWidget(top_bar)
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)

    def populate_categories(self, categories):
        # Clear existing
        for i in range(self.cat_layout.count()): 
            self.cat_layout.itemAt(i).widget().setParent(None)
            
        all_btn = QPushButton("All")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setObjectName("CategoryBtn")
        all_btn.clicked.connect(lambda: self.category_selected.emit(0))
        self.cat_layout.addWidget(all_btn)
        
        self.cat_btns = [all_btn]
        
        for cat in categories:
            btn = QPushButton(cat['name'])
            btn.setCheckable(True)
            btn.setObjectName("CategoryBtn")
            btn.clicked.connect(lambda ch, cid=cat['id']: self.category_selected.emit(cid))
            self.cat_layout.addWidget(btn)
            self.cat_btns.append(btn)

    def update_grid(self, items):
        # Clear grid
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
        # Save last items for potential re-layout on resize
        self._last_items = items

        # Decide number of columns based on available width
        spacing = self.grid_layout.spacing() or 10
        # Calculate approximate available width for grid area (widget width minus cart panel)
        available_width = max(200, self.width() - (self.cart_panel.width() if self.cart_panel.isVisible() else 0) - 60)
        tile_min_w = 240
        max_cols = max(1, int(available_width // (tile_min_w + spacing)))

        row, col = 0, 0
        for item in items:
            tile = ProductTile(item)
            tile.clicked.connect(self.item_added.emit)
            self.grid_layout.addWidget(tile, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reflow grid on resize to adapt column count
        if hasattr(self, '_last_items') and self._last_items is not None:
            # Use a queued call to avoid heavy immediate re-layout during rapid resizes
            try:
                self.update_grid(self._last_items)
            except Exception:
                pass

    def update_cart_display(self, cart_items, totals):
        self.cart_table.setRowCount(0)
        self.cart_table.setRowCount(len(cart_items))
        
        for row, item in enumerate(cart_items):
            self.cart_table.setItem(row, 0, QTableWidgetItem(item['name']))
            
            # Qty Widget
            qty_widget = QWidget()
            qty_lay = QHBoxLayout()
            qty_lay.setContentsMargins(0,0,0,0)
            btn_minus = QPushButton("-")
            btn_minus.setFixedSize(36,36)
            btn_minus.clicked.connect(lambda ch, i=item['id']: self.update_qty.emit(i, -1))
            lbl_q = QLabel(str(item['quantity']))
            lbl_q.setFixedWidth(40)
            lbl_q.setAlignment(Qt.AlignCenter)
            btn_plus = QPushButton("+")
            btn_plus.setFixedSize(36,36)
            btn_plus.clicked.connect(lambda ch, i=item['id']: self.update_qty.emit(i, 1))
            qty_lay.addWidget(btn_minus)
            qty_lay.addWidget(lbl_q)
            qty_lay.addWidget(btn_plus)
            qty_widget.setLayout(qty_lay)
            self.cart_table.setCellWidget(row, 1, qty_widget)
            
            self.cart_table.setItem(row, 2, QTableWidgetItem(f"{item['price'] * item['quantity']:.2f}"))
            
            btn_rem = QPushButton("x")
            btn_rem.setStyleSheet("background-color: #E74C3C;")
            btn_rem.clicked.connect(lambda ch, i=item['id']: self.remove_item.emit(i))
            self.cart_table.setCellWidget(row, 3, btn_rem)
            
        self.lbl_subtotal.setText(f"Subtotal: ₱ {totals['subtotal']:,.2f}")
        self.lbl_vat.setText(f"VAT (12%): ₱ {totals['vat']:,.2f}")
        self.lbl_total.setText(f"Total: ₱ {totals['total']:,.2f}")

class PaymentDialog(QDialog):
    def __init__(self, total_amount):
        super().__init__()
        self.setWindowTitle("Payment")
        self.setFixedSize(500, 400)
        self.total = total_amount
        
        layout = QVBoxLayout()
        
        lbl_info = QLabel(f"Total to Pay: ₱ {self.total:,.2f}")
        lbl_info.setStyleSheet("font-size: 24pt; font-weight: bold;")
        lbl_info.setAlignment(Qt.AlignCenter)
        
        self.rb_cash = QRadioButton("Cash")
        self.rb_cash.setChecked(True)
        self.rb_cash.setStyleSheet("font-size: 18pt;")
        
        self.rb_card = QRadioButton("Cashless (Card/QR)")
        self.rb_card.setStyleSheet("font-size: 18pt;")
        
        self.input_cash = QLineEdit()
        self.input_cash.setPlaceholderText("Enter Cash Amount")
        self.input_cash.setStyleSheet("font-size: 18pt; padding: 10px;")
        
        self.btn_pay = QPushButton("CONFIRM PAYMENT")
        self.btn_pay.setStyleSheet("background-color: #27AE60; font-size: 18pt; padding: 15px;")
        self.btn_pay.clicked.connect(self.validate)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        layout.addWidget(lbl_info)
        layout.addWidget(self.rb_cash)
        layout.addWidget(self.rb_card)
        layout.addWidget(self.input_cash)
        layout.addSpacing(20)
        layout.addWidget(self.btn_pay)
        layout.addWidget(self.btn_cancel)
        self.setLayout(layout)
        
    def validate(self):
        method = "CASH" if self.rb_cash.isChecked() else "CASHLESS"
        cash_given = 0.0
        
        if method == "CASH":
            try:
                cash_given = float(self.input_cash.text())
                if cash_given < self.total:
                    QMessageBox.warning(self, "Error", "Insufficient cash.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid amount.")
                return
        else:
            # Cashless flow: show a QR placeholder and start a 10s countdown that auto-completes
            cash_given = self.total
            # Build a small QR dialog inside this dialog
            qr_dlg = QDialog(self)
            qr_dlg.setWindowTitle('Scan QR Code')
            qr_dlg.setModal(True)
            qr_layout = QVBoxLayout()
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            # Create a placeholder pixmap with text (simple)
            pix = QPixmap(200,200)
            pix.fill(Qt.white)
            lbl.setPixmap(pix)
            countdown_lbl = QLabel("Waiting for payment... 10s")
            countdown_lbl.setAlignment(Qt.AlignCenter)
            qr_layout.addWidget(lbl)
            qr_layout.addWidget(countdown_lbl)
            qr_dlg.setLayout(qr_layout)

            # Timer to simulate payment confirmation
            counter = {'n': 10}
            timer = QTimer(qr_dlg)
            def _tick():
                counter['n'] -= 1
                if counter['n'] <= 0:
                    timer.stop()
                    qr_dlg.accept()
                else:
                    countdown_lbl.setText(f"Waiting for payment... {counter['n']}s")

            timer.timeout.connect(_tick)
            timer.start(1000)
            qr_dlg.exec_()

        # After either flow completes, set payment_data and accept
        self.payment_data = {
            'method': method,
            'cash_given': cash_given,
            'change': cash_given - self.total
        }
        self.accept()


class ReceiptDialog(QDialog):
    def __init__(self, pdf_path=None, png_path=None):
        super().__init__()
        self.setWindowTitle("Receipt")
        self.setMinimumSize(420, 640)
        layout = QVBoxLayout()

        if png_path and os.path.exists(png_path):
            lbl = QLabel()
            pm = QPixmap(png_path)
            if not pm.isNull():
                scaled = pm.scaled(380, 520, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(scaled)
            else:
                lbl.setText("Receipt preview not available")
            layout.addWidget(lbl)
        else:
            layout.addWidget(QLabel("Receipt preview not available"))

        btns = QHBoxLayout()
        btn_open = QPushButton("Open PDF")
        btn_close = QPushButton("Close")
        btns.addWidget(btn_open)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

        def _open_pdf():
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.startfile(pdf_path)
                except Exception:
                    QMessageBox.information(self, "Open", f"PDF located at: {pdf_path}")
            else:
                QMessageBox.warning(self, "Not found", "PDF not available")

        btn_open.clicked.connect(_open_pdf)
        btn_close.clicked.connect(self.accept)
        self.setLayout(layout)

# VizPanel moved to `datavisualization.py` and imported above


class AdminLoginDialog(QDialog):
    """Simple admin login dialog. Returns username/password on accept."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin Login")
        self.setFixedSize(360, 200)
        layout = QVBoxLayout()

        form = QFormLayout()
        self.input_user = QLineEdit()
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        form.addRow("Username:", self.input_user)
        form.addRow("Password:", self.input_pass)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Login")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)

    def _on_ok(self):
        if not self.input_user.text().strip():
            QMessageBox.warning(self, "Error", "Enter username")
            return
        if not self.input_pass.text().strip():
            QMessageBox.warning(self, "Error", "Enter password")
            return
        self.accept()


class ItemEditorDialog(QDialog):
    """Dialog to add/edit an item, including uploading an image."""
    def __init__(self, categories=None, item=None):
        super().__init__()
        self.setWindowTitle("Item")
        self.setMinimumSize(480, 320)
        self.item = item
        self.categories = categories or []

        layout = QVBoxLayout()
        form = QFormLayout()

        self.input_name = QLineEdit()
        self.input_price = QDoubleSpinBox()
        self.input_price.setMaximum(1000000)
        self.input_price.setPrefix("₱ ")
        self.input_stock = QSpinBox()
        self.input_stock.setMaximum(1000000)
        self.input_cat = QComboBox()
        for c in self.categories:
            self.input_cat.addItem(c['name'], c['id'])

        img_h = QHBoxLayout()
        self.input_img = QLineEdit()
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse_image)
        img_h.addWidget(self.input_img)
        img_h.addWidget(btn_browse)

        form.addRow("Name:", self.input_name)
        form.addRow("Price:", self.input_price)
        form.addRow("Stock:", self.input_stock)
        form.addRow("Category:", self.input_cat)
        form.addRow("Image:", img_h)

        btns = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)

        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)

        if self.item:
            # Prefill
            self.input_name.setText(self.item['name'])
            self.input_price.setValue(float(self.item['price']))
            self.input_stock.setValue(int(self.item['stock']))
            if self.item.get('category_id'):
                idx = self.input_cat.findData(self.item['category_id'])
                if idx >= 0:
                    self.input_cat.setCurrentIndex(idx)
            if self.item.get('image_path'):
                self.input_img.setText(self.item['image_path'])

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.input_img.setText(path)

    def _on_save(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required")
            return
        self.result = {
            'name': name,
            'price': float(self.input_price.value()),
            'stock': int(self.input_stock.value()),
            'category_id': int(self.input_cat.currentData()) if self.input_cat.currentData() is not None else 0,
            'image_path': self.input_img.text().strip() or None
        }
        self.accept()


class AdminPanel(QWidget):
    add_item = pyqtSignal(dict)
    edit_item = pyqtSignal(int, dict)
    delete_item = pyqtSignal(int)
    adjust_stock = pyqtSignal(int, int)  # item_id, new_stock
    back_clicked = pyqtSignal()
    exit_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin - Products")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout()

        # Top row: navigation
        top_nav = QHBoxLayout()
        self.btn_back = QPushButton("Back to Kiosk")
        self.btn_exit = QPushButton("Exit App")
        top_nav.addWidget(self.btn_back)
        top_nav.addWidget(self.btn_exit)
        top_nav.addStretch()

        # Controls
        ctrl = QHBoxLayout()
        self.btn_add = QPushButton("Add Item")
        self.btn_edit = QPushButton("Edit Selected")
        self.btn_del = QPushButton("Delete Selected")
        self.btn_refresh = QPushButton("Refresh")
        ctrl.addWidget(self.btn_add)
        ctrl.addWidget(self.btn_edit)
        ctrl.addWidget(self.btn_del)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_refresh)

        self.table = QTableWidget()
        # Add an extra column for stock adjustment controls
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Price", "Stock", "Category", "Image", "Adjust"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        layout.addLayout(top_nav)
        layout.addLayout(ctrl)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_del.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_back.clicked.connect(self.back_clicked.emit)
        self.btn_exit.clicked.connect(self.exit_clicked.emit)

        self._categories = []

    def load_categories(self, cats):
        self._categories = cats

    def populate_items(self, items):
        self.table.setRowCount(0)
        for row, it in enumerate(items):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(it['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(it['name']))
            self.table.setItem(row, 2, QTableWidgetItem(f"{it['price']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(it['stock'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(it.get('category_name') or '')))
            # Show whether an image blob exists
            has_image = False
            try:
                has_image = bool(it.get('image'))
            except Exception:
                has_image = False
            self.table.setItem(row, 5, QTableWidgetItem('Yes' if has_image else 'No'))

            # Stock adjust widget: spinbox for typing desired stock and a Set button
            adj_w = QWidget()
            adj_l = QHBoxLayout()
            adj_l.setContentsMargins(0, 0, 0, 0)
            sb = QSpinBox()
            sb.setRange(0, 1000000)
            try:
                sb.setValue(int(it.get('stock') or 0))
            except Exception:
                sb.setValue(0)
            sb.setFixedWidth(80)
            btn_set = QPushButton('Set')
            btn_set.setFixedHeight(28)
            adj_l.addWidget(sb)
            adj_l.addWidget(btn_set)
            adj_w.setLayout(adj_l)

            # When Set is clicked, emit the new stock value (controller computes delta)
            def _make_set_handler(iid, spinbox):
                def _handler():
                    try:
                        new = int(spinbox.value())
                        self.adjust_stock.emit(iid, new)
                    except Exception:
                        QMessageBox.warning(self, "Error", "Invalid stock value")
                return _handler

            item_id = int(it['id'])
            btn_set.clicked.connect(_make_set_handler(item_id, sb))

            self.table.setCellWidget(row, 6, adj_w)

    def _selected_id(self):
        sel = self.table.currentRow()
        if sel < 0:
            return None
        item = self.table.item(sel, 0)
        return int(item.text()) if item else None

    def _row_data(self, row):
        return {
            'id': int(self.table.item(row, 0).text()),
            'name': self.table.item(row, 1).text(),
            'price': float(self.table.item(row, 2).text()),
            'stock': int(self.table.item(row, 3).text()),
            'category_name': self.table.item(row, 4).text(),
            'has_image': (self.table.item(row, 5).text() == 'Yes')
        }

    def _on_add(self):
        dlg = ItemEditorDialog(categories=self._categories)
        if dlg.exec_() == QDialog.Accepted:
            self.add_item.emit(dlg.result)

    def _on_edit(self):
        sel_id = self._selected_id()
        if sel_id is None:
            QMessageBox.warning(self, "Select", "Select an item first")
            return
        # Build item dict from selected row
        row = self.table.currentRow()
        item = self._row_data(row)
        # Find category id from name if present
        cat_id = None
        for c in self._categories:
            if c['name'] == item.get('category_name'):
                cat_id = c['id']
                break
        item_payload = {
            'name': item['name'],
            'price': item['price'],
            'stock': item['stock'],
            'category_id': cat_id,
            'image_path': item.get('image_path')
        }
        dlg = ItemEditorDialog(categories=self._categories, item=item_payload)
        if dlg.exec_() == QDialog.Accepted:
            self.edit_item.emit(sel_id, dlg.result)

    def _on_delete(self):
        sel_id = self._selected_id()
        if sel_id is None:
            QMessageBox.warning(self, "Select", "Select an item first")
            return
        if QMessageBox.question(self, "Delete", "Delete selected item?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.delete_item.emit(sel_id)

    def refresh(self):
        # Controller should repopulate by calling populate_items
        pass
