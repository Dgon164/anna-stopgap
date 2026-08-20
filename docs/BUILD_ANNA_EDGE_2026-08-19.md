# ANNA EDGE — the local edge-compute layer (build writeup, 2026-08-19)

*(Owner's brief, paraphrased from the ask: a stopgap build to make sure data
processing is down cold — detect everything, no specifying or limiting
anything, live information query against the processed state, real-time
input or cached processing, local edge compute for data queries. "It does
the job of the live real-time data analyzer for you — just review the
results and ask for specifics.")*

## What was found before building

- Anna (bab84b3) already IS the detect-everything stopgap: one command,
  no columns named, full organ suite. Smoke-tested this session against
  the sibling dc engine: business_demo3, 2558 rows, analyst face 7.5s,
  report rendered. GREEN.
- What did NOT exist anywhere (this machine or GitHub): persistence.
  Every run was one-shot — process, render, forget. No cache, no live
  query, no watch road. That gap is what this build fills.

## What was built

`anna_edge.py` (anna root, beside honest_report.py). Storefront-side
only: it reuses honest_report's pipeline functions untouched and the
promoted engine untouched. Three additions, none of them analysis:

1. **THE STORE** — every processed dataset's full state cached under
   `edge_store/<name>/`: state.json (KPIs, headlines, every section's
   lines, per-column engine verdicts/equations, described grades,
   audit verdict, column kinds), the normalized table, receipts,
   charts, report.html. Cache key = sha256 of the file bytes: same
   bytes never process twice (measured hit: 0.18s vs ~14s full run),
   changed bytes always reprocess.
2. **THE WATCH ROAD** — `watch --drop DIR`: polls a drop folder;
   any new or changed delimited file processes itself, hands-off.
   Mid-copy files skipped until whole; a failing file is reported and
   not retried until its bytes change (no crash loops).
3. **THE QUERY ROAD** — `ask [name] "question"`: keyword+synonym
   routing over the cached sections and findings; every line returned
   is VERBATIM from the cached receipts — retrieval only, no
   generation. No dataset named = searches every cached dataset.
   Nothing matches = says so and lists what IS cached, never guesses.

Commands: `add`, `watch`, `list`, `show`, `ask`, `report` (opens the
html). `edge_store/` and `dropbox/` added to .gitignore — client data
never reaches GitHub (standing privacy law).

## The courts (all green)

- **Cache court:** re-add of identical bytes = hit in 0.18s, zero
  engine calls; appended row = hash change detected, full reprocess.
- **Planted court (numbers):** independent recompute from the raw CSV
  (plain csv module, no shared code): revenue by region east 284,853
  (44.7%) / west 231,936 / north 120,138, grand total 636,927 — the
  cached claims match to the digit. Demo3's planted reconciliation
  truths (3 rows breaking total=revenue+tax, 5 breaking tax=0.08×rev)
  surface in the cached headlines with the exact row numbers.
- **Query court:** "where does the book not balance" → reconciliation
  section first. "which customers are at risk" → going-quiet organ
  with named whales. Cross-dataset ask works unnamed.
- **Refusal court:** "employee salaries by department" FIRST FAILED —
  the word "by" sat in a synonym group and dragged three unrelated
  sections in. Wound cured (stopword strip + synonym fix); the same
  question now refuses honestly and lists what is cached. Real
  queries re-courted after the fix: still route correctly.
- **Watch court:** watcher live at 2s interval; dirty_sales.csv
  dropped in mid-watch → intake (3 normalization notes on the
  deliberately dirty file) → analyst → cached, no human step.

## Honest limits (said, not hidden)

- The query road is keyword retrieval over what the organs already
  computed — it cannot answer a question no organ asked (that is the
  lens loop's territory, engine-side, research-gated).
- Watch = polling, not push; interval 5s default. Fine for a drop
  folder; not a message bus.
- The sellability-audit intake blockers (currency-as-text, 0-byte
  crash) live in honest_report's normalize and are inherited here —
  still the flagship's ~one-session fix list, untouched by this build.
- Uncommitted as of this writeup; nothing here touches dc.

## Part 2 (same day): the three sellability blockers CURED

Owner's context: v1 goes to outside testers; owner validates via
checklist, not expertise. The July-30 audit's blockers were exactly
what first testers would hit, so they were fixed first — all in
honest_report's intake/engine layers, inherited by anna_edge free.

1. **Currency-as-text** — new intake pass `read_formatted_numbers`:
   a column ≥80% formatted numbers ($1,234.56 / 105,50 € / (500.00)
   parens-negative / 1.234.567 dot-thousands) is converted in place,
   date-shaped values excluded, every conversion receipted. COURT:
   planted file converted 8/8 values exactly; the semantics layer
   then rightly refused to SUM per-unit prices and derived
   revenue=qty×price, total 6,031 vs hand-computed 6,030.88. GREEN.
2. **Relative --out hollow report** — out_dir forced absolute
   (engine runs with cwd=DC and used to get a path that existed
   only from anna's cwd), AND run_engine now refuses loudly when
   the engine returns nothing (a dead engine must never ship as a
   polished report). COURT: relative --out from a foreign cwd now
   produces a real report with 3,281-byte receipts. GREEN.
3. **0-byte crash** — plain refusals for: empty/blank file, header
   with no data rows, every-row-quarantined. COURT: all three
   messages plain, exit 1, zero tracebacks. GREEN.

Regression court: business_demo3 reprocessed through the new intake —
east 284,853 / west 231,936 / north 120,138 / total 636,927 all
unchanged to the digit. anna_edge's watcher taught to survive the new
refusals (a refused file logs and skips; the watch never dies).

Also written for the v1 push: `docs/OWNER_CHECK.md` (the owner-review
law as a 5-minute no-expertise checklist) and `docs/TESTER_GUIDE.md`
(handout for the test guys: two test paths, what to throw at her,
the 5-question feedback template, known-limits list so honesty isn't
filed as bugs).

**Distribution DECIDED (owner, same day): "the github anna stopgap
repo should be standalone." Built as ENGINE-OPTIONAL, part 3:**
- `engine_available()` — a sibling dc clone (or ISAAC_ENGINE_DIR)
  is now optional. Present: full two-tier reports, unchanged.
  Absent: STANDALONE mode — the entire descriptive suite still runs
  (it always lived in this repo: department organs, SOLID/WEAK/
  UNSTABLE graded trends, charts, KPIs, reconciliation, the edge
  layer); findings are synthesized from anna's own column
  classification; time column falls back to the first date-kind
  column; the report carries an "About this standalone build"
  section saying nothing was certified. The private engine never
  ships. plain_summary grew a verdict-None branch so described
  trends speak alone, plainly labeled.
- COURTS: standalone honest_report on demo3 → full report, graded
  what's-there per column, all organs (reconciliation catches
  intact — they are anna's own), standalone note present, no empty
  receipts file. Standalone anna_edge → add/cache/ask all work,
  book-balance rows surface identically. Engine-present regression
  → analyst face 7.2s, receipts full, 636,927 / east 45% unchanged.
- Testers can now clone anna and run hands-on (TESTER_GUIDE Path B
  updated); the certified tier stays a compare-and-upsell: "our
  systems also run the strictest law courts."

**Still-filed majors (not blockers, from the same audit):** no dedupe
in the one-command flow; Online/online/ONLINE case-variants split
segments; TOTAL footer rows counted as data; date-range
self-contradiction on unsorted files; per-column time charts skipped
on ISO-date x; GIG_COPY.md still says `standalone/` paths.

## Part 4 (same day, in anna-stopgap): THE HUMAN ROAD + DATABASES + FEEDS

Owner: "make it intuitive and human usable" + "take sql and other
database inputs, direct feeds, and be fast, as well as be able to
process entire db instead of just the standard only what is
returned."

1. **anna_ui.py + START_ANNA.bat** — double-click, a page opens
   (127.0.0.1 only, nothing leaves the machine): drag-drop → auto-
   process with a live status page → KPI tiles, headlines, every
   section expandable, a question box per dataset AND one across
   everything, full report one click away, honest refusal pages for
   Excel/binary/empty files, delete button. Stdlib http.server —
   zero new dependencies. COURTS: home, upload→303→status→dataset
   page, ask verbatim, refusal, 149KB report served, docs pages.
   WOUND FOUND+CURED in court: the multipart parser stripped ALL
   trailing \r\n bytes — corrupting binary (SQLite) uploads; the
   format guarantees exactly one, now exactly one is stripped.
2. **Whole-database intake** — `export_database` + `process_any`:
   an SQLite file or SQLite-compatible .sql dump is exported table
   by table (EVERY table, never one query's view) into receipted
   CSVs, each becoming its own cached dataset `<db>.<table>`; add/
   watch/feed/UI all take them. Wrong-dialect dumps and non-SQLite
   binaries refused plainly with what-to-do-instead. Live server
   connections (Postgres/MySQL) NOT wired — filed, needs drivers.
   COURTS on a 3-table planted db: every table processed; region
   revenue east 99,961 (60%, SOLID) vs planted 99,960.65 — to the
   cent; dump twin ingested identically; both refusals fired.
3. **Direct feeds** — `feed <url>`: polls a link (any delimited
   file, db, or dump served over HTTP), sha256-compares, downloads
   and reprocesses the moment content changes; fetch errors retry,
   refused content doesn't crash the loop. COURT: served a CSV
   locally, appended mid-feed → change detected, reprocessed; a
   proper append re-court confirmed the new row counted (63 rows).
4. **Ask ranking wound cured**: "revenue by region" tied the
   profile block with the groups-compare block (where the number
   lives) and lost on order — cured with a verbatim-phrase bonus;
   re-courted, the right section leads with the planted numbers.
5. **Speed**, honestly stated: the cache is the speed story —
   already-seen bytes are instant (0.18s vs ~14s); a whole db warms
   table by table once, then every ask is instant. `--no-audit`
   available where the audit face is the cost.

## Part 5 (same day): THE QA PACKAGE

Owner: "we need a testing demo and datasets. i need to get my qa in
on this to review it and develop a ui for it as well."

- **demo_data/**: business_demo3.csv (planted book errors, rows
  390/590/1702 + 427/632/1206/1363/1966), test_shop.db (3 tables,
  seeded generator make_demo_db.py, region truth to the cent),
  currency_test.csv (formatted money, hand truth 6,030.88),
  dirty_sales.csv (honest UNSTABLE on 62 rows), refusals/ (empty
  file, wrong-dialect dump).
- **docs/DEMO_SCRIPT.md**: the 15-minute guided tour with every
  planted answer listed — QA review = checking against known
  answers; includes the bug-vs-not-a-bug line (refusals are the
  product).
- **demo_data/run_demo_checks.py**: all planted truths asserted
  automatically — COURTED 13/13 with the engine AND 13/13
  standalone (QA machines won't have the engine).
- **THE JSON API** (for the UI developer): /api/datasets,
  /api/dataset/<name>, /api/ask, /api/upload (multipart),
  /api/status/<job> on the same local server; docs/API.md carries
  the state schema and THE HONESTY RULES A UI MUST PRESERVE
  (grades never upgraded, refusals rendered as answers, numbers
  verbatim, receipts one click away, standalone said). COURTED:
  all five routes returning valid JSON end-to-end including
  upload→status→done.

## Repo state noticed while checking (for the owner)

dc has two pieces newer than its last commit (02db3b8): untracked
docs/DESIGN_REPAIR_GRAMMAR_2026-08-02.md + audit.jsonl. That design
doc names a companion probe lens_research/repair_policy_probe.py —
THE PROBE WAS NEVER BUILT. The repair-grammar road is designed,
not yet courted.
