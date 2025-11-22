from dataclasses import dataclass, field
from typing import Dict, List, Optional


VAT_RATE = 0.12  #12% VAT


@dataclass
class Item:
    id: int
    name: str
    price: float  #pre-VAT
    stock: int
    category: Optional[str] = None
    active: int = 1


@dataclass
class CartItem:
    item: Item
    quantity: int = 1

    def line_total(self) -> float:
        return self.item.price * self.quantity


class Cart:
    def __init__(self):
        self._items: Dict[int, CartItem] = {}

    #manipulation 

    def add_item(self, item: Item, quantity: int = 1):
        if item.id in self._items:
            self._items[item.id].quantity += quantity
        else:
            self._items[item.id] = CartItem(item=item, quantity=quantity)

    def increase_quantity(self, item_id: int, step: int = 1):
        if item_id in self._items:
            self._items[item_id].quantity += step

    def decrease_quantity(self, item_id: int, step: int = 1):
        if item_id in self._items:
            self._items[item_id].quantity -= step
            if self._items[item_id].quantity <= 0:
                del self._items[item_id]

    def remove_item(self, item_id: int):
        if item_id in self._items:
            del self._items[item_id]

    def clear(self):
        self._items.clear()

    #queries 

    def get_items(self) -> List[CartItem]:
        return list(self._items.values())

    def get_item_quantity(self, item_id: int) -> int:
        ci = self._items.get(item_id)
        return ci.quantity if ci else 0

    def subtotal(self) -> float:
        return sum(ci.line_total() for ci in self._items.values())

    def compute_totals(self):
        subtotal = round(self.subtotal(), 2)
        vat_amount = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat_amount, 2)
        return subtotal, vat_amount, total

    def is_empty(self) -> bool:
        return len(self._items) == 0


@dataclass
class OrderData:
    id: int
    order_datetime: str
    subtotal: float
    vat_amount: float
    total_amount: float
    payment_method: str
    cash_given: float
    change: float
    items: List[CartItem] = field(default_factory=list)
