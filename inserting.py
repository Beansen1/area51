import argparse
import os
import time
import sqlite3
from database import db
from passlib.hash import bcrypt


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

    # Items
    items = [
        ("Chicken Sandwich", 150.00, 50, 1),
        ("Beef Burger", 180.00, 50, 1),
        ("Cola Zero", 45.00, 100, 2),
        ("Bottled Water", 20.00, 200, 2),
        ("Potato Chips", 55.00, 30, 3),
        ("Chocolate Bar", 35.00, 80, 4),
        ("Umbrella", 250.00, 10, 5)
    ]

    for name, price, stock, cat_id in items:
        try:
            c.execute("INSERT INTO items (name, price, stock, category_id) VALUES (?,?,?,?)", 
                      (name, price, stock, cat_id))
        except Exception:
            pass

    # Users
    pw = bcrypt.hash("change_me")
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
