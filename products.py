from database import get_connection

def add_product(sku, name, price, stock):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO products (sku, name, price, stock) VALUES (?, ?, ?, ?)",
        (sku, name, price, stock)
    )
    
    conn.commit()
    conn.close()

def get_product(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products WHERE id = ?", (id,))
    product = cur.fetchone()

    conn.close()
    return product

def get_product_by_sku(sku):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    product = cur.fetchone()

    conn.close()
    return product

def list_products():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products ORDER BY name")
    products = cur.fetchall()

    conn.close()
    return products

def update_stock(product_id, change):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False

    new_stock = row["stock"] + change
    if new_stock < 0:
        conn.close()
        return False  # insufficient stock

    cur.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()
    return True