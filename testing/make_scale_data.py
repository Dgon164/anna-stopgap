"""Generate a large synthetic sales dataset with KNOWN answers.

    python testing/make_scale_data.py --rows 1000000 --out big.csv

Writes the CSV plus <out>.truths.json holding the exact expected
numbers (totals, per-region sums, rule-violation rows, the planted
biggest order, the planted refund day, monthly sums). Seeded, so the
same arguments always produce the same file and the same answers.
Every truth is accumulated from the values actually written to disk,
so the truths file is exact for the file, not for the formula.
"""
import argparse
import csv
import json
import os
import random
from datetime import date, timedelta

START = date(2025, 1, 1)
SPAN_DAYS = 546          # through 2026-06-30
REGIONS = [("east", 2.0), ("west", 1.0), ("north", 0.5)]
PRODUCTS = ["alpha", "beta", "gamma", "delta", "epsilon",
            "zeta", "eta", "theta"]
PRICES = {p: round(10 + 15 * i, 2) for i, p in enumerate(PRODUCTS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    n = args.rows
    truths = dict(rows=n, revenue_total=0.0,
                  region_revenue={r: 0.0 for r, _ in REGIONS},
                  monthly_revenue={}, tax_violation_rows=[],
                  total_violation_rows=[], whale_order="O-WHALE",
                  whale_revenue=0.0, refund_day=None,
                  refund_revenue=0.0, orders=0)
    # violation rows: ~1 per 20k rows, at least 3 of each
    n_viol = max(3, n // 20_000)
    tax_rows = set(rng.sample(range(1, n + 1), n_viol))
    tot_rows = set(rng.sample(
        sorted(set(range(1, n + 1)) - tax_rows), n_viol))
    # the planted refund day (3/4 mark) and the planted whale order
    # (midpoint) — kept apart so the whale can't swallow the refunds
    refund_day = START + timedelta(days=(SPAN_DAYS * 3) // 4)
    truths["refund_day"] = refund_day.isoformat()
    whale_at = n // 2
    whale_left = 60

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "order_id", "customer", "region",
                    "product", "units", "unit_price", "revenue",
                    "tax", "total"])
        order_no, rows_left = 0, 0
        cur_date = START
        for i in range(1, n + 1):
            if rows_left == 0:
                order_no += 1
                rows_left = rng.choice((1, 2, 2, 3))
                cur_date = START + timedelta(
                    days=int((i - 1) / n * SPAN_DAYS))
            rows_left -= 1
            oid = f"O{order_no}"
            customer = f"C{rng.randint(1, max(10, n // 10))}"
            region = rng.choices([r for r, _ in REGIONS],
                                 [wt for _, wt in REGIONS])[0]
            if i >= whale_at and whale_left > 0:
                # the planted biggest order: 60 rows, one order
                whale_left -= 1
                oid, product = "O-WHALE", "alpha"
                units, price = 20, 150.0
            elif cur_date == refund_day and rng.random() < 0.6:
                product = "REFUND"
                units, price = -rng.randint(1, 5), 40.0
            else:
                product = rng.choice(PRODUCTS)
                units, price = rng.randint(1, 8), PRICES[product]
            revenue = round(units * price, 2)
            tax = round(0.08 * revenue, 2)
            if i in tax_rows:
                tax = round(tax * 2.2 + 5, 2)
                truths["tax_violation_rows"].append(i)
            total = round(revenue + tax, 2)
            if i in tot_rows:
                total = round(total + 25, 2)
                truths["total_violation_rows"].append(i)
            w.writerow([cur_date.isoformat(), oid, customer, region,
                        product, units, price, revenue, tax, total])
            truths["revenue_total"] += revenue
            truths["region_revenue"][region] += revenue
            mk = cur_date.isoformat()[:7]
            truths["monthly_revenue"][mk] = \
                truths["monthly_revenue"].get(mk, 0.0) + revenue
            if oid == "O-WHALE":
                truths["whale_revenue"] += revenue
            if product == "REFUND":
                truths["refund_revenue"] += revenue
        truths["orders"] = order_no + 1

    for k in ("revenue_total", "whale_revenue", "refund_revenue"):
        truths[k] = round(truths[k], 2)
    truths["region_revenue"] = {k: round(v, 2) for k, v in
                                truths["region_revenue"].items()}
    truths["monthly_revenue"] = {k: round(v, 2) for k, v in
                                 truths["monthly_revenue"].items()}
    truths["tax_violation_rows"].sort()
    truths["total_violation_rows"].sort()
    tp = args.out + ".truths.json"
    with open(tp, "w", encoding="utf-8") as f:
        json.dump(truths, f, indent=1)
    print(f"wrote {args.out} ({os.path.getsize(args.out):,} bytes, "
          f"{n:,} rows) + truths at {tp}")
    print(f"revenue total {truths['revenue_total']:,.2f}; "
          f"violations {len(truths['tax_violation_rows'])} tax / "
          f"{len(truths['total_violation_rows'])} total")


if __name__ == "__main__":
    main()
