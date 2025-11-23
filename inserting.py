from database import DatabaseManager


def main():
    db = DatabaseManager("sales_management.db")
    db.connect()
    db.create_tables()

    existing = db.get_items()
    if existing:
        print("Items already exist in the database; skipping seeding.")
        return

    sample_items = [
        ("Cheeseburger", 120.00, 20, "Meals"),
        ("Fried Chicken Meal", 160.00, 15, "Meals"),
        ("Spaghetti", 95.00, 25, "Meals"),
        ("Chocolate Bar", 45.00, 40, "Snacks"),
        ("Banana Cue", 25.00, 30, "Snacks"),
        ("Bottled Water 500ml", 20.00, 80, "Drinks"),
        ("Iced Tea 500ml", 35.00, 60, "Drinks"),
        ("Ice Cream Cup", 50.00, 30, "Desserts"),
        ("Chocolate Sundae", 65.00, 25, "Desserts"),
        ("Siomai", 30.00, 40, "Others"),
        ("Hotdog Sandwich", 55.00, 20, "Others"),
        ("Coca-Cola 290ml", 25.00, 70, "Drinks"),
        ("Mountain Dew 290ml", 25.00, 70, "Drinks"),
        ("Royal 290ml", 25.00, 70, "Drinks"),
        ("Sprite 290ml", 25.00, 70, "Drinks"),
        ("Pepsi 290ml", 25.00, 70, "Drinks"),
        ("Egg Sandwich", 35.00, 20, "Others"),
        ("Piattos", 22.00, 50, "Snacks"),
        ("Nova", 22.00, 50, "Snacks"),
        ("Pic-A", 60.00, 50, "Snacks"),
        ("V-cut", 35.00, 50, "Snacks"),
    ]

    for name, price, stock, category in sample_items:
        db.insert_item(name, price, stock, category)

    print("Sample items inserted successfully.")


if __name__ == "__main__":
    main()
