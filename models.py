#product model
class Product:
    def __init__(self, id, sku, name, price, stock):
        self.id = id
        self.sku = sku
        self.name = name
        self.price = price
        self.stock = stock

#cart iteam model
class CartItem:
    def __init__(self, product, qty):
        self.product = product
        self.qty = qty

    @property
    def total(self):
        return self.product.price * self.qty
    
#cart model
class Cart:
    def __init__(self):
        self.items = []

    def add(self, product, qty=1):
        for item in self.items:
            if item.product.id == product.id:
                item.qty += qty
                return

        self.items.append(CartItem(product, qty))

    def remove(self, product_id):
        self.items = [item for item in self.items if item.product.id != product_id]

    def clear(self):
        self.items = []

    @property
    def total(self):
        return sum(item.total for item in self.items)
    
#transaction model
class Transaction:
    def __init__(self):
        self.items = []
        self.total = 0.0

    def add_item(self, cart_item):
        self.items.append(cart_item)
        self.total += cart_item.total