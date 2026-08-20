# THE DEMO SCRIPT — a guided tour with the answers in hand
*(for QA and anyone evaluating anna. Every demo file has PLANTED
truths, listed below — so reviewing = checking her answers against
known answers, no data expertise needed. ~15 minutes.)*

## Setup (once)

1. Python 3.12+ · `pip install numpy matplotlib` · clone this repo.
2. **Double-click `START_ANNA.bat`** (or `python anna_ui.py`).
   A page opens at 127.0.0.1 — local only, nothing leaves the
   machine.
3. Faster than the tour: `python demo_data/run_demo_checks.py`
   runs every planted check below automatically and prints
   PASS/FAIL per item.

## The tour (drop files from `demo_data/`)

**1. `business_demo3.csv` — the flagship business file (2,558 rows).**
Expect on the dataset page:
- KPI tiles: Rows 2,558 · Total revenue 636,927.
- Headlines include: **3 row(s) break total=revenue+tax** and
  **5 row(s) break the tax=0.08×revenue rule** — those are planted
  errors; the exact rows are 390, 590, 1702 (totals) and 427, 632,
  1206, 1363, 1966 (tax).
- Ask: *where does the book not balance* → the reconciliation
  section leads with those exact row numbers.
- Ask: *employee salaries by department* → an honest refusal (there
  are no salaries in this data). **A refusal is correct behavior.**

**2. `test_shop.db` — a whole SQLite database (3 tables).**
Expect: "Database processed — 3 tables" (orders, products,
tickets) — EVERY table processed, no query needed. On
test_shop.orders, ask *revenue by region*. Planted truth:

| region | true revenue | true share |
|---|---|---|
| east | 99,960.65 | 60% |
| west | 42,457.22 | 26% |
| north | 23,382.10 | 14% |
| **total** | **165,799.97** | |

She reports east 99,961 (60%) — SOLID, held in 100% of 200 random
half-samples. (`make_demo_db.py` regenerates this db with a fixed
seed; the truths never change.)

**3. `currency_test.csv` — money wearing formatting.**
$1,234.56 / ($500.00) / European 10,50 €. Expect: intake receipts
saying the currency values were converted (8 of 8), and a derived
revenue = qty × price with **total 6,031** (hand truth: 6,030.88).
Also expect her to REFUSE to sum unit prices — a total of prices
means nothing, and she says so.

**4. `dirty_sales.csv` — a deliberately dirty export (62 rows).**
Expect receipts for: a skipped title row, delimiter conversion
(semicolons), a blanked missing-value marker. On 62 rows most
grades are honestly **UNSTABLE** — small data should not produce
confident claims. That's the honesty working, not a weakness.

**5. `refusals/` — she refuses rather than guesses.**
- `empty.csv` → plain refusal page (no crash, no empty report).
- `mysql_flavored_dump.sql` → refusal naming the dialect problem
  and what to do instead.
- Any Excel .xlsx → refusal with save-as-CSV instructions.

**6. Speed.** Re-drop `business_demo3.csv` — instant (cache hit;
same bytes never process twice). The home question box searches
every dataset you've dropped, at once.

## What to file as a bug (and what not)

BUG: a number that doesn't match the planted truths above; a crash
or raw traceback; a claim without a receipt; a WEAK/UNSTABLE claim
presented as confident; anything confusing in the UI.
NOT A BUG: refusals (empty files, Excel, unsupported dialects,
"no rule certified", "nothing matches") — refusing rather than
guessing is the product. If a refusal's WORDING is unclear, file
that.

## For the UI developer

The reference UI (`anna_ui.py`) is a stopgap. A real UI should sit
on the local JSON API — endpoints, the state schema, and the
honesty rules a UI must preserve are in `docs/API.md`.
