"""Data pipeline: pulls orders from a source and loads them into the Excel file.

Sources
-------
demo   : generates realistic fake orders (default, works offline).
spapi  : Amazon Selling Partner API (needs your own seller credentials, see README).
"""
import os
import random
import time
from datetime import date, datetime, timedelta, timezone

import storage

PRODUCTS = [
    ("Echo Dot (5th Gen)", "Electronics", 3999, 5499),
    ("Fire TV Stick 4K", "Electronics", 4999, 6499),
    ("Kindle Paperwhite", "Electronics", 13999, 16999),
    ("Wireless Earbuds", "Electronics", 1499, 3999),
    ("Cotton Bedsheet Set", "Home", 899, 2499),
    ("Non-stick Cookware Set", "Home", 1799, 3999),
    ("LED Desk Lamp", "Home", 699, 1899),
    ("Running Shoes", "Fashion", 1299, 3499),
    ("Denim Jacket", "Fashion", 1599, 2999),
    ("Backpack 30L", "Fashion", 899, 2199),
    ("Yoga Mat", "Sports", 499, 1299),
    ("Protein Powder 1kg", "Sports", 1499, 2799),
    ("Dumbbell Set", "Sports", 1999, 4599),
    ("Atomic Habits (Book)", "Books", 349, 599),
    ("Python Crash Course", "Books", 549, 899),
    ("Organic Green Tea", "Grocery", 249, 599),
    ("Almonds 500g", "Grocery", 399, 749),
    ("Face Serum", "Beauty", 499, 1499),
]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Pune", "Hyderabad", "Chennai",
          "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Surat", "Indore"]
FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Kabir", "Arjun", "Neha",
         "Priya", "Ananya", "Diya", "Isha", "Kavya", "Meera", "Riya", "Sneha",
         "Rahul", "Amit", "Sanjay", "Pooja", "Nikhil", "Tanvi", "Karan", "Simran"]
LAST = ["Sharma", "Verma", "Patel", "Reddy", "Iyer", "Nair", "Gupta", "Singh",
        "Khan", "Joshi", "Mehta", "Das", "Kulkarni", "Shah", "Bose", "Rao"]


def _customer_pool(rng, n=1500):
    pool, seen = [], set()
    while len(pool) < n:
        f, l = rng.choice(FIRST), rng.choice(LAST)
        email = f"{f}.{l}{rng.randint(1, 999)}@example.com".lower()
        if email in seen:
            continue
        seen.add(email)
        pool.append({"CustomerID": email, "CustomerName": f"{f} {l}",
                     "Email": email, "City": rng.choice(CITIES)})
    return pool


_POOL = _customer_pool(random.Random(42))
_WEIGHTS = [1 / (i + 1) ** 0.45 for i in range(len(_POOL))]


def _make_order(rng, d, source, order_id=None):
    cust = rng.choices(_POOL, weights=_WEIGHTS, k=1)[0]
    name, cat, lo, hi = rng.choice(PRODUCTS)
    qty = rng.choices([1, 2, 3, 4], weights=[70, 20, 8, 2])[0]
    price = round(rng.uniform(lo, hi), 2)
    return {
        "OrderID": order_id or f"{random.randint(100,999)}-{rng.randint(1000000,9999999)}-{rng.randint(1000000,9999999)}",
        "Date": d, **cust, "Product": name, "Category": cat,
        "Qty": qty, "UnitPrice": price, "Source": source,
    }


def generate_history(days=900):
    """Seed data: ~2.5 years of orders with growth, weekends and festive-season peaks."""
    rng = random.Random(7)
    end = date.today()
    start = end - timedelta(days=days)
    orders, d, n = [], start, 0
    while d <= end:
        growth = 1 + 1.2 * ((d - start).days / days)
        season = 1.5 if d.month in (10, 11, 12) else 1.0
        weekend = 1.25 if d.weekday() >= 5 else 1.0
        base = 2.2 * growth * season * weekend
        for _ in range(max(0, int(rng.gauss(base, 1.2)))):
            n += 1
            orders.append(_make_order(rng, d, "amazon-demo", f"SEED-{n:06d}"))
        d += timedelta(days=1)
    return orders


class DemoSource:
    name = "demo"

    def fetch(self):
        rng = random.Random()
        stamp = int(time.time())
        return [
            _make_order(rng, date.today(), "amazon-demo", f"LIVE-{stamp}-{i}")
            for i in range(rng.randint(2, 7))
        ]


class SPAPISource:
    """Amazon Selling Partner API (Orders API v0). Needs credentials in env vars:
    LWA_CLIENT_ID, LWA_CLIENT_SECRET, LWA_REFRESH_TOKEN, MARKETPLACE_ID, SPAPI_ENDPOINT
    Note: buyer names/addresses are restricted PII, so customers are keyed by Amazon's
    anonymised buyer email when available."""
    name = "spapi"

    def __init__(self):
        self.cid = os.getenv("LWA_CLIENT_ID")
        self.secret = os.getenv("LWA_CLIENT_SECRET")
        self.refresh = os.getenv("LWA_REFRESH_TOKEN")
        self.marketplace = os.getenv("MARKETPLACE_ID", "A21TJRUUN4KGV")  # India
        self.endpoint = os.getenv("SPAPI_ENDPOINT", "https://sellingpartnerapi-eu.amazon.com")
        if not all([self.cid, self.secret, self.refresh]):
            raise RuntimeError("Amazon credentials missing. Fill in the .env file (see README).")

    def _token(self):
        import requests
        r = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type": "refresh_token", "refresh_token": self.refresh,
            "client_id": self.cid, "client_secret": self.secret}, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    def fetch(self):
        import requests
        hdr = {"x-amz-access-token": self._token()}
        since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(f"{self.endpoint}/orders/v0/orders", headers=hdr, timeout=30,
                         params={"MarketplaceIds": self.marketplace, "CreatedAfter": since})
        r.raise_for_status()
        out = []
        for o in r.json().get("payload", {}).get("Orders", []):
            oid = o["AmazonOrderId"]
            d = datetime.strptime(o["PurchaseDate"][:10], "%Y-%m-%d").date()
            email = (o.get("BuyerInfo") or {}).get("BuyerEmail") or f"buyer-{oid}@marketplace.amazon"
            items = requests.get(f"{self.endpoint}/orders/v0/orders/{oid}/orderItems",
                                 headers=hdr, timeout=30)
            items.raise_for_status()
            for k, it in enumerate(items.json().get("payload", {}).get("OrderItems", [])):
                qty = int(it.get("QuantityOrdered", 1)) or 1
                total = float((it.get("ItemPrice") or {}).get("Amount", 0) or 0)
                out.append({
                    "OrderID": f"{oid}-{k+1}", "Date": d, "CustomerID": email.lower(),
                    "CustomerName": (o.get("BuyerInfo") or {}).get("BuyerName") or "Amazon Customer",
                    "Email": email, "City": (o.get("ShippingAddress") or {}).get("City", ""),
                    "Product": it.get("Title", "Unknown")[:60], "Category": "Amazon",
                    "Qty": qty, "UnitPrice": round(total / qty, 2), "Source": "amazon-spapi",
                })
        return out


def get_source():
    kind = os.getenv("SOURCE", "demo").lower()
    return SPAPISource() if kind == "spapi" else DemoSource()


def run_once():
    """Extract -> Transform (dedupe) -> Load into Excel. Returns (source_name, fetched, added)."""
    src = get_source()
    orders = src.fetch()
    added = storage.append_orders(orders)
    return src.name, len(orders), added
