import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import date


DB_DEFAULT_PATH = "sales_management.db"


class DatabaseManager:
    def __init__(self, db_path: str = DB_DEFAULT_PATH):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        if self.conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row

    #schema 

    def create_tables(self):
        if self.conn is None:
            raise RuntimeError("Database not connected")

        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                category TEXT,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_datetime TEXT NOT NULL,
                subtotal REAL NOT NULL,
                vat_amount REAL NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                cash_given REAL,
                change REAL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
            """
        )

        self.conn.commit()

    #items

    def insert_item(
        self, name: str, price: float, stock: int, category: str, active: int = 1
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO items (name, price, stock, category, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, price, stock, category, active),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_categories(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT DISTINCT COALESCE(category, 'Others') AS category "
            "FROM items WHERE active = 1 ORDER BY category"
        )
        categories = [row["category"] for row in cur.fetchall()]
        return categories

    def get_items(
        self, category: Optional[str] = None, search: Optional[str] = None
    ) -> List[sqlite3.Row]:
        sql = "SELECT * FROM items WHERE active = 1"
        params: List = []

        if category and category != "All":
            sql += " AND COALESCE(category, 'Others') = ?"
            params.append(category)

        if search:
            sql += " AND name LIKE ?"
            params.append(f"%{search}%")

        sql += " ORDER BY name"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def get_all_items(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM items ORDER BY category, name")
        return cur.fetchall()

    def get_item_by_id(self, item_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        return cur.fetchone()

    def update_item_stock(self, item_id: int, new_stock: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE items SET stock = ? WHERE id = ?", (new_stock, item_id))
        self.conn.commit()

    def update_item_price(self, item_id: int, new_price: float):
        cur = self.conn.cursor()
        cur.execute("UPDATE items SET price = ? WHERE id = ?", (new_price, item_id))
        self.conn.commit()

    #orders

    def insert_order(
        self,
        subtotal: float,
        vat_amount: float,
        total_amount: float,
        payment_method: str,
        cash_given: float,
        change: float,
        order_datetime: str,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (
                order_datetime, subtotal, vat_amount, total_amount,
                payment_method, cash_given, change
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_datetime,
                subtotal,
                vat_amount,
                total_amount,
                payment_method,
                cash_given,
                change,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_order_item(
        self,
        order_id: int,
        item_id: int,
        quantity: int,
        unit_price: float,
        line_total: float,
    ):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO order_items (
                order_id, item_id, quantity, unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, item_id, quantity, unit_price, line_total),
        )
        self.conn.commit()

    def get_last_order_with_items(
        self,
    ) -> Tuple[Optional[sqlite3.Row], List[sqlite3.Row]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 1")
        order_row = cur.fetchone()
        if not order_row:
            return None, []

        cur.execute(
            """
            SELECT oi.*, i.name
            FROM order_items oi
            JOIN items i ON oi.item_id = i.id
            WHERE oi.order_id = ?
            """,
            (order_row["id"],),
        )
        items_rows = cur.fetchall()
        return order_row, items_rows

    def get_today_sales_total(self) -> float:
        today_str = date.today().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0.0) AS total
            FROM orders
            WHERE DATE(order_datetime) = ?
            """,
            (today_str,),
        )
        row = cur.fetchone()
        return float(row["total"]) if row else 0.0

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
