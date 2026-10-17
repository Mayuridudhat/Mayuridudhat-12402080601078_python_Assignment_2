"""
Enrollment : 12402080601078
Assignment : 2          Question : Q2
Title      : Offline Web Scraping Ranker from HTML Pages

Run:
    python 12402080601078_2_Q2.py < input.txt
    python 12402080601078_2_Q2.py sample_data/q2_input.txt

Input  : line 1 -> "p k"; next p lines -> paths of saved HTML files
Output : top K unique products -> "name price rating"

Expected HTML layout (assumption - typical product-listing markup)
    <div class="product">
        <h2 class="name">Python Book</h2>
        <span class="price">Rs. 499</span>
        <span class="rating">4.8</span>
    </div>
    * container class  : product / product-item / product-card / item
    * name class       : name / product-name / title / product-title
    * price class      : price / product-price
    * rating class     : rating / product-rating / stars
    (tag types do not matter; "data-rating"/"data-price" attributes are also
    accepted).  The parser is tolerant: broken pages, missing fields and
    unknown files are skipped, never fatal.

Cleaning rules
    * price  : currency symbols/words (Rs, INR, $, EUR ...) and thousands commas
               are removed -> number; 1,299.00 becomes 1299
    * rating : first number in the text ("4.8", "4.8/5", "4.8 out of 5")
    * name   : whitespace collapsed; duplicates detected on the name
               (case-insensitive); for a duplicate the better record is kept
               (higher rating, then lower price)

Ranking : highest rating, then lower price, then lexicographic name.

Complexity
    Time  : O(total HTML size + u log u)  (u = unique products)
    Space : O(u) + one page at a time
"""

import heapq
import re
import sys
from html import unescape
from html.parser import HTMLParser

CONTAINER = {"product", "product-item", "product-card", "item"}
NAME = {"name", "product-name", "title", "product-title"}
PRICE = {"price", "product-price"}
RATING = {"rating", "product-rating", "stars"}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+")


def to_number(text):
    """First number in text, commas removed.  None when there is no number."""
    m = NUM_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


class ProductParser(HTMLParser):
    """Collects product records using a tag stack, so nested markup is fine."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.products = []
        self.stack = []          # (tag, role) role: 'container'/'name'/... / None
        self.current = None      # dict of the product being read
        self.capture = None      # field currently collecting text
        self.buf = []

    @staticmethod
    def _classes(attrs):
        return set((dict(attrs).get("class") or "").lower().split())

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        classes = self._classes(attrs)
        role = None
        if self.current is None:
            if classes & CONTAINER:
                role = "container"
                self.current = {"name": "", "price": None, "rating": None}
        else:
            amap = dict(attrs)
            if classes & NAME:
                role = "name"
            elif classes & PRICE:
                role = "price"
                if amap.get("data-price"):
                    self.current["price"] = to_number(amap["data-price"])
            elif classes & RATING:
                role = "rating"
                if amap.get("data-rating"):
                    self.current["rating"] = to_number(amap["data-rating"])
            if role in ("name", "price", "rating") and self.capture is None:
                self.capture, self.buf = role, []
            else:
                role = role if role == "container" else None
        self.stack.append((tag, role))

    def handle_data(self, data):
        if self.capture is not None:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack:
            return
        # tolerate unclosed tags: pop until the matching tag is found
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                popped = self.stack[i:]
                del self.stack[i:]
                break
        else:
            return
        for _t, role in reversed(popped):
            if role in ("name", "price", "rating") and self.capture == role:
                text = unescape("".join(self.buf)).strip()
                if role == "name":
                    self.current["name"] = " ".join(text.split())
                elif self.current[role] is None:      # data-* attr wins
                    self.current[role] = to_number(text)
                self.capture, self.buf = None, []
            elif role == "container":
                self._finish_product()

    def _finish_product(self):
        rec, self.current = self.current, None
        if rec and rec["name"] and rec["price"] is not None and rec["rating"] is not None:
            self.products.append((rec["name"], rec["price"], rec["rating"]))


def parse_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    parser = ProductParser()
    parser.feed(text)
    parser.close()
    if parser.current is not None:      # page ended inside a product block
        parser._finish_product()
    return parser.products


def better(new, old):
    """True if new (price, rating) beats old for the same product name."""
    return (-new[1], new[0]) < (-old[1], old[0])


def fmt_price(p):
    return str(int(p)) if float(p).is_integer() else f"{p:.2f}"


def fmt_rating(r):
    return f"{r:g}"


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    try:
        first = src.readline().split()
        p, k = int(first[0]), int(first[1])
    except (IndexError, ValueError):
        print("Error: first line must be: p k")
        sys.exit(1)
    if not (1 <= p <= 5000 and 1 <= k <= 1000):
        print("Error: constraints are 1 <= p <= 5000 and 1 <= k <= 1000")
        sys.exit(1)
    paths = [src.readline().strip() for _ in range(p)]

    best = {}                       # lower-case name -> (price, rating, display name)
    for path in paths:
        if not path:
            continue
        try:
            found = parse_file(path)
        except OSError as exc:
            print(f"Warning: skipped {path}: {exc}", file=sys.stderr)
            continue
        for name, price, rating in found:
            key = name.casefold()
            cand = (price, rating, name)
            if key not in best or better(cand, best[key]):
                best[key] = cand

    # rank: rating desc, price asc, name asc ; heapq.nsmallest is O(u log k)
    top = heapq.nsmallest(
        k, best.values(), key=lambda t: (-t[1], t[0], t[2]))
    for price, rating, name in top:
        print(f"{name} {fmt_price(price)} {fmt_rating(rating)}")


if __name__ == "__main__":
    main()
