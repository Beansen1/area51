import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream
from controller import MainController
# Ensure DB and seeds are prepared before launching the GUI to avoid locking conflicts
from database import db
import inserting
import sqlite3

def prepare_db_and_seed_if_needed():
    conn = db.connect()
    try:
        try:
            row = conn.execute('SELECT COUNT(*) as c FROM items').fetchone()
            count = row['c'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]
        except Exception:
            # fallback indexing
            count = conn.execute('SELECT COUNT(*) FROM items').fetchone()[0]
        if count == 0:
            print('No items found in DB — running seed() to populate initial data...')
            # close current connection before seeding to avoid lock overlap
            conn.close()
            inserting.seed()
        else:
            conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

def main():
    app = QApplication(sys.argv)
    
    # Load QSS
    f = QFile("assets/themes/quickstop.qss")
    if f.open(QFile.ReadOnly | QFile.Text):
        ts = QTextStream(f)
        app.setStyleSheet(ts.readAll())
    
    # Prepare DB (create schema and seed if empty) before creating the GUI
    prepare_db_and_seed_if_needed()

    window = MainController()
    # Kiosk Mode settings (uncomment for production)
    # window.showFullScreen() 
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
