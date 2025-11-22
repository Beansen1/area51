import sqlite3

import pandas as pd
import matplotlib.pyplot as plt

DB_PATH = "sales_management.db"


def best_selling_items(conn):
    query = """
    SELECT i.name AS item_name, SUM(oi.quantity) AS total_quantity
    FROM order_items oi
    JOIN items i ON oi.item_id = i.id
    GROUP BY i.name
    ORDER BY total_quantity DESC;
    """
    df = pd.read_sql_query(query, conn)
    print("Best-selling items:")
    print(df.head())

    if df.empty:
        print("No sales data yet.")
        return

    df.plot(kind="bar", x="item_name", y="total_quantity", legend=False)
    plt.title("Best-selling Items")
    plt.xlabel("Item")
    plt.ylabel("Quantity Sold")
    plt.tight_layout()
    plt.show()


def daily_sales_total(conn):
    query = """
    SELECT DATE(order_datetime) AS order_date,
           SUM(total_amount) AS total_sales
    FROM orders
    GROUP BY DATE(order_datetime)
    ORDER BY order_date;
    """
    df = pd.read_sql_query(query, conn)
    print("\nDaily total sales:")
    print(df.head())

    if df.empty:
        print("No sales data yet.")
        return

    df.plot(kind="bar", x="order_date", y="total_sales", legend=False)
    plt.title("Daily Sales (Total Amount)")
    plt.xlabel("Date")
    plt.ylabel("Total Sales (₱)")
    plt.tight_layout()
    plt.show()


def main():
    conn = sqlite3.connect(DB_PATH)

    best_selling_items(conn)
    daily_sales_total(conn)

    conn.close()


if __name__ == "__main__":
    main()
