from database import get_connection
from products import get_product, update_stock

def create_transaction(items):  
    """
    #Example Input mga puge
    items = [
        {"product_id": 1, "qty": 2},
        {"product_id": 3, "qty": 1}
    ]
    """
    conn = get_connection()
    cur = conn.cursor()

    # Calculate total
    total = 0
    for it in items:
        product = get_product(it["product_id"])
        if not product or product["stock"] < it["qty"]:
            conn.close()
            return None  # Item not found or insufficient stock

        total += product["price"] * it["qty"]

    # Insert transaction
    cur.execute("INSERT INTO transactions (total) VALUES (?)", (total,))
    trans_id = cur.lastrowid

    # Insert items + reduce stock
    for it in items:
        product = get_product(it["product_id"])
        line_total = product["price"] * it["qty"]

        cur.execute(
            "INSERT INTO transaction_items (transaction_id, product_id, quantity, line_total) VALUES (?, ?, ?, ?)",
            (trans_id, it["product_id"], it["qty"], line_total)
        )

        update_stock(it["product_id"], -it["qty"])  # deduct

    conn.commit()
    conn.close()
    return trans_id

def get_transaction(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions WHERE id = ?", (id,))
    trans = cur.fetchone()

    cur.execute("SELECT * FROM transaction_items WHERE transaction_id = ?", (id,))
    items = cur.fetchall()

    conn.close()
    return trans, items