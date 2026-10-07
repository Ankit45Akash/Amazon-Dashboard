import os
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, request, render_template, send_file

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pipeline
import storage

app = Flask(__name__)

PIPE = {"last_run": None, "last_added": 0, "total_added": 0, "source": os.getenv("SOURCE", "demo"),
        "auto": False, "interval": 15, "log": []}


def log(msg):
    PIPE["log"].insert(0, {"t": datetime.now().strftime("%H:%M:%S"), "msg": msg})
    del PIPE["log"][60:]


def run_pipeline():
    try:
        name, fetched, added = pipeline.run_once()
        PIPE.update(last_run=datetime.now().strftime("%d %b %Y %H:%M:%S"), last_added=added, source=name)
        PIPE["total_added"] += added
        log(f"[{name}] fetched {fetched} orders, {added} new saved to Excel")
        return {"ok": True, "fetched": fetched, "added": added}
    except Exception as e:  # show the problem in the UI instead of crashing
        log(f"ERROR: {e}")
        return {"ok": False, "error": str(e)}


def _auto_loop():
    while True:
        time.sleep(1)
        if PIPE["auto"] and (time.time() % PIPE["interval"] < 1):
            run_pipeline()
            time.sleep(1)


# ---------- helpers ----------
def pkey(d, p):
    if p == "daily":
        return d
    if p == "weekly":
        return d - timedelta(days=d.weekday())
    if p == "monthly":
        return date(d.year, d.month, 1)
    return date(d.year, 1, 1)


def nxt(k, p):
    if p == "daily":
        return k + timedelta(days=1)
    if p == "weekly":
        return k + timedelta(days=7)
    if p == "monthly":
        return date(k.year + (k.month == 12), k.month % 12 + 1, 1)
    return date(k.year + 1, 1, 1)


def label(k, p):
    if p == "daily":
        return k.strftime("%d %b")
    if p == "weekly":
        return "Wk " + k.strftime("%d %b")
    if p == "monthly":
        return k.strftime("%b %Y")
    return str(k.year)


def pct(a, b):
    return round((a - b) / b * 100, 1) if b else None


# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html")


# ---------- API ----------
@app.route("/api/overview")
def overview():
    orders = storage.read_orders()
    today = date.today()
    rev = sum(o["Total"] for o in orders)
    custs = {o["CustomerID"] for o in orders}
    last30 = [o for o in orders if (today - o["Date"]).days < 30]
    prev30 = [o for o in orders if 30 <= (today - o["Date"]).days < 60]
    r30, rp30 = sum(o["Total"] for o in last30), sum(o["Total"] for o in prev30)
    today_rev = sum(o["Total"] for o in orders if o["Date"] == today)
    cat = defaultdict(float)
    for o in orders:
        cat[o["Category"]] += o["Total"]
    prod = defaultdict(float)
    for o in orders:
        prod[o["Product"]] += o["Total"]
    top_products = sorted(prod.items(), key=lambda x: -x[1])[:6]
    return jsonify({
        "revenue": round(rev, 2), "orders": len(orders), "customers": len(custs),
        "aov": round(rev / len(orders), 2) if orders else 0,
        "today": round(today_rev, 2), "rev30": round(r30, 2), "growth30": pct(r30, rp30),
        "categories": {"labels": list(cat), "values": [round(v, 2) for v in cat.values()]},
        "top_products": {"labels": [p[0] for p in top_products], "values": [round(p[1], 2) for p in top_products]},
    })


@app.route("/api/sales")
def sales():
    p = request.args.get("period", "daily")
    if p not in ("daily", "weekly", "monthly", "yearly"):
        return jsonify({"error": "bad period"}), 400
    orders = storage.read_orders()
    today = date.today()
    end = pkey(today, p)
    if p == "yearly":
        first = min((o["Date"].year for o in orders), default=today.year)
        start = date(first, 1, 1)
    else:
        n = {"daily": 30, "weekly": 12, "monthly": 12}[p]
        start = end
        for _ in range(n - 1):
            start = pkey(start - timedelta(days=1), p)
    keys, k = [], start
    while k <= end:
        keys.append(k)
        k = nxt(k, p)
    rev, cnt, units = defaultdict(float), defaultdict(int), defaultdict(int)
    cat = defaultdict(float)
    for o in orders:
        key = pkey(o["Date"], p)
        if key < start or key > end:
            continue
        rev[key] += o["Total"]
        cnt[key] += 1
        units[key] += o["Qty"]
        cat[o["Category"]] += o["Total"]
    revenue = [round(rev[k], 2) for k in keys]
    orders_n = [cnt[k] for k in keys]
    total = sum(revenue)
    best_i = max(range(len(keys)), key=lambda i: revenue[i]) if keys else 0
    return jsonify({
        "period": p,
        "labels": [label(k, p) for k in keys],
        "revenue": revenue, "orders": orders_n, "units": [units[k] for k in keys],
        "summary": {
            "total": round(total, 2), "orders": sum(orders_n),
            "avg": round(total / len(keys), 2) if keys else 0,
            "best_label": label(keys[best_i], p) if keys else "-",
            "best_value": revenue[best_i] if keys else 0,
            "change": pct(revenue[-1], revenue[-2]) if len(revenue) > 1 else None,
        },
        "categories": {"labels": list(cat), "values": [round(v, 2) for v in cat.values()]},
    })


