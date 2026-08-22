"""ANNA EDGE — the local edge-compute layer around the honest report.

The stopgap the owner asked for (2026-08-19): drop a file, everything
gets processed automatically — no columns to name, no analysis to
specify — the full processed state is CACHED, and from then on you
review the results and ask for specifics LIVE, without reprocessing.
Machinery, not mind: this file reuses honest_report's storefront
pipeline untouched and the promoted engine untouched; it adds only a
store and a query road over what was already computed. Every answer
is a verbatim line from the cached receipts — where nothing in the
cache matches, the answer says so instead of guessing.

    python anna_edge.py add client.csv            # process + cache (instant if unchanged)
    python anna_edge.py watch --drop dropbox      # real-time: new/changed files auto-process
    python anna_edge.py list                      # what is cached
    python anna_edge.py show client               # review the results (plain English)
    python anna_edge.py ask client "returns by source"   # live query against the cache
    python anna_edge.py ask "biggest customers"   # no name = search every cached dataset
    python anna_edge.py report client             # open the full report.html

Store: edge_store/ beside this file (or --store DIR). One folder per
dataset holding state.json, the normalized table, receipts, charts,
and report.html. Cache key = file content hash: the same bytes never
process twice; changed bytes always do.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE_DIR)

import honest_report as hr                      # noqa: E402
from analyst_full import (build_extras,         # noqa: E402
                          classify_columns)

DATA_EXTS = {".csv", ".tsv", ".txt"}
DB_EXTS = {".db", ".sqlite", ".sqlite3"}
SQL_EXTS = {".sql"}


# ---------------------------------------------------------------- store
def store_dir(args):
    d = args.store or os.path.join(HERE_DIR, "edge_store")
    os.makedirs(d, exist_ok=True)
    return d


def index_path(store):
    return os.path.join(store, "index.json")


def load_index(store):
    p = index_path(store)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}


def save_index(store, idx):
    with open(index_path(store), "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=1)


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jsonable(x):
    """Down-convert numpy/dates so the state survives json — values
    only, never invented."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if x is None or isinstance(x, (str, bool, int, float)):
        return x
    if hasattr(x, "item"):
        try:
            return x.item()
        except Exception:
            pass
    if hasattr(x, "isoformat"):
        return x.isoformat()
    return str(x)


