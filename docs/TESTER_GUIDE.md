# ANNA — tester guide (v1, 2026-08-19)

Thanks for kicking the tires. Anna is a data analyst that would
rather say "no rule here" than make something up — every number in
her reports traces to a receipt in the same file, and her claims
carry grades (SOLID / WEAK / UNSTABLE) from re-testing on 200 random
half-samples of your data. **A refusal is a feature, not a crash.**
You're testing whether that honesty holds up on YOUR real files.

## Two ways to test

**Path A — send a file (easiest, default).** Send any real CSV
(messy is better — that's the point). You get back `report.html`:
open it in any browser, everything is embedded, nothing phones home.
Your data is processed locally, never uploaded anywhere, never fed
into any learning system, and deleted on request.

**Path B — hands-on (the repo is standalone).** Needs only
Python 3.12+, numpy, matplotlib — clone and run:

    python honest_report.py yourfile.csv          # one-shot client report
    python anna_edge.py add yourfile.csv          # process once, cache
    python anna_edge.py show yourfile             # review the results
    python anna_edge.py ask yourfile "returns by region"   # ask live
    python anna_edge.py watch --drop dropbox      # drop files, they process themselves

One honest note: the standalone build runs the full descriptive
suite (everything above), but the extra certified-rule tier — our
strictest law courts — runs on our systems only. Standalone reports
say so right in the report; nothing is dressed up as certified.

## What we want you to throw at it

- Your ugliest real spreadsheet exports (extra header rows, currency
  symbols, blank lines, missing values, duplicate rows).
- Sales/transactions data if you have it — that's where the organ
  suite is deepest (customers, returns, whales, coupons, baskets,
  reconciliation).
- Files where YOU already know a fact ("March was our worst month",
  "one customer is half our revenue") — then check whether anna
  found it, and at what grade.
- Questions via `ask` phrased YOUR way, not ours.

## What to write down (per file — this is the whole ask)

1. Did it run? If not, paste the exact message.
2. Any number that looks WRONG — which one, and what you believe the
   true value is. (This is the most valuable feedback there is; the
   guarantee is built on numbers tracing.)
3. A question you wanted answered that the report didn't answer.
4. Anything that confused you — a word, a section, a grade.
5. Would you pay for this report? What's missing before you would?

## Known limits (please don't file these as bugs)

- Excel .xlsx is refused on purpose — save as CSV first (File >
  Save As > CSV). Binary files are refused rather than guessed at.
- Data covering under ~30 days gets no customer-loyalty claims —
  short windows lie, so anna won't use them for that.
- "No law-grade rule certified" on a column is an honest verdict,
  not an error.
- Very wide files: the full audit face can take 10+ minutes; the
  default report skips nothing you'd notice.
