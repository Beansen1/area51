import argparse
import os
import time
import sqlite3
import shutil
import re
from database import db
from passlib.context import CryptContext

# Use a CryptContext that prefers pbkdf2_sha256 but can still verify bcrypt hashes.
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], default="pbkdf2_sha256", deprecated="auto")


def commit_with_retry(conn, retries=6, initial_delay=0.5):
    """Attempt to commit, retrying on `sqlite3.OperationalError: database is locked`.

    Retries use exponential backoff (initial_delay * 2**attempt).
    """
    last_exc = None
    for attempt in range(retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            last_exc = e
            msg = str(e).lower()
            if 'locked' in msg or 'busy' in msg:
                delay = initial_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            raise
    # If we exhausted retries, re-raise last exception
    raise last_exc


def seed():
    conn = db.connect()
    c = conn.cursor()

    # Categories
    cats = ["Meals", "Drinks", "Snacks", "Desserts", "Others"]
    for cat in cats:
        try:
            c.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
        except Exception:
            pass

    # Items (name, price, stock, category_id)
    # Category IDs correspond to the `cats` list above:
    # Meals=1, Drinks=2, Snacks=3, Desserts=4, Others=5
    items = [
        ("Chicken Sandwich", 150.00, 50, 1),
        ("Beef Burger", 180.00, 50, 1),
        ("Cola Zero", 45.00, 100, 2),
        ("Bottled Water", 20.00, 200, 2),
        ("Potato Chips", 55.00, 30, 3),
        ("Chocolate Bar", 35.00, 80, 4),
        ("Umbrella", 250.00, 10, 5),
        
        ("Beef Pares Rice Meal", 120.00, 15, 1),
        ("Cheeseburger", 120.00, 20, 1),
        ("Fried Chicken Meal", 160.00, 15, 1),
        ("Ham & Cheese Sandwich", 45.00, 25, 1),
        ("Instant Cup Noodles - Beef", 35.00, 50, 1),
        ("Instant Cup Noodles - Chicken", 35.00, 50, 1),
        ("Instant Cup Noodles - Spicy", 40.00, 30, 1),
        ("Lumpiang Shanghai Meal", 85.00, 18, 1),
        ("Pork SiLog", 95.00, 20, 1),
        ("Spaghetti", 95.00, 25, 1),
        ("Tocino SiLog", 95.00, 20, 1),
        ("Tuna Sandwich", 45.00, 25, 1),

        ("Banana Cue", 25.00, 30, 3),
        ("Boy Bawang", 15.00, 60, 3),
        ("Chiz Curls", 12.00, 80, 3),
        ("Choc Nut", 16.00, 50, 3),
        ("Chocolate Bar", 45.00, 40, 3),
        ("Chippy", 22.00, 50, 3),
        ("Cloud 9 Classic", 15.00, 60, 3),
        ("Corn Bits", 10.00, 100, 3),
        ("Clover Chips", 20.00, 50, 3),
        ("Ding Dong Mixed Nuts", 25.00, 40, 3),
        ("Fita", 15.00, 90, 3),
        ("Flat Tops", 3.00, 300, 3),
        ("Happy Peanuts", 12.00, 70, 3),
        ("Hansel Mocha", 12.00, 100, 3),
        ("Hansel Premium", 15.00, 80, 3),
        ("Hansel Crackers", 15.00, 80, 3),
        ("Menthol Candy", 1.00, 500, 3),
        ("Mentos", 28.00, 40, 3),
        ("Nova", 22.00, 50, 3),
        ("Pic-A", 60.00, 50, 3),
        ("Pillows", 12.00, 80, 3),
        ("Piattos", 22.00, 50, 3),
        ("Presto Peanut Butter", 12.00, 80, 3),
        ("Rebisco Sandwich", 12.00, 80, 3),
        ("Roller Coaster", 20.00, 50, 3),
        ("SkyFlakes", 15.00, 90, 3),
        ("Snowbear Mint Candy", 1.00, 500, 3),
        ("Stick-O", 10.00, 100, 3),
        ("Sungka Peanuts", 20.00, 50, 3),
        ("Tortillos", 22.00, 50, 3),
        ("V-cut", 35.00, 50, 3),
        ("X.O. Coffee Candy", 1.00, 500, 3),
        ("Yakult Pack (5s)", 55.00, 20, 3),

        ("Bottled Water 500ml", 20.00, 80, 2),
        ("Bottled Water 1L", 30.00, 50, 2),
        ("C2 Green Tea 355ml", 30.00, 60, 2),
        ("Coca-Cola 290ml", 25.00, 70, 2),
        ("Coke 1.5L", 75.00, 20, 2),
        ("Cobra Energy Drink", 35.00, 70, 2),
        ("Gatorade Blue Bolt", 55.00, 40, 2),
        ("Gatorade Orange", 55.00, 40, 2),
        ("Iced Tea 500ml", 35.00, 60, 2),
        ("Kopiko Black 3-in-1 Bottle", 40.00, 50, 2),
        ("Mogu Mogu Lychee", 35.00, 40, 2),
        ("Mogu Mogu Strawberry", 35.00, 40, 2),
        ("Mountain Dew 290ml", 25.00, 70, 2),
        ("Nescafe Iced Coffee", 42.00, 50, 2),
        ("Pepsi 290ml", 25.00, 70, 2),
        ("Pepsi 1.5L", 70.00, 20, 2),
        ("Royal 290ml", 25.00, 70, 2),
        ("Royal Tru-Orange 1L", 55.00, 30, 2),
        ("Sprite 290ml", 25.00, 70, 2),
        ("Sprite 1L", 52.00, 25, 2),
        ("Sting Energy Drink", 20.00, 70, 2),
        ("Zest-O Mango 250ml", 12.00, 80, 2),
        ("Zest-O Orange 250ml", 12.00, 80, 2),

        ("Banana Muffin", 30.00, 25, 4),
        ("Brownies", 20.00, 30, 4),
        ("Chocolate Cake Slice", 55.00, 20, 4),
        ("Chocolate Sundae", 65.00, 25, 4),
        ("Choco Chip Cookie", 25.00, 30, 4),
        ("Graham Balls (Pack of 5)", 20.00, 30, 4),
        ("Ice Cream Cup", 50.00, 30, 4),
        ("Leche Flan Cup", 40.00, 20, 4),
        ("Mango Float Slice", 75.00, 15, 4),

        ("Alcohol 70% 250ml", 45.00, 30, 5),
        ("Bread Loaf", 55.00, 20, 5),
        ("Cooking Oil 90ml", 20.00, 50, 5),
        ("Cup Rice", 20.00, 40, 5),
        ("Egg (1 piece)", 8.00, 200, 5),
        ("Egg Sandwich", 35.00, 20, 5),
        ("Fishball Cup", 25.00, 30, 5),
        ("Hotdog on Stick", 25.00, 30, 5),
        ("Hotdog Sandwich", 55.00, 20, 5),
        ("Kikiam Cup", 25.00, 30, 5),
        ("Laundry Detergent Sachet", 8.00, 100, 5),
        ("Lucky Me Pancit Canton Extra Hot", 18.00, 70, 5),
        ("Lucky Me Pancit Canton Kalamansi", 18.00, 70, 5),
        ("Lucky Me Pancit Canton Original", 18.00, 70, 5),
        ("Magic Sarap Sachet", 5.00, 150, 5),
        ("Shampoo Sachet", 7.00, 150, 5),
        ("Siomai", 30.00, 40, 5),
        ("Siopao Asado", 45.00, 20, 5),
        ("Siopao Bola-Bola", 45.00, 20, 5),
        ("Sardines in Tomato Sauce", 25.00, 50, 5),
        ("Soy Sauce 100ml", 10.00, 80, 5),
        ("Toothpaste Sachet", 10.00, 100, 5),
        ("Tissue Travel Pack", 20.00, 40, 5),
        ("Vinegar 100ml", 10.00, 80, 5),
    ]

    def _sanitize(name):
        # produce a simple filename-friendly key
        s = name.lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = s.strip("_")
        return s

    def find_image(name, category):
        # Search Products Img/<Category> for matching filenames.
        base_dir = os.path.join(os.getcwd(), 'Products Img', category)
        if not os.path.isdir(base_dir):
            return None
        key = _sanitize(name)
        exts = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']

        # direct matches: key + ext
        for ext in exts:
            p = os.path.join(base_dir, key + ext)
            if os.path.exists(p):
                return p

        # try basename contains heuristics
        for fn in os.listdir(base_dir):
            fn_low = fn.lower()
            if any(fn_low.endswith(ext) for ext in exts):
                if key in fn_low or all(tok in fn_low for tok in name.lower().split()[:2]):
                    return os.path.join(base_dir, fn)

        return None

    for name, price, stock, cat_id in items:
        try:
            image_path_val = None
            # Map numeric category id to name if possible
            try:
                category_name = cats[cat_id - 1]
            except Exception:
                category_name = None

            if category_name:
                src_img = find_image(name, category_name)
                if src_img:
                    # ensure assets/images exists
                    dest_dir = os.path.join('assets', 'images')
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_name = os.path.basename(src_img)
                    dest_path = os.path.join(dest_dir, dest_name)
                    try:
                        shutil.copy2(src_img, dest_path)
                        # store relative path so UI can find it
                        image_path_val = dest_path
                    except Exception:
                        image_path_val = None

            if image_path_val:
                c.execute("INSERT INTO items (name, price, stock, category_id, image_path) VALUES (?,?,?,?,?)",
                          (name, price, stock, cat_id, image_path_val))
            else:
                c.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)",
                          (name, price, stock, cat_id))
        except Exception:
            pass

    # Users
    # Hash using CryptContext so we avoid initializing the bcrypt backend at seed time
    # (some environments have an incompatible `bcrypt` module that causes passlib
    # to raise during backend auto-detection). pbkdf2_sha256 is a safe default.
    pw = pwd_ctx.hash("Daley4rn")
    try:
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ("admin", pw, "admin"))
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ("superadmin", pw, "super_admin"))
    except Exception:
        pass

    # Commit with retry to handle brief locks
    try:
        commit_with_retry(conn)
    finally:
        conn.close()

    print("Database Seeded.")