# ---------------------------------------------------------------- process
def process(source, store, time_col=None, audit=True, force=False,
            quiet=False):
    """Run the FULL honest-report pipeline once and cache everything.
    Same bytes = cache hit, nothing reruns. Returns the dataset name."""
    digest = file_digest(source)
    idx = load_index(store)
    name = os.path.splitext(os.path.basename(source))[0]
    prior = idx.get(name)
    if prior and prior["sha256"] != digest and \
            os.path.abspath(prior["source"]) != os.path.abspath(source):
        # a DIFFERENT file wearing the same stem — keep both honestly
        name = f"{name}-{digest[:6]}"
        prior = idx.get(name)
    if prior and prior["sha256"] == digest and not force:
        if not quiet:
            print(f"{name}: unchanged (cache hit) — processed "
                  f"{prior['processed_at']}, {prior['rows']} rows. "
                  f"Ask away.")
        return name

    out_dir = os.path.join(store, name)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.perf_counter()
    rows, header, notes = hr.normalize(source)
    notes += hr.normalize_dates(rows, header)
    notes += hr.derive_measures(rows, header)
    norm_csv = os.path.join(out_dir, f"{name}.normalized.csv")
    hr.write_csv(rows, header, norm_csv)
    if not quiet:
        print(f"{name}: intake {len(rows)} rows x {len(header)} cols; "
              f"{len(notes)} normalization note(s)", flush=True)

    standalone = not hr.engine_available()
    analyst_text, t1 = ("", 0.0)
    audit_text, t2 = ("", 0.0)
    if standalone:
        if not quiet:
            print(f"{name}: standalone build — certified tier off, "
                  f"what's-there tier only (said in the report)",
                  flush=True)
    else:
        eng_csv = hr.engine_input(rows, header, norm_csv, notes)
        extra = ["--analyst"] + (["--time", time_col]
                                 if time_col else [])
        analyst_text, t1 = hr.run_engine(eng_csv, extra)
        if not quiet:
            print(f"{name}: analyst face {t1:.1f}s", flush=True)
        if audit:
            audit_text, t2 = hr.run_engine(eng_csv, ["--audit"])
            if not quiet:
                print(f"{name}: audit face {t2:.1f}s", flush=True)

    kinds = classify_columns(rows, header)
    if standalone:
        findings = hr.standalone_findings(header, kinds)
    else:
        findings = [f for f in hr.parse_analyst(analyst_text)
                    if kinds.get(f["name"], {}).get("kind")
                    not in ("identifier", "coordinate")]
    audit_d = hr.parse_audit(audit_text) if audit_text else None
    tcol = time_col
    if not tcol and analyst_text:
        m = re.search(r"time key: (.+?) \(", analyst_text)
        if m:
            tcol = m.group(1).strip()
    if not tcol:
        tcol = next((h for h in header
                     if kinds.get(h, {}).get("kind") == "date"),
                    None)
    ts = time.perf_counter()
    described = hr.describe_columns(rows, header, findings, tcol)
    chart_dir = os.path.join(out_dir, "charts")
    charts = hr.make_charts(rows, header, findings, tcol, chart_dir,
                            described)
    if not quiet:
        print(f"{name}: describe+charts "
              f"{time.perf_counter() - ts:.1f}s", flush=True)
    ts = time.perf_counter()
    try:
        heads, blocks, kpis = build_extras(rows, header, tcol,
                                           described, chart_dir, None)
    except Exception as e:
        heads = ["## The headlines", "",
                 f"- the full-analytics pass could not run "
                 f"({type(e).__name__}: {e}) — everything else in "
                 f"this state is unaffected; we say so rather than "
                 f"hide it", ""]
        blocks, kpis = [], []

    if not quiet:
        print(f"{name}: analytics blocks "
              f"{time.perf_counter() - ts:.1f}s", flush=True)
    if analyst_text:
        with open(os.path.join(out_dir, "receipts_analyst.txt"), "w",
                  encoding="utf-8") as f:
            f.write(analyst_text)
    if audit_text:
        with open(os.path.join(out_dir, "receipts_audit.txt"), "w",
                  encoding="utf-8") as f:
            f.write(audit_text)
    ts = time.perf_counter()
    hr.render(name, header, len(rows), notes, findings, audit_d,
              charts, analyst_text, audit_text, out_dir, t1 + t2,
              described, (heads, blocks, kpis), None, None)
    if not quiet:
        print(f"{name}: render {time.perf_counter() - ts:.1f}s",
              flush=True)

    # split the block markdown into named sections for the query road
    sections, cur = [], None
    for ln in blocks:
        if ln.startswith("## "):
            cur = dict(title=ln[3:].strip(), lines=[])
            sections.append(cur)
        elif cur is not None:
            cur["lines"].append(ln)

    state = dict(
        name=name, source=os.path.abspath(source), sha256=digest,
        processed_at=datetime.now().isoformat(timespec="seconds"),
        rows=len(rows), header=header,
        kinds={h: kinds.get(h, {}).get("kind", "?") for h in header},
        notes=notes,
        kpis=kpis,
        headlines=[ln for ln in heads if ln.startswith("- ")],
        sections=sections,
        findings=[dict(name=f["name"], verdict=f["verdict"],
                       equation=f["equation"], books=f["books"],
                       cycle=f["cycle"], forecast=f["forecast"],
                       lines=f["lines"]) for f in findings],
        described={k: dict(grade=v["d"].get("grade"),
                           slope=v["d"].get("slope"),
                           total=v["d"].get("total"))
                   for k, v in (described or {}).items()},
        audit=audit_d, time_col=tcol, standalone=standalone,
        engine_secs=round(t1 + t2, 1),
        total_secs=round(time.perf_counter() - t0, 1),
        report=os.path.join(out_dir, "report.html"),
    )
    with open(os.path.join(out_dir, "state.json"), "w",
              encoding="utf-8") as f:
        json.dump(jsonable(state), f, indent=1)

    idx[name] = dict(source=state["source"], sha256=digest,
                     processed_at=state["processed_at"],
                     rows=len(rows), cols=len(header),
                     engine_secs=state["engine_secs"])
    save_index(store, idx)
    if not quiet:
        print(f"{name}: cached — total wall clock "
              f"{state['total_secs']}s — report -> "
              f"{state['report']}", flush=True)
    return name


