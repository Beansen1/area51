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
        tabs.addTab(self.chart4, "Weekday Avg")

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

            conn.close()

            self.chart1.draw()
            self.chart2.draw()
            self.chart3.draw()
            # Weekday average: compute average orders per weekday across the selected range
            try:
                # parse start/end into date objects and compute span in days (inclusive)
                from datetime import datetime
                sd = datetime.strptime(start, "%Y-%m-%d").date()
                ed = datetime.strptime(end, "%Y-%m-%d").date()
                span_days = (ed - sd).days + 1

                # number of weeks in the span (as fractional weeks). We divide totals by this value
                # to get average orders per week for each weekday.
                weeks = float(span_days) / 7.0
                if weeks <= 0:
                    weeks = 1.0

                # Query counts grouped by weekday using strftime('%w') where Sunday=0..Saturday=6
                qd = """
                SELECT strftime('%w', order_datetime) as dow, COUNT(*) as cnt
                FROM orders
                WHERE order_datetime BETWEEN ? AND ?
                GROUP BY dow
                """
                rowsd = conn.execute(qd, (start_ts, end_ts)).fetchall()
                counts = {int(r['dow']): r['cnt'] for r in rowsd}

                # Build per-week averages Monday->Sunday
                order = [1,2,3,4,5,6,0]
                labels = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
                avgs = []
                for w in order:
                    cnt = counts.get(w, 0)
                    avg = float(cnt) / weeks
                    avgs.append(avg)

                fig4 = self.chart4.figure
                fig4.clear()
                ax4 = fig4.add_subplot(111)
                ax4.bar(labels, avgs, color='#ff7f0e')
                ax4.set_title('Average Orders per Day of Week')
                ax4.set_ylabel('Average Orders')
                ax4.set_xlabel('Weekday')
            except Exception:
                fig4 = self.chart4.figure
                fig4.clear()
                ax4 = fig4.add_subplot(111)
                ax4.text(0.5, 0.5, 'No data for weekday averages', ha='center', va='center')

            self.chart4.draw()
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            QMessageBox.warning(self, 'Data Error', f'Could not load visualization data:\n{e}')
