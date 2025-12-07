from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QMessageBox, QDateEdit
from PyQt5.QtCore import QDate, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from database import db


class VizPanel(QWidget):
    """Visualization panel providing three charts:
    - Daily sales (line)
    - Top items (quantity, horizontal bar)
    - Revenue contribution (pie)

    This widget is self-contained and uses the project's `db` module.
    """
    # navigation signals for Back/Exit
    back_clicked = pyqtSignal()
    exit_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # Top navigation (Back / Exit) for kiosk flow consistency
        nav = QHBoxLayout()
        btn_back = QPushButton("Back to Kiosk")
        btn_exit = QPushButton("Exit App")
        nav.addWidget(btn_back)
        nav.addWidget(btn_exit)
        nav.addStretch()
        btn_back.clicked.connect(lambda: self.back_clicked.emit())
        btn_exit.clicked.connect(lambda: self.exit_clicked.emit())
        layout.addLayout(nav)

        # Controls
        controls = QHBoxLayout()
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_charts)
        controls.addWidget(QLabel("From:"))
        controls.addWidget(self.date_from)
        controls.addWidget(QLabel("To:"))
        controls.addWidget(self.date_to)
        controls.addWidget(btn_refresh)

        # Tabs for charts
        tabs = QTabWidget()
        self.chart1 = FigureCanvas(plt.Figure(figsize=(5, 3)))
        self.chart2 = FigureCanvas(plt.Figure(figsize=(5, 3)))
        self.chart3 = FigureCanvas(plt.Figure(figsize=(5, 3)))
        self.chart4 = FigureCanvas(plt.Figure(figsize=(5, 3)))

        tabs.addTab(self.chart1, "Daily Sales")
        tabs.addTab(self.chart2, "Top Items")
        tabs.addTab(self.chart3, "Contribution")
        tabs.addTab(self.chart4, "Insights")

        layout.addLayout(controls)
        layout.addWidget(tabs)
        self.setLayout(layout)

    def refresh_charts(self):
        start = self.date_from.date().toString("yyyy-MM-dd")
        end = self.date_to.date().toString("yyyy-MM-dd")
        start_ts = f"{start} 00:00:00"
        end_ts = f"{end} 23:59:59"

        try:
            conn = db.connect()
            # Daily sales
            q = """
            SELECT substr(order_datetime,1,10) as day, SUM(total_amount) as total
            FROM orders
            WHERE order_datetime BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
            """
            rows = conn.execute(q, (start_ts, end_ts)).fetchall()
            days = [r['day'] for r in rows]
            totals = [r['total'] for r in rows]

            fig1 = self.chart1.figure
            fig1.clear()
            ax1 = fig1.add_subplot(111)
            if days:
                ax1.plot(days, totals, marker='o', color='#1f77b4')
                ax1.set_title('Daily Sales')
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Total Sales (₱)')
                ax1.tick_params(axis='x', rotation=45)
            else:
                ax1.text(0.5, 0.5, 'No sales in range', ha='center', va='center')

            # Top items by quantity sold
            q2 = """
            SELECT oi.item_id, i.name as item_name, SUM(oi.quantity) as qty_sold
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN items i ON oi.item_id = i.id
            WHERE o.order_datetime BETWEEN ? AND ?
            GROUP BY oi.item_id
            ORDER BY qty_sold DESC
            LIMIT 10
            """
            rows2 = conn.execute(q2, (start_ts, end_ts)).fetchall()
            names = [r['item_name'] for r in rows2]
            qtys = [r['qty_sold'] for r in rows2]

            fig2 = self.chart2.figure
            fig2.clear()
            ax2 = fig2.add_subplot(111)
            if names:
                ax2.barh(list(reversed(names)), list(reversed(qtys)), color='#2ca02c')
                ax2.set_title('Top Items (by quantity)')
                ax2.set_xlabel('Quantity Sold')
            else:
                ax2.text(0.5, 0.5, 'No items sold in range', ha='center', va='center')

            # Contribution by revenue per product (top 10)
            q3 = """
            SELECT oi.item_id, i.name as item_name, SUM(oi.line_total) as revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN items i ON oi.item_id = i.id
            WHERE o.order_datetime BETWEEN ? AND ?
            GROUP BY oi.item_id
            ORDER BY revenue DESC
            LIMIT 10
            """
            rows3 = conn.execute(q3, (start_ts, end_ts)).fetchall()
            labels = [r['item_name'] for r in rows3]
            revenues = [r['revenue'] for r in rows3]

            fig3 = self.chart3.figure
            fig3.clear()
            ax3 = fig3.add_subplot(111)
            if labels and sum(revenues) > 0:
                ax3.pie(revenues, labels=labels, autopct='%1.1f%%', colors=plt.cm.Pastel1.colors)
                ax3.set_title('Revenue Contribution (top products)')
            else:
                ax3.text(0.5, 0.5, 'No revenue data in range', ha='center', va='center')

            # --- Insights summary (replaces weekday chart) ---
            try:
                # total sales and orders
                qtot = """
                SELECT COALESCE(SUM(total_amount),0.0) as total_sales, COUNT(*) as total_orders
                FROM orders
                WHERE order_datetime BETWEEN ? AND ?
                """
                row_tot = conn.execute(qtot, (start_ts, end_ts)).fetchone()
                total_sales = float(row_tot['total_sales'] or 0.0)
                total_orders = int(row_tot['total_orders'] or 0)

                # average order value and per-day averages
                from datetime import datetime
                sd = datetime.strptime(start, "%Y-%m-%d").date()
                ed = datetime.strptime(end, "%Y-%m-%d").date()
                span_days = max(1, (ed - sd).days + 1)
                avg_order_value = (total_sales / total_orders) if total_orders > 0 else 0.0
                avg_sales_per_day = (total_sales / float(span_days)) if span_days > 0 else 0.0

                # Top items (reuse rows2 for quantities) and map revenues from rows3
                top_items = []
                rev_map = {r['item_name']: r['revenue'] for r in rows3}
                for r in rows2[:5]:
                    name = r['item_name']
                    qty = int(r['qty_sold'] or 0)
                    revenue = float(rev_map.get(name, 0.0))
                    top_items.append((name, qty, revenue))

                # Sales by category
                qcat = """
                SELECT COALESCE(c.name,'Uncategorized') as cat_name, COALESCE(SUM(oi.line_total),0.0) as revenue
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                JOIN items i ON oi.item_id = i.id
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE o.order_datetime BETWEEN ? AND ?
                GROUP BY c.id
                ORDER BY revenue DESC
                LIMIT 10
                """
                rows_cat = conn.execute(qcat, (start_ts, end_ts)).fetchall()

                # Recent admin login successes and super-admin change logs
                try:
                    rows_login_admin = conn.execute(
                        "SELECT username, created_at FROM audit_logs WHERE event_type='login_success' AND role='admin' ORDER BY created_at DESC LIMIT 2"
                    ).fetchall()
                except Exception:
                    rows_login_admin = []
                try:
                    rows_login_super = conn.execute(
                        "SELECT username, created_at FROM audit_logs WHERE event_type='login_success' AND role='super_admin' ORDER BY created_at DESC LIMIT 2"
                    ).fetchall()
                except Exception:
                    rows_login_super = []

                try:
                    rows_changes = conn.execute(
                        "SELECT username, event_type, detail, created_at FROM audit_logs WHERE role='super_admin' AND event_type IN ('item_create','item_update','item_delete','stock_adjust') ORDER BY created_at DESC LIMIT 8"
                    ).fetchall()
                except Exception:
                    rows_changes = []

                # Build a concise multiline summary for display
                summary_lines = []
                summary_lines.append(f"Date range: {start} → {end}")
                summary_lines.append(f"Total sales: ₱ {total_sales:,.2f}")
                summary_lines.append(f"Total orders: {total_orders}")
                summary_lines.append(f"Avg order value: ₱ {avg_order_value:,.2f}")
                summary_lines.append(f"Avg sales / day: ₱ {avg_sales_per_day:,.2f} over {span_days} days")
                summary_lines.append("")
                summary_lines.append("Top items:")
                if top_items:
                    for name, qty, rev in top_items:
                        summary_lines.append(f" - {name}: {qty} units, ₱ {rev:,.2f}")
                else:
                    summary_lines.append(" - No item sales")
                summary_lines.append("")
                summary_lines.append("Sales by category:")
                if rows_cat:
                    for rc in rows_cat:
                        summary_lines.append(f" - {rc['cat_name']}: ₱ {rc['revenue']:,.2f}")
                else:
                    summary_lines.append(" - No category sales")
                summary_lines.append("")
                summary_lines.append("Recent admin logins (admin):")
                if rows_login_admin:
                    for r in rows_login_admin:
                        summary_lines.append(f" - {r['username']}: {r['created_at']}")
                else:
                    summary_lines.append(" - No recent admin logins")
                summary_lines.append("")
                summary_lines.append("Recent admin logins (super_admin):")
                if rows_login_super:
                    for r in rows_login_super:
                        summary_lines.append(f" - {r['username']}: {r['created_at']}")
                else:
                    summary_lines.append(" - No recent super_admin logins")

                summary_lines.append("")
                summary_lines.append("Recent super_admin changes (most recent first):")
                if rows_changes:
                    for rc in rows_changes:
                        summary_lines.append(f" - [{rc['created_at']}] {rc['username']} {rc['event_type']}: {rc['detail']}")
                else:
                    summary_lines.append(" - No recent super_admin changes recorded")

                # Render a richer insights layout using gridspec:
                fig4 = self.chart4.figure
                fig4.clear()
                try:
                    gs = fig4.add_gridspec(nrows=3, ncols=3, height_ratios=[0.8, 2.0, 1.2], hspace=0.6, wspace=0.6)
                    # KPI cards (row 0: 3 columns)
                    kpi_vals = [
                        ("Total Sales", f"₱ {total_sales:,.2f}", '#2E86AB'),
                        ("Total Orders", f"{total_orders}", '#27AE60'),
                        ("Avg Order", f"₱ {avg_order_value:,.2f}", '#F6C85F')
                    ]
                    for i, (title, val, color) in enumerate(kpi_vals):
                        ax_k = fig4.add_subplot(gs[0, i])
                        ax_k.axis('off')
                        # Draw colored rounded rectangle background
                        ax_k.set_xlim(0, 1); ax_k.set_ylim(0, 1)
                        ax_k.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=color, alpha=0.14, zorder=0))
                        ax_k.text(0.02, 0.62, title, fontsize=10, weight='bold', va='center')
                        ax_k.text(0.02, 0.18, val, fontsize=18, weight='bold', va='center')

                    # Middle: Top items (span cols 0-1), Category contribution (col 2)
                    ax_top = fig4.add_subplot(gs[1, 0:2])
                    if top_items:
                        names = [t[0] for t in top_items]
                        qtys = [t[1] for t in top_items]
                        ax_top.barh(list(reversed(names)), list(reversed(qtys)), color='#2ca02c')
                        ax_top.set_title('Top Items (units)')
                        ax_top.set_xlabel('Units Sold')
                    else:
                        ax_top.text(0.5, 0.5, 'No top items', ha='center', va='center')
                        ax_top.axis('off')

                    ax_cat = fig4.add_subplot(gs[1, 2])
                    if rows_cat and sum([r['revenue'] for r in rows_cat]) > 0:
                        labels = [r['cat_name'] for r in rows_cat]
                        vals = [r['revenue'] for r in rows_cat]
                        ax_cat.pie(vals, labels=labels, autopct='%1.1f%%', colors=plt.cm.Pastel2.colors)
                        ax_cat.set_title('Sales by Category')
                    else:
                        ax_cat.text(0.5, 0.5, 'No category sales', ha='center', va='center')
                        ax_cat.axis('off')

                    # Bottom: recent logins and changes (span all columns)
                    ax_logs = fig4.add_subplot(gs[2, :])
                    ax_logs.axis('off')
                    # Build an HTML-like multiline string with headings
                    log_lines = []
                    log_lines.append(f"Insights: {start} → {end}")
                    log_lines.append(f"Total sales: ₱ {total_sales:,.2f} — Orders: {total_orders} — Avg/day: ₱ {avg_sales_per_day:,.2f}")
                    log_lines.append("")
                    log_lines.append("Recent admin logins (admin):")
                    if rows_login_admin:
                        for r in rows_login_admin:
                            log_lines.append(f" {r['created_at']} — {r['username']}")
                    else:
                        log_lines.append("  — None")
                    log_lines.append("")
                    log_lines.append("Recent super_admin logins:")
                    if rows_login_super:
                        for r in rows_login_super:
                            log_lines.append(f" {r['created_at']} — {r['username']}")
                    else:
                        log_lines.append("  — None")
                    log_lines.append("")
                    log_lines.append("Recent super_admin changes:")
                    if rows_changes:
                        for rc in rows_changes:
                            log_lines.append(f" {rc['created_at']} — {rc['username']}: {rc['event_type']} — {rc['detail']}")
                    else:
                        log_lines.append("  — None recorded")

                    # Render as left-aligned monospaced text
                    txt = '\n'.join(log_lines)
                    ax_logs.text(0.01, 0.99, txt, va='top', ha='left', family='monospace', fontsize=9)
                except Exception:
                    # fallback to simple text if layout fails
                    fig4 = self.chart4.figure
                    fig4.clear()
                    ax4 = fig4.add_subplot(111)
                    ax4.axis('off')
                    txt = '\n'.join(summary_lines)
                    ax4.text(0.01, 0.99, txt, va='top', ha='left', family='monospace', fontsize=10)
            except Exception:
                fig4 = self.chart4.figure
                fig4.clear()
                ax4 = fig4.add_subplot(111)
                ax4.text(0.5, 0.5, 'No insights available for range', ha='center', va='center')

            # close DB now that we've pulled required data
            try:
                conn.close()
            except Exception:
                pass

            # draw updated charts
            self.chart1.draw()
            self.chart2.draw()
            self.chart3.draw()
            self.chart4.draw()
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            QMessageBox.warning(self, 'Data Error', f'Could not load visualization data:\n{e}')