def export_database(path, store):
    """EVERY table, whole — never just what one query returns. Each
    user table is exported to a receipted CSV and becomes its own
    cached dataset named <db>.<table>. SQLite files and
    SQLite-compatible .sql dumps; anything else refused plainly."""
    import sqlite3
    stem = os.path.splitext(os.path.basename(path))[0]
    ext = os.path.splitext(path)[1].lower()
    if ext in SQL_EXTS:
        con = sqlite3.connect(":memory:")
        try:
            con.executescript(open(path, encoding="utf-8-sig",
                                   errors="replace").read())
        except sqlite3.Error as e:
            raise SystemExit(
                f"REFUSED: could not run "
                f"{os.path.basename(path)} as a SQL script ({e}). "
                f"SQLite-compatible dumps only for now — a "
                f"Postgres/MySQL-dialect dump needs converting, or "
                f"export the tables to CSV.")
    else:
        with open(path, "rb") as f:
            magic = f.read(16)
        if not magic.startswith(b"SQLite format 3"):
            raise SystemExit(
                f"REFUSED: {os.path.basename(path)} is not an "
                f"SQLite database file. Live server databases "
                f"(Postgres/MySQL) aren't wired yet — export to "
                f"SQLite or CSV and drop that instead. Said "
                f"honestly rather than guessed at.")
        con = sqlite3.connect(path)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if not tables:
        raise SystemExit(f"REFUSED: no tables found in "
                         f"{os.path.basename(path)}.")
    exp_dir = os.path.join(store, "_db_exports", stem)
    os.makedirs(exp_dir, exist_ok=True)
    out = []
    for t in tables:
        cur = con.execute(f'SELECT * FROM "{t}"')
        header = [c[0] for c in cur.description]
        safe_t = re.sub(r"[^-\w. ]", "_", t)
        csv_path = os.path.join(exp_dir, f"{stem}.{safe_t}.csv")
        with open(csv_path, "w", newline="",
                  encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for row in cur:
                w.writerow(["" if v is None else v for v in row])
        out.append((t, csv_path))
    con.close()
    return out


def process_any(source, store, time_col=None, audit=True,
                force=False, quiet=False):
    """One entry for every input shape. A delimited file = one
    dataset; a database = one dataset PER TABLE, all of them.
    Returns the list of dataset names."""
    ext = os.path.splitext(source)[1].lower()
    if ext in DB_EXTS | SQL_EXTS:
        tables = export_database(source, store)
        if not quiet:
            print(f"{os.path.basename(source)}: database — "
                  f"{len(tables)} table(s); processing the WHOLE "
                  f"database, every table", flush=True)
        return [process(p, store, time_col=None, audit=audit,
                        force=force, quiet=quiet)
                for _, p in tables]
    return [process(source, store, time_col=time_col, audit=audit,
                    force=force, quiet=quiet)]


def load_state(store, name):
    p = os.path.join(store, name, "state.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------- query
SYNONYMS = {
    "revenue": {"revenue", "sales", "money", "income", "total"},
    "customer": {"customer", "customers", "client", "clients",
                 "buyer", "buyers", "base", "repeat", "loyalty",
                 "guest"},
    "return": {"return", "returns", "refund", "refunds", "negative",
               "negatives", "reversal", "reversals", "writeoff",
               "write-offs", "chargeback"},
    "whale": {"whale", "whales", "biggest", "largest", "top",
              "concentration", "order", "orders"},
    "trend": {"trend", "trends", "rising", "falling", "growth",
              "decline", "forecast", "trajectory"},
    "season": {"season", "seasonal", "seasonality", "weekday",
               "weekly", "monthly", "month", "months", "period",
               "periods", "cycle", "yoy"},
    "segment": {"segment", "segments", "region", "regions",
                "product", "products", "category", "breakdown"},
    "risk": {"risk", "at-risk", "churn", "lapsed", "leaving"},
    "coupon": {"coupon", "coupons", "discount", "discounts",
               "promo", "promotion"},
    "basket": {"basket", "baskets", "together", "pairs", "combo"},
    "reconcile": {"reconcile", "reconciliation", "balance", "books",
                  "mismatch", "audit"},
    "anomaly": {"anomaly", "anomalies", "outlier", "outliers",
                "spike", "spikes", "unusual", "event", "events"},
    "relationship": {"relationship", "relationships", "correlation",
                     "correlations", "related", "law", "laws",
                     "equation"},
    "profile": {"profile", "columns", "schema", "fields", "shape",
                "coverage"},
}


def _expand(words):
    out = set(words)
    for w in words:
        for group in SYNONYMS.values():
            if w in group:
                out |= group
    return out


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 1}


# grammar words carry no content — matching on them once dragged
# three unrelated sections into an answer that should have refused
STOP = {"the", "an", "of", "in", "on", "for", "by", "to", "and",
        "or", "with", "what", "which", "who", "how", "where",
        "when", "is", "are", "was", "were", "does", "do", "did",
        "show", "me", "my", "about", "tell", "give", "get", "any",
        "all", "much", "many", "there", "this", "that", "it", "at"}


def ask_one(state, question):
    """Score every cached section/finding against the question and
    return the best matches VERBATIM. No generation — retrieval only."""
    q = _expand(_words(question) - STOP)
    ql = " ".join(question.lower().split())
    scored = []
    for sec in state["sections"]:
        title_w = _words(sec["title"])
        body_text = " ".join(sec["lines"]).lower()
        body_w = _words(body_text)
        score = 3 * len(q & title_w) + min(len(q & body_w), 4)
        # the question appearing VERBATIM in a section beats
        # word-bag ties ("revenue by region" names its own block)
        if len(ql) > 3 and ql in body_text:
            score += 5
        if score:
            scored.append((score, f"## {sec['title']}", sec["lines"]))
    for f in state["findings"]:
        col_w = _words(f["name"])
        if q & col_w:
            hdr = f"── {f['name']} ── " \
                  f"[{f['verdict'] or 'described only'}]"
            scored.append((3 * len(q & col_w) + 1, hdr, f["lines"]))
    head_w = _words(" ".join(state["headlines"]))
    if q & head_w and not scored:
        scored.append((1, "## The headlines", state["headlines"]))
    scored.sort(key=lambda s: -s[0])
    return scored[:3]


def cmd_ask(args, store):
    idx = load_index(store)
    if not idx:
        print("nothing cached yet — `add` a file or start `watch`.")
        return
    # "ask <name> <question>" or "ask <question>" across everything
    parts = args.query
    names = list(idx)
    if parts and parts[0] in names:
        targets, question = [parts[0]], " ".join(parts[1:])
    else:
        targets, question = names, " ".join(parts)
    if not question.strip():
        print("ask what? e.g.  anna_edge.py ask "
              f"{targets[0]} \"returns by source\"")
        return
    any_hit = False
    for name in targets:
        state = load_state(store, name)
        if not state:
            continue
        hits = ask_one(state, question)
        if not hits:
            continue
        any_hit = True
        print(f"\n=== {name} (processed {state['processed_at']}, "
              f"{state['rows']} rows) ===")
        for _, title, lines in hits:
            print(title)
            for ln in lines:
                if ln.strip():
                    print(ln)
            print()
    if not any_hit:
        print(f"nothing in the processed state matches "
              f"\"{question}\" — that is the honest answer, not a "
              f"guess. What IS cached:")
        for name in targets:
            state = load_state(store, name)
            if state:
                titles = ", ".join(s["title"]
                                   for s in state["sections"])
                print(f"  {name}: {titles}")


def cmd_show(args, store):
    state = load_state(store, args.name)
    if not state:
        print(f"no cached dataset named '{args.name}' — see `list`.")
        return
    print(f"{state['name']} — {state['rows']} rows x "
          f"{len(state['header'])} cols, processed "
          f"{state['processed_at']} (engine {state['engine_secs']}s)")
    print(f"source: {state['source']}")
    if state["kpis"]:
        print("\nthe five-second numbers:")
        for k in state["kpis"]:
            sub = f"  ({k['sub']})" if k.get("sub") else ""
            print(f"  {k['label']}: {k['value']}{sub}")
    if state["headlines"]:
        print("\nthe headlines:")
        for ln in state["headlines"]:
            print(f"  {ln}")
    print("\nsections you can `ask` about: "
          + ", ".join(s["title"] for s in state["sections"]))
    print(f"full report: {state['report']}")


def cmd_list(args, store):
    idx = load_index(store)
    if not idx:
        print("nothing cached yet — `add` a file or start `watch`.")
        return
    for name, e in sorted(idx.items()):
        print(f"{name}: {e['rows']} rows x {e['cols']} cols, "
              f"processed {e['processed_at']} "
              f"(engine {e['engine_secs']}s) — {e['source']}")


def cmd_report(args, store):
    state = load_state(store, args.name)
    if not state:
        print(f"no cached dataset named '{args.name}' — see `list`.")
        return
    print(state["report"])
    if os.name == "nt" and not args.path_only:
        os.startfile(state["report"])


def cmd_watch(args, store):
    drop = os.path.abspath(args.drop)
    os.makedirs(drop, exist_ok=True)
    print(f"watching {drop} every {args.interval}s — drop delimited "
          f"files (csv/tsv/txt) and they process themselves. Ctrl+C "
          f"to stop.", flush=True)
    seen = {}
    while True:
        for fn in sorted(os.listdir(drop)):
            path = os.path.join(drop, fn)
            if not os.path.isfile(path) or \
                    os.path.splitext(fn)[1].lower() not in \
                    DATA_EXTS | DB_EXTS | SQL_EXTS:
                continue
            try:
                digest = file_digest(path)
            except OSError:
                continue    # mid-copy; next pass gets it whole
            if seen.get(path) == digest:
                continue
            try:
                process_any(path, store, time_col=None,
                            audit=not args.no_audit)
                seen[path] = digest
            except (Exception, SystemExit) as e:
                # a refused file (empty, binary, dead engine) must
                # not kill the watch — logged, skipped until changed
                print(f"{fn}: FAILED ({type(e).__name__}: {e}) — "
                      f"will not retry until the file changes",
                      flush=True)
                seen[path] = digest
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("watch stopped.")
            return


def cmd_feed(args, store):
    """The direct-feed road: poll a link; the moment its bytes
    change, download and reprocess. Any URL serving a delimited
    file, an SQLite database, or a SQL dump."""
    fname = os.path.basename(
        urllib.parse.urlparse(args.url).path) or "feed.csv"
    if os.path.splitext(fname)[1].lower() not in \
            DATA_EXTS | DB_EXTS | SQL_EXTS:
        fname += ".csv"
    if args.name:
        fname = args.name + os.path.splitext(fname)[1]
    dest_dir = os.path.join(store, "feeds")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, fname)
    print(f"feeding from {args.url} every {args.interval}s — "
          f"reprocesses the moment the content changes. Ctrl+C to "
          f"stop.", flush=True)
    last = None
    while True:
        try:
            data = urllib.request.urlopen(args.url,
                                          timeout=60).read()
            digest = hashlib.sha256(data).hexdigest()
            if digest != last:
                with open(dest, "wb") as f:
                    f.write(data)
                try:
                    process_any(dest, store,
                                audit=not args.no_audit)
                except (Exception, SystemExit) as e:
                    print(f"feed: content refused ({e}) — will "
                          f"retry when it changes", flush=True)
                last = digest
        except OSError as e:
            print(f"feed: fetch failed ({e}) — retrying next pass",
                  flush=True)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("feed stopped.")
            return


