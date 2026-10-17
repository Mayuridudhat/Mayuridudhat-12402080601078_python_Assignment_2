"""
Enrollment : 12402080601078
Assignment : 2          Question : Q9
Title      : OOP Inventory Merger with Operator Overloading

Run:
    python 12402080601078_2_Q9.py < sample_data/q9_input.txt
    python 12402080601078_2_Q9.py sample_data/q9_input.txt

Input file layout
    line 1 : path of inventory file A
    line 2 : path of inventory file B
    line 3 : q (number of operations)
    next q : operations
Inventory file line :  product_id name stock purchase_price selling_price
                       (name may contain spaces - the last 3 fields are numbers)
                       e.g.  P1 Pen 10 5 8

Operations (A / B / M = inventory A, inventory B, last merge result)
    ADD <inv> <id> <name...> <stock> <purchase> <selling>
    DELETE <inv> <id>
    UPDATE <inv> <id> <new_stock>        (sets stock to the new value)
    MERGE                                (M = A + B, prints merged summary)
    COMPARE                              (A vs B by total valuation)

Design
    Product   : id, name, stock, purchase, selling   (__add__ merges same-id products)
    Inventory : dict {id: Product}  ->  O(1) average add / delete / update
                __add__  : A + B  -> new Inventory (inputs are not modified)
                __lt__/__eq__/... (functools.total_ordering) compare by value
                __len__, __contains__, __iter__ for natural use
    Merge rule for the same product id:
        stock = stockA + stockB, purchase = min(...), selling = max(...)
    Total valuation = sum(stock * purchase_price)   (inventory valued at cost);
    the potential selling value is printed as well.

Complexity
    Time  : O(n + m + q) average (dictionary operations)
    Space : O(n + m)
"""

import sys
from functools import total_ordering


def to_num(text):
    """Parse int when possible, otherwise float.  Raises ValueError."""
    try:
        return int(text)
    except ValueError:
        value = float(text)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"not a finite number: {text}")
        return value


def show(v):
    """Print whole floats without the trailing .0"""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(round(v, 2)) if isinstance(v, float) else str(v)


class Product:
    __slots__ = ("pid", "name", "stock", "purchase", "selling")

    def __init__(self, pid, name, stock, purchase, selling):
        if stock < 0 or purchase < 0 or selling < 0:
            raise ValueError("stock and prices must not be negative")
        self.pid, self.name = pid, name
        self.stock, self.purchase, self.selling = stock, purchase, selling

    def __add__(self, other):
        if not isinstance(other, Product) or other.pid != self.pid:
            return NotImplemented
        return Product(self.pid, self.name, self.stock + other.stock,
                       min(self.purchase, other.purchase),
                       max(self.selling, other.selling))

    def value(self):
        return self.stock * self.purchase

    def __str__(self):
        return (f"{self.pid} {self.name} stock={show(self.stock)} "
                f"purchase={show(self.purchase)} selling={show(self.selling)}")


@total_ordering
class Inventory:
    def __init__(self, name="inv"):
        self.name = name
        self._items = {}

    # ---- basic operations -------------------------------------------------
    def add_product(self, product):
        """Add a product; if the id exists it is merged (stock adds up)."""
        old = self._items.get(product.pid)
        self._items[product.pid] = product if old is None else old + product

    def delete_product(self, pid):
        if pid not in self._items:
            raise KeyError(pid)
        del self._items[pid]

    def update_stock(self, pid, stock):
        if pid not in self._items:
            raise KeyError(pid)
        if stock < 0:
            raise ValueError("stock must not be negative")
        self._items[pid].stock = stock

    def total_value(self):
        return sum(p.value() for p in self._items.values())

    def total_selling_value(self):
        return sum(p.stock * p.selling for p in self._items.values())

    # ---- operator overloading ---------------------------------------------
    def __add__(self, other):
        if not isinstance(other, Inventory):
            return NotImplemented
        merged = Inventory(f"{self.name}+{other.name}")
        for p in self._items.values():                # copy, never share objects
            merged._items[p.pid] = Product(p.pid, p.name, p.stock, p.purchase, p.selling)
        for p in other._items.values():
            merged.add_product(p)
        return merged

    def __eq__(self, other):
        if not isinstance(other, Inventory):
            return NotImplemented
        return self.total_value() == other.total_value()

    def __lt__(self, other):
        if not isinstance(other, Inventory):
            return NotImplemented
        return self.total_value() < other.total_value()

    def __len__(self):
        return len(self._items)

    def __contains__(self, pid):
        return pid in self._items

    def __iter__(self):
        return iter(sorted(self._items.values(), key=lambda p: p.pid))

    __hash__ = None


# ---------------------------------------------------------------------------
def parse_product(tokens):
    """tokens = [id, name..., stock, purchase, selling]"""
    if len(tokens) < 5:
        raise ValueError("need: id name stock purchase selling")
    pid = tokens[0]
    stock, purchase, selling = (to_num(t) for t in tokens[-3:])
    name = " ".join(tokens[1:-3])
    return Product(pid, name, stock, purchase, selling)


def load_inventory(path, label):
    inv = Inventory(label)
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                inv.add_product(parse_product(line.split()))
            except ValueError as exc:
                print(f"Warning: {path} line {lineno} skipped ({exc})", file=sys.stderr)
    return inv


def summary(inv):
    for p in inv:
        print(p)
    print(f"TOTAL products={len(inv)} valuation={show(inv.total_value())} "
          f"selling_value={show(inv.total_selling_value())}")


def run_operation(line, inventories):
    parts = line.split()
    if not parts:
        return
    op = parts[0].upper()
    try:
        if op == "MERGE":
            inventories["M"] = inventories["A"] + inventories["B"]
            print("MERGE OK")
            summary(inventories["M"])
        elif op == "COMPARE":
            a, b = inventories["A"], inventories["B"]
            va, vb = show(a.total_value()), show(b.total_value())
            sign = ">" if a > b else "<" if a < b else "=="
            print(f"COMPARE A({va}) {sign} B({vb})")
        elif op in ("ADD", "DELETE", "UPDATE"):
            target = inventories.get(parts[1].upper())
            if target is None:
                raise ValueError("inventory must be A, B or M (M exists after MERGE)")
            if op == "ADD":
                target.add_product(parse_product(parts[2:]))
            elif op == "DELETE":
                target.delete_product(parts[2])
            else:
                target.update_stock(parts[2], to_num(parts[3]))
            print(f"{op} OK")
        else:
            print(f"ERROR unknown operation: {op}")
    except KeyError as exc:
        print(f"{op} FAILED product {exc.args[0]} not found")
    except (ValueError, IndexError) as exc:
        print(f"{op} FAILED {exc}")


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    try:
        path_a = src.readline().strip()
        path_b = src.readline().strip()
        q = int(src.readline())
        inventories = {"A": load_inventory(path_a, "A"), "B": load_inventory(path_b, "B")}
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    for _ in range(q):
        run_operation(src.readline(), inventories)


if __name__ == "__main__":
    main()
