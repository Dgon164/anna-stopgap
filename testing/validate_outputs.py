"""Independent output validator — recompute, then compare.

    python testing/validate_outputs.py --store DIR --name DATASET [--truths FILE]

This program shares NO analysis code with anna. It re-reads the
normalized CSV with its own arithmetic, recomputes every checkable
claim class, and compares three ways:
  1. recomputed vs truths file (if given): did intake preserve the
     data exactly, even at scale?
  2. anna's displayed claims vs recomputed: is every number on the
     page right (to its displayed precision)?
  3. anna's rule-violation row lists vs recomputed: zero false
     accusations allowed.
PASS/FAIL per check; exit code 0 = all green. This is the same
method (independent recomputation) that caught the row-counting bug
in the July blind test — automated.
"""
import argparse
import csv
import json
import os
import re
import sys

FAILS = []


def check(label, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label
          + (f"  [{detail}]" if detail and not ok else ""),
          flush=True)
    if not ok:
        FAILS.append(label)


def parse_human(s):
    """'137.51M' -> (137510000.0, tolerance); '99,961' -> (99961, 0.5)."""
    s = s.strip().rstrip(";,. ")
    mult = 1.0
    if s.endswith(("M", "B", "K")):
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}[s[-1]]
        s = s[:-1]
    s = s.replace(",", "")
    val = float(s) * mult
    dec = len(s.split(".")[1]) if "." in s else 0
    return val, max(0.5, 0.5 * (10 ** -dec) * mult)


def close(shown, actual):
    val, tol = parse_human(shown)
    return abs(val - actual) <= tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--truths", default=None)
    args = ap.parse_args()

    sp = os.path.join(args.store, args.name, "state.json")
    state = json.load(open(sp, encoding="utf-8"))
    norm = os.path.join(args.store, args.name,
                        f"{args.name}.normalized.csv")
    truths = (json.load(open(args.truths, encoding="utf-8"))
              if args.truths else None)

    # ---- independent recomputation from the normalized file ----
    rows = list(csv.DictReader(open(norm, encoding="utf-8")))
    rev = [float(r["revenue"]) for r in rows]
    total_rev = sum(rev)
    region_rev, monthly, order_rev = {}, {}, {}
    tax_bad, tot_bad = [], []
    for idx, r in enumerate(rows, start=1):
        v = float(r["revenue"])
        region_rev[r["region"]] = region_rev.get(r["region"], 0) + v
        monthly[r["date"][:7]] = monthly.get(r["date"][:7], 0) + v
        order_rev[r["order_id"]] = order_rev.get(r["order_id"], 0) + v
        tax, tot = float(r["tax"]), float(r["total"])
        if abs(tax - round(0.08 * v, 2)) > 0.011:
            tax_bad.append(idx)
        elif abs(tot - round(v + tax, 2)) > 0.011:
            tot_bad.append(idx)
    leader = max(region_rev, key=region_rev.get)
    top_order = max(order_rev, key=order_rev.get)

    print(f"validating {args.name}: {len(rows):,} rows, "
          f"recomputed revenue {total_rev:,.2f}\n")

    # ---- 1. file fidelity vs truths ----
    if truths:
        check("intake preserved row count",
              len(rows) == truths["rows"],
              f"{len(rows)} vs {truths['rows']}")
        check("intake preserved revenue to the cent",
              abs(total_rev - truths["revenue_total"]) < 0.01,
              f"{total_rev:.2f} vs {truths['revenue_total']}")
        for rg, tv in truths["region_revenue"].items():
            check(f"intake preserved {rg} revenue",
                  abs(region_rev.get(rg, 0) - tv) < 0.01)
        check("recomputed tax violations = planted",
              tax_bad == truths["tax_violation_rows"],
              f"{len(tax_bad)} vs "
              f"{len(truths['tax_violation_rows'])}")
        check("recomputed total violations = planted",
              tot_bad == truths["total_violation_rows"],
              f"{len(tot_bad)} vs "
              f"{len(truths['total_violation_rows'])}")

    # ---- 2. displayed claims vs recomputed ----
    txt = " ".join(" ".join(s["lines"]) for s in state["sections"])
    kpi = next((k for k in state["kpis"]
                if k["label"] == "Total revenue"), None)
    check("KPI total revenue matches recomputed",
          kpi is not None and close(kpi["value"], total_rev),
          kpi["value"] if kpi else "KPI ABSENT")

    m = re.search(r"\*\*revenue by region\*\* — leader "
                  r"'([^']+)' with (\d+)% of the total", txt)
    check("region leader claim present", m is not None)
    if m:
        check("region leader correct", m.group(1) == leader,
              f"claimed {m.group(1)}, actual {leader}")
        share = 100 * region_rev[leader] / total_rev
        check("leader share within 1%",
              abs(int(m.group(2)) - share) <= 1.0,
              f"claimed {m.group(2)}%, actual {share:.1f}%")
    # scope to the revenue-by-region sentence — the units-by-region
    # line matches the same shape with different (correct) numbers
    rr = re.search(r"\*\*revenue by region\*\*(.*?)(?:\*\*|$)", txt)
    for rg, amt in (re.findall(
            r"'(\w+)' ([\d.,]+[KMB]?) \(\d+%, [\d,]+ rows",
            rr.group(1)) if rr else [])[:3]:
        if rg in region_rev:
            check(f"displayed {rg} total matches recomputed",
                  close(amt, region_rev[rg]),
                  f"shown {amt}, actual {region_rev[rg]:,.2f}")

    mm = re.search(r"\*\*revenue\*\*: (\d{4}-\d{2}) total "
                   r"([\d.,]+[KMB]?),", txt)
    check("monthly revenue claim present", mm is not None)
    if mm:
        check(f"monthly revenue for {mm.group(1)} matches",
              mm.group(1) in monthly
              and close(mm.group(2), monthly[mm.group(1)]),
              f"shown {mm.group(2)}, actual "
              f"{monthly.get(mm.group(1), 0):,.2f}")

    # ---- 3. rule-violation lists: zero false accusations ----
    # anna reports SPREADSHEET line numbers (header = line 1), the
    # number a client sees in Excel — so listed N = data row N-1
    listed = [int(x) - 1 for x in re.findall(r"row (\d+):", txt)]
    bad_set = set(tax_bad) | set(tot_bad)
    false_acc = [x for x in listed if x not in bad_set]
    check("reconciliation listed at least one violation",
          len(listed) > 0)
    check("zero false accusations in reconciliation",
          not false_acc, f"falsely accused rows {false_acc[:5]}")
    if len(listed) < len(bad_set):
        print(f"note: {len(listed)} of {len(bad_set)} violations "
              f"listed (display cap) — all listed ones are real")

    if truths:
        check("planted biggest order found by recompute",
              top_order == truths["whale_order"])
        check("biggest order named in the results",
              truths["whale_order"] in txt)
        check("planted refund day named in the results",
              truths["refund_day"] in txt)

    print(f"\nresult: "
          f"{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL(S): ' + '; '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