def main():
    ap = argparse.ArgumentParser(
        description="anna edge — auto-process, cache, ask live")
    ap.add_argument("--store", default=None,
                    help="cache directory (default: edge_store/ "
                         "beside this file)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="process + cache a file or a "
                                   "whole database (every table)")
    p.add_argument("source")
    p.add_argument("--time", default=None)
    p.add_argument("--no-audit", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="reprocess even if the bytes are unchanged")

    p = sub.add_parser("watch", help="auto-process a drop folder")
    p.add_argument("--drop",
                   default=os.path.join(HERE_DIR, "dropbox"))
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--no-audit", action="store_true")

    p = sub.add_parser("feed", help="poll a link; reprocess the "
                                    "moment its content changes")
    p.add_argument("url")
    p.add_argument("--name", default=None,
                   help="dataset name (default: from the url)")
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--no-audit", action="store_true")

    sub.add_parser("list", help="what is cached")

    p = sub.add_parser("show", help="review a dataset's results")
    p.add_argument("name")

    p = sub.add_parser("ask",
                       help="live query: ask [name] question...")
    p.add_argument("query", nargs="+")

    p = sub.add_parser("report", help="open the full report.html")
    p.add_argument("name")
    p.add_argument("--path-only", action="store_true")

    args = ap.parse_args()
    store = store_dir(args)
    if args.cmd == "add":
        process_any(args.source, store, time_col=args.time,
                    audit=not args.no_audit, force=args.force)
    elif args.cmd == "watch":
        cmd_watch(args, store)
    elif args.cmd == "feed":
        cmd_feed(args, store)
    elif args.cmd == "list":
        cmd_list(args, store)
    elif args.cmd == "show":
        cmd_show(args, store)
    elif args.cmd == "ask":
        cmd_ask(args, store)
    elif args.cmd == "report":
        cmd_report(args, store)


if __name__ == "__main__":
    main()