def verify_images():
    """List items and whether their `image_path` exists on disk.

    Prints lines: id, name, image_path, status
    """
    conn = db.connect()
    try:
        rows = conn.execute("SELECT id, name, image_path FROM items").fetchall()
        print(f"{'ID':<4} {'Name':<30} {'Image Path':<60} {'Status'}")
        print('-' * 110)
        for r in rows:
            pid = r['id']
            name = r['name']
            ip = r['image_path'] or ''
            exists = False
            path_checked = ''
            if ip:
                # try as given
                if os.path.isabs(ip) and os.path.exists(ip):
                    exists = True
                    path_checked = ip
                else:
                    # try relative assets/images
                    alt = os.path.join('assets', 'images', os.path.basename(ip))
                    if os.path.exists(alt):
                        exists = True
                        path_checked = alt
                    else:
                        path_checked = ip
            status = 'OK' if exists else 'MISSING'
            print(f"{pid:<4} {name:<30} {path_checked:<60} {status}")
    finally:
        conn.close()


def migrate_image_paths_to_blob():
    """If the `items` table still has an `image_path` text column, copy files into the BLOB `image` column.

    This will attempt to read each `image_path`, load the file bytes, and update the `image` column.
    """
    conn = db.connect()
    try:
        # Check schema for image_path column
        cols = [r[1] for r in conn.execute("PRAGMA table_info('items')").fetchall()]
        if 'image_path' not in cols:
            print('No image_path column found; nothing to migrate.')
            return

        rows = conn.execute("SELECT id, image_path FROM items WHERE image_path IS NOT NULL AND image_path <> ''").fetchall()
        updated = 0
        for r in rows:
            pid = r['id']
            ip = r['image_path']
            candidate = None
            if ip and os.path.exists(ip):
                candidate = ip
            else:
                alt = os.path.join('assets', 'images', os.path.basename(ip))
                if os.path.exists(alt):
                    candidate = alt

            if candidate:
                try:
                    with open(candidate, 'rb') as f:
                        raw = f.read()
                    conn.execute('UPDATE items SET image=? WHERE id=?', (raw, pid))
                    updated += 1
                except Exception:
                    pass

        conn.commit()
        print(f'Migration complete: updated {updated} rows.')
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', help='Verify item image paths')
    parser.add_argument('--seed', action='store_true', help='Run DB seed')
    parser.add_argument('--migrate-images', action='store_true', help='Migrate image_path text to image BLOB')
    args = parser.parse_args()

    if args.verify:
        verify_images()
    elif args.migrate_images:
        migrate_image_paths_to_blob()
    else:
        # Default to seeding when no flags provided (keeps previous behavior)
        seed()
