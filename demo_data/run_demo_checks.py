"""RUN THE DEMO CHECKS — every planted truth, one command, PASS/FAIL.

    python demo_data/run_demo_checks.py

Processes the demo files into a throwaway store and asserts the
answers against the planted truths in docs/DEMO_SCRIPT.md. Works
with or without the engine (standalone mode is reported, not
failed). Exit code 0 = all green.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import anna_edge                    # noqa: E402
import honest_report as hr          # noqa: E402

FAILS = []


def check(label, ok):
    print(("PASS  " if ok else "FAIL  ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def all_text(state):
    return " ".join(" ".join(s["lines"]) for s in state["sections"])


def main():
    store = tempfile.mkdtemp(prefix="anna_demo_checks_")
    print(f"engine connected: {hr.engine_available()} "
          f"(False = standalone build — also a valid result)")
    print(f"throwaway store: {store}\n")

    # 1. the flagship business file and its planted book errors
    names = anna_edge.process_any(
        os.path.join(HERE, "business_demo3.csv"), store,
        audit=False, quiet=True)
    st = anna_edge.load_state(store, names[0])
    txt = all_text(st)
    check("business_demo3: KPI total revenue 636,927",
          any(k["value"] == "636,927" for k in st["kpis"]))
    check("business_demo3: planted total=revenue+tax break at row 390",
          "row 390" in txt)
    check("business_demo3: planted tax-rule break at row 427",
          "row 427" in txt)
    hits = anna_edge.ask_one(st, "where does the book not balance")
    check("ask routes to reconciliation first",
          bool(hits) and "book doesn't balance" in hits[0][1])
    check("ask refuses honestly on absent topics",
          not anna_edge.ask_one(st, "employee salaries by department"))

    # 2. cache: same bytes never process twice
    again = anna_edge.process_any(
        os.path.join(HERE, "business_demo3.csv"), store,
        audit=False, quiet=True)
    check("cache hit returns the same dataset", again == names)

    # 3. the whole database — every table, planted region truth
    db_names = anna_edge.process_any(
        os.path.join(HERE, "test_shop.db"), store,
        audit=False, quiet=True)
    check("test_shop.db: all 3 tables processed", len(db_names) == 3)
    orders = anna_edge.load_state(store, "test_shop.orders")
    otxt = all_text(orders) if orders else ""
    check("orders: east 99,961 at 60% (planted 99,960.65)",
          "'east' 99,961 (60%" in otxt)
    check("orders: west 42,457 (planted 42,457.22)",
          "42,457" in otxt)

    # 4. currency intake + derived revenue
    cn = anna_edge.process_any(
        os.path.join(HERE, "currency_test.csv"), store,
        audit=False, quiet=True)
    cst = anna_edge.load_state(store, cn[0])
    check("currency: conversion receipted",
          any("currency/formatted" in n for n in cst["notes"]))
    check("currency: derived revenue total 6,031 (hand: 6,030.88)",
          "total 6,031" in all_text(cst))

    # 5. refusals refuse — and never crash
    for fname, want in [("refusals/empty.csv", "no content"),
                        ("refusals/mysql_flavored_dump.sql",
                         "SQLite-compatible")]:
        try:
            anna_edge.process_any(os.path.join(HERE, fname), store,
                                  quiet=True)
            check(f"{fname}: refused", False)
        except SystemExit as e:
            check(f"{fname}: refused plainly", want in str(e))

    total = 13
    print(f"\nresult: {total - len(FAILS)}/{total} passed"
          + ("" if not FAILS
             else " — failures: " + "; ".join(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
