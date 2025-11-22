#Product Service
from products import get_product, get_product_by_sku, list_products
from models import Product

class ProductService:

    def get_all_products(self):
        rows = list_products()
        return [Product(r["id"], r["sku"], r["name"], r["price"], r["stock"]) for r in rows]

    def get_product_by_id(self, id):
        row = get_product(id)
        if not row:
            return None
        return Product(row["id"], row["sku"], row["name"], row["price"], row["stock"])

    def get_product_by_sku(self, sku):
        row = get_product_by_sku(sku)
        if not row:
            return None
        return Product(row["id"], row["sku"], row["name"], row["price"], row["stock"])
    
#Cart service
from models import Cart

class CartService:
    def __init__(self):
        self.cart = Cart()

    def add_to_cart(self, product, qty=1):
        self.cart.add(product, qty)

    def remove_from_cart(self, product_id):
        self.cart.remove(product_id)

    def clear_cart(self):
        self.cart.clear()

    def get_items(self):
        return self.cart.items

    def get_total(self):
        return self.cart.total
    
#Check-out(?) service
from transactions import create_transaction
from products import update_stock

class CheckoutService:

    def checkout(self, cart):
        if len(cart.items) == 0:
            return None  # no items

        # Validate stock from DB
        for item in cart.items:
            if item.product.stock < item.qty:
                return None  # insufficient stock

        # Prepare dictionary for DB transaction
        db_items = []
        for item in cart.items:
            db_items.append({
                "product_id": item.product.id,
                "qty": item.qty
            })

        # Store in DB (this deducts the stock)
        trans_id = create_transaction(db_items)

        if trans_id:
            cart.clear()

        return trans_id