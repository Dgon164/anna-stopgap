# THE LOCAL JSON API — for UI builders

`python anna_ui.py` serves the reference page AND a JSON API on the
same local port (default `http://127.0.0.1:8765`). Bound to
127.0.0.1 only; client data never leaves the machine. Build any UI
on these five routes — the reference page uses the same store and
functions, so behavior always matches.

## Routes

| Route | Method | Returns |
|---|---|---|
| `/api/datasets` | GET | `{engine_connected, datasets:[{name, rows, cols, processed_at, engine_secs, source, sha256}]}` |
| `/api/dataset/<name>` | GET | the full processed state for one dataset (schema below); 404 `{error}` if unknown |
| `/api/ask?q=<question>&name=<optional>` | GET | `{question, results:[{dataset, hits:[{score, title, lines}]}], refusal}` — `name` limits to one dataset, else all. Empty `results` + `refusal` text = honest no-match, NOT an error |
| `/api/upload` | POST multipart (`file` field) | `{job, status_url}`; 422 `{refusal}` for unsupported/binary types. CSV/TSV/text, SQLite `.db`, or `.sql` dump — a database becomes one dataset PER TABLE |
| `/api/status/<job>` | GET | `{done, error, names}` — poll until `done`; `error` set = honest refusal text; `names` = datasets created (several for a database) |

The finished client report is plain HTML at `/d/<name>/report`
(self-contained, charts embedded) — link or iframe it.

## The dataset state (what `/api/dataset/<name>` returns)

- `name, source, sha256, processed_at, rows, header[]` — identity.
- `kinds{col: kind}` — date / numeric / rate (per-unit, never
  summed) / identifier (label wearing numbers, never summed) /
  coordinate / category / text.
- `kpis[{label, value, sub}]` — the five-second numbers, ready for
  stat tiles (values pre-humanized: "636,927").
- `headlines[]` — ranked one-liners; lines starting `- ↳` are the
  so-what follow-up of the line above.
- `sections[{title, lines[]}]` — everything found, in plain-English
  markdown-ish lines (`**bold**`, `![chart](...)` references live
  in the full report).
- `findings[{name, verdict, equation, books, cycle, forecast,
  lines}]` — per-column engine verdicts (verdict null in standalone
  builds or where none).
- `described{col: {grade, slope, total}}` — the what's-there trend
  per column, grade SOLID / WEAK / UNSTABLE.
- `audit` — the audit face verdict/counts/flags, or null.
- `standalone` — true when the certified-rule tier was not run;
  the UI must say so (see rules).
- `notes[]` — intake receipts (what was changed/quarantined/
  converted); show them, clients pay for them.
- `report` — absolute path of report.html (serve via
  `/d/<name>/report`, not the path).

## The honesty rules a UI MUST preserve

These are the product. A UI that breaks them isn't anna.

1. **Grades are never upgraded or hidden.** SOLID may be stated as
   a finding; WEAK/UNSTABLE keep hedged wording; UNSTABLE is
   "we'd call this spurious," not a smaller font of confident.
2. **Refusals are answers, rendered as answers** — never as error
   toasts, never retried, never papered over. Empty ask results
   show the refusal text.
3. **Numbers come from the state verbatim** — never recomputed,
   reformatted into different precision, or summarized by an LLM.
   Every number on screen must exist in the state or the report.
4. **Receipts stay reachable** — one click from any claim to the
   full report / notes that back it.
5. **`standalone: true` is shown** — "nothing here is certified"
   in visible text, exactly because it's true.
6. Identifier/rate columns: never render sums for them (the state
   never contains such sums — don't invent them client-side).

## Lifecycle example

    POST /api/upload  (file=shop.db)      -> {status_url}
    GET  {status_url}  ... poll ...        -> {done:true, names:["shop.orders","shop.products"]}
    GET  /api/dataset/shop.orders          -> state (tiles, headlines, sections)
    GET  /api/ask?q=revenue+by+region      -> verbatim receipt hits across datasets
    GET  /d/shop.orders/report             -> the client-ready HTML report

Planted-truth demo data for testing any UI lives in `demo_data/`
with expected answers in `docs/DEMO_SCRIPT.md`;
`python demo_data/run_demo_checks.py` asserts them automatically.
