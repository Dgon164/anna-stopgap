# ANNA STOPGAP — the standalone working build
*(owner ruling 2026-08-19: the stopgap goes HERE; "anna is the math
pure unfinished but untainted one." Anna herself was named
2026-07-30: "its not really isaac. its a subset of his abilities.
We can call it anna, for analyzer.")*

This is the STOPGAP repo: the standalone, clone-and-run working
build — the edge-compute layer, the tester push, the intake fixes,
everything product-wrapper. It moves fast and ships to testers.
The `anna` repo stays the pure product and does not take this
traffic; proven pieces graduate there deliberately, never by
default.

## The family

- **isaac dc** — the datacenter live version (the engine, the
  promoted wall, the business machinery). Private, never ships.
- **isaac-paperclip** — research.
- **anna** — the math-pure product repo, unfinished but untainted.
- **anna-stopgap** (this repo) — the standalone working build:
  reports a client pays for, today, plus the edge layer around them.

## What Anna does

One command turns a messy real-world CSV into a client-ready
report: `report.html` with a KPI band, ranked headlines with
so-what lines, month-over-month with YoY, segments, seasonality
(validated out-of-sample), correlations (shared-trend caution),
concentration, customer base, at-risk customers, coupons, baskets,
returns/reversals with event detection, order whales,
reconciliation (the book that doesn't balance, by row), charts —
and the full receipts beneath. Two tiers of claims, never
conflated: a **certified rule** (the engine's strictest courts) and
a **what's-there description** graded SOLID / WEAK / UNSTABLE by
200 random half-samples plus a persistence test. Where the data
can't support a claim, Anna says so instead of guessing — that
honesty is the product.

    python honest_report.py client.csv --brand "Your Name"
    python honest_report.py client.csv --time date --no-audit
    python honest_report.py client.csv --narrative note.txt
    python honest_report.py client.csv --window 2026-06-01 2026-06-14 --window-label "the promo"
    python clean_file.py dirty.csv --resolution revenue=2.5

## Anna Edge — process once, ask forever

`anna_edge.py` (2026-08-19) is the local edge-compute layer: drop a
file, the full pipeline runs by itself, the processed state is cached
(same bytes never process twice), and from then on you review results
and ask for specifics live — answers are verbatim receipt lines, and
where nothing matches she says so instead of guessing.

    python anna_edge.py add client.csv          # process + cache (instant if unchanged)
    python anna_edge.py watch --drop dropbox    # real-time: new/changed files auto-process
    python anna_edge.py list                    # what is cached
    python anna_edge.py show client             # review the results
    python anna_edge.py ask client "returns by source"   # live query, no reprocessing
    python anna_edge.py report client           # open the full report.html

Build writeup and courts: `docs/BUILD_ANNA_EDGE_2026-08-19.md`.

Requires: Python 3.12+, numpy, matplotlib. **This repo is
STANDALONE** (2026-08-19): clone it and everything runs — the full
department-organ suite, graded what's-there trends, charts, KPIs,
reconciliation, the edge layer. The Isaac engine (a sibling `dc/`
clone or `ISAAC_ENGINE_DIR`) is OPTIONAL: with it, reports add the
certified-rule tier and the audit face; without it, the report says
plainly that nothing was certified. The engine is private and never
ships with this repo. Delimited text only — Excel refused with
instructions, never garbage.

## The record behind her

Every organ passed a planted-truth court AND a blind court on real
unseen data (25k UCI Online Retail; 20k NYC 311), with findings
validated by independent recomputation — including naming a
−52,784 fee-reversal source to the pound and a one-day event
carrying 87% of all negatives. The full history, courts, and the
lens-loop research direction live in `dc/docs/` (see
SESSION_HANDOFF_2026-07-30_INCOME_AND_LENS.md and
DESIGN_LENS_LOOP_2026-07-30.md).

`portfolio/` holds the sample deliverables and `GIG_COPY.md` the
offers, prices, and paste-ready listings.
