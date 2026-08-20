"""Planted-truth SQLite db for the whole-database court."""
import os
import random
import sqlite3
import sys

out = sys.argv[1]
if os.path.exists(out):
    os.remove(out)
con = sqlite3.connect(out)
con.execute("CREATE TABLE orders (date TEXT, region TEXT, revenue REAL)")
con.execute("CREATE TABLE products (product TEXT, price REAL, stock INTEGER)")
con.execute("CREATE TABLE tickets (category TEXT, status TEXT)")
rng = random.Random(17)
# planted: east gets 2x the orders of west; north smallest
truth = {"east": 0.0, "west": 0.0, "north": 0.0}
for i in range(600):
    region = rng.choices(["east", "west", "north"], [2, 1, 0.5])[0]
    rev = round(rng.uniform(50, 500), 2)
    truth[region] += rev
    day = 1 + (i % 28)
    month = 1 + (i // 200)
    con.execute("INSERT INTO orders VALUES (?,?,?)",
                (f"2026-{month:02d}-{day:02d}", region, rev))
for p, price in [("widget", 19.99), ("gadget", 49.5), ("doohickey", 5.25)]:
    con.execute("INSERT INTO products VALUES (?,?,?)",
                (p, price, rng.randint(10, 500)))
for i in range(120):
    con.execute("INSERT INTO tickets VALUES (?,?)",
                (rng.choice(["billing", "shipping", "quality"]),
                 rng.choice(["open", "closed", "closed", "closed"])))
con.commit()
# the dump twin for the .sql court
with open(os.path.splitext(out)[0] + "_dump.sql", "w",
          encoding="utf-8") as f:
    for line in con.iterdump():
        f.write(line + "\n")
con.close()
print("planted truth, revenue by region:",
      {k: round(v, 2) for k, v in truth.items()},
      "grand total:", round(sum(truth.values()), 2))