@app.route("/api/customers")
def customers():
    orders = storage.read_orders()
    by = {}
    for o in orders:
        c = by.setdefault(o["CustomerID"], {"id": o["CustomerID"], "name": o["CustomerName"],
                                            "city": o["City"], "spend": 0.0, "orders": 0,
                                            "first": o["Date"], "last": o["Date"]})
        c["spend"] += o["Total"]
        c["orders"] += 1
        c["first"] = min(c["first"], o["Date"])
        c["last"] = max(c["last"], o["Date"])
    cl = list(by.values())
    top = sorted(cl, key=lambda c: -c["spend"])[:10]
    seg = {"One-time": 0, "Repeat (2-3)": 0, "Loyal (4+)": 0}
    for c in cl:
        seg["One-time" if c["orders"] == 1 else "Repeat (2-3)" if c["orders"] <= 3 else "Loyal (4+)"] += 1
    city = defaultdict(float)
    for o in orders:
        if o["City"]:
            city[o["City"]] += o["Total"]
    city_top = sorted(city.items(), key=lambda x: -x[1])[:8]
    today = date.today()
    months, k = [], date(today.year, today.month, 1)
    for _ in range(11):
        k = date(k.year - (k.month == 1), (k.month - 2) % 12 + 1, 1)
    for _ in range(12):
        months.append(k)
        k = nxt(k, "monthly")
    new_by = defaultdict(int)
    for c in cl:
        new_by[date(c["first"].year, c["first"].month, 1)] += 1
    repeat_rate = round(sum(1 for c in cl if c["orders"] > 1) / len(cl) * 100, 1) if cl else 0
    return jsonify({
        "total": len(cl), "repeat_rate": repeat_rate,
        "avg_ltv": round(sum(c["spend"] for c in cl) / len(cl), 2) if cl else 0,
        "top": [{**c, "spend": round(c["spend"], 2), "first": c["first"].isoformat(),
                 "last": c["last"].isoformat()} for c in top],
        "segments": {"labels": list(seg), "values": list(seg.values())},
        "cities": {"labels": [c[0] for c in city_top], "values": [round(c[1], 2) for c in city_top]},
        "new_customers": {"labels": [m.strftime("%b %y") for m in months],
                          "values": [new_by[m] for m in months]},
    })


@app.route("/api/orders", methods=["GET"])
def list_orders():
    orders = storage.read_orders()
    orders.sort(key=lambda o: (o["Date"], o["OrderID"]), reverse=True)
    q = request.args.get("q", "").lower()
    if q:
        orders = [o for o in orders if q in (o["CustomerName"] + o["Product"] + o["OrderID"] + o["City"]).lower()]
    return jsonify([{**o, "Date": o["Date"].isoformat()} for o in orders[:200]])


@app.route("/api/orders", methods=["POST"])
def add_order():
    f = request.get_json(force=True, silent=True) or {}
    name, product = (f.get("customer_name") or "").strip(), (f.get("product") or "").strip()
    try:
        qty, price = int(f.get("qty")), float(f.get("unit_price"))
        d = datetime.strptime(f.get("date") or date.today().isoformat(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Check quantity, price and date."}), 400
    if not name or not product or qty < 1 or price < 0:
        return jsonify({"ok": False, "error": "Customer name, product, quantity (>=1) and price are required."}), 400
    email = (f.get("email") or "").strip().lower()
    order = {
        "OrderID": "MAN-" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:18],
        "Date": d, "CustomerID": email or name.lower().replace(" ", "."),
        "CustomerName": name, "Email": email, "City": (f.get("city") or "").strip(),
        "Product": product, "Category": (f.get("category") or "Other").strip(),
        "Qty": qty, "UnitPrice": price, "Source": "manual",
    }
    try:
        storage.append_orders([order])
    except PermissionError as e:
        return jsonify({"ok": False, "error": str(e)}), 423
    log(f"Manual entry saved: {name} - {product} x{qty}")
    return jsonify({"ok": True, "order_id": order["OrderID"], "total": round(qty * price, 2)})


@app.route("/api/pipeline/run", methods=["POST"])
def pipe_run():
    return jsonify(run_pipeline())


@app.route("/api/pipeline/status")
def pipe_status():
    return jsonify(PIPE)


@app.route("/api/pipeline/auto", methods=["POST"])
def pipe_auto():
    f = request.get_json(force=True, silent=True) or {}
    PIPE["auto"] = bool(f.get("enabled"))
    PIPE["interval"] = max(5, int(f.get("interval", 15)))
    log(f"Live mode {'ON' if PIPE['auto'] else 'OFF'} (every {PIPE['interval']}s)")
    return jsonify(PIPE)


@app.route("/api/export")
def export():
    return send_file(storage.XLSX_PATH, as_attachment=True, download_name="sales_data.xlsx")


def bootstrap():
    if not os.path.exists(storage.XLSX_PATH):
        print("First run: creating sales_data.xlsx with sample history...")
        storage.init(pipeline.generate_history())
    threading.Thread(target=_auto_loop, daemon=True).start()


bootstrap()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"\n  Dashboard running ->  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
