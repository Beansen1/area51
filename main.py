import customtkinter as ctk

from database import DatabaseManager
from view import QuickStopView
from controller import QuickStopController


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    db_manager = DatabaseManager("sales_management.db")
    db_manager.connect()
    db_manager.create_tables()

    app = QuickStopView()
    controller = QuickStopController(app, db_manager)
    #controller will attach itself to the gui

    app.mainloop()


if __name__ == "__main__":
    main()
