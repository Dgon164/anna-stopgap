"""ANNA UI — the human road. Double-click, drop a file, read, ask.

No command line, no flags, no column names: this serves a small page
on YOUR machine only (127.0.0.1 — nothing leaves the computer). Drop
a spreadsheet export on it; the full pipeline runs by itself; the
page shows the five-second numbers, the headlines, every section,
and a question box that answers LIVE from the cached receipts —
verbatim lines only, and an honest "nothing matches" when nothing
does. The full client report is one click away.

    python anna_ui.py            # opens http://127.0.0.1:8765 in the browser
    python anna_ui.py --port 9000 --no-browser

Windows: double-click START_ANNA.bat instead.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE_DIR)

import anna_edge                       # noqa: E402
import honest_report as hr             # noqa: E402

STORE = os.path.join(HERE_DIR, "edge_store")
UPLOADS = os.path.join(STORE, "uploads")

# one entry per in-flight or finished upload, keyed by saved path
JOBS = {}
JOBS_LOCK = threading.Lock()

OK_EXTS = (anna_edge.DATA_EXTS | anna_edge.DB_EXTS
           | anna_edge.SQL_EXTS)

# the report's own palette — one accent, text wears text tokens
CSS = """
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
 max-width:880px;margin:2.2em auto;padding:0 1.2em;color:#0b0b0b;
 background:#fcfcfb;line-height:1.55}
h1{font-size:1.7rem;margin-bottom:.1em;letter-spacing:-.02em}
h2{font-size:1.1rem;margin-top:1.8em;border-left:4px solid #2a78d6;
 padding-left:.6em}
a{color:#2a78d6}
.sub{color:#52514e;margin-top:0}
.muted{color:#898781;font-size:.85rem}
.drop{border:2px dashed #b7d3f6;border-radius:12px;padding:2.2em;
 text-align:center;background:#fff;margin:1.2em 0}
.drop.on{background:#f2f6fc;border-color:#2a78d6}
.btn{display:inline-block;background:#2a78d6;color:#fff;border:0;
 border-radius:8px;padding:.55em 1.2em;font-size:1rem;cursor:pointer;
 text-decoration:none}
.btn2{display:inline-block;background:#fff;color:#0b0b0b;
 border:1px solid #d5d3ce;border-radius:8px;padding:.5em 1.1em;
 cursor:pointer;text-decoration:none;font-size:.9rem}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:1.2em 0}
.kpi{flex:1 1 150px;background:#fff;border:1px solid #e6e4df;
 border-radius:10px;padding:12px 16px}
.kl{font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;
 color:#898781}
.kv{font-size:1.45rem;font-weight:600;margin:.1em 0;color:#0b0b0b}
.ks{font-size:.75rem;color:#52514e}
ul{padding-left:1.3em}li{margin:.45em 0}
.card{background:#fff;border:1px solid #e6e4df;border-radius:10px;
 padding:.9em 1.2em;margin:.7em 0}
.card .when{color:#898781;font-size:.8rem}
details{background:#fff;border:1px solid #e6e4df;border-radius:10px;
 padding:.6em 1em;margin:.5em 0}
summary{cursor:pointer;font-weight:600}
input[type=text]{width:100%;box-sizing:border-box;font-size:1rem;
 padding:.55em .8em;border:1px solid #d5d3ce;border-radius:8px}
.note{border-left:3px solid #2a78d6;background:#f2f6fc;
 padding:.6em 1em;border-radius:0 8px 8px 0;color:#52514e}
.warn{border-left:3px solid #d03b3b;background:#fdf1f1;
 padding:.6em 1em;border-radius:0 8px 8px 0}
form.inline{display:inline}
"""


def page(title, body_html):
    return (f"<!doctype html><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, "
            f"initial-scale=1'><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style>{body_html}").encode("utf-8")


def esc(s):
    return html.escape(str(s))


def md_line(ln):
    """One markdown-ish receipt line as safe HTML: bold honored,
    chart references pointed at the full report, nothing invented."""
    if ln.strip().startswith("!["):
        return "<span class='muted'>(chart — see the full report)</span>"
    t = esc(ln)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t


def safe_name(name):
    return bool(re.fullmatch(r"[-\w. ()]+", name))


# ---------------------------------------------------------------- upload
def parse_upload(headers, body):
    """Pull (filename, bytes) out of a multipart POST — stdlib only."""
    m = re.search(r'boundary="?([^";]+)"?',
                  headers.get("Content-Type", ""))
    if not m:
        return None, None
    for part in body.split(b"--" + m.group(1).encode()):
        if b"\r\n\r\n" not in part:
            continue
        head, _, data = part.partition(b"\r\n\r\n")
        fm = re.search(r'filename="([^"]*)"',
                       head.decode("utf-8", "replace"))
        if fm and fm.group(1):
            # the part ends with exactly ONE \r\n before the
            # boundary — stripping more corrupts binary uploads
            # (an SQLite file ending in 0x0a lost its last byte)
            if data.endswith(b"\r\n"):
                data = data[:-2]
            return (os.path.basename(fm.group(1).replace("\\", "/")),
                    data)
    return None, None


def start_job(saved_path):
    with JOBS_LOCK:
        JOBS[saved_path] = dict(done=False, error=None, names=None)

    def run():
        try:
            names = anna_edge.process_any(saved_path, STORE,
                                          audit=True, quiet=True)
            with JOBS_LOCK:
                JOBS[saved_path].update(done=True, names=names)
        except (Exception, SystemExit) as e:
            with JOBS_LOCK:
                JOBS[saved_path].update(done=True, error=str(e) or
                                        type(e).__name__)
    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- views
def view_home():
    idx = anna_edge.load_index(STORE)
    engine = hr.engine_available()
    tier = ("engine connected — reports carry both tiers "
            "(certified rules + what's-there descriptions)"
            if engine else
            "standalone build — what's-there tier only, and every "
            "report says so plainly")
    cards = ""
    for name, e in sorted(idx.items(),
                          key=lambda kv: kv[1]["processed_at"],
                          reverse=True):
        cards += (f"<div class='card'><b><a href='/d/{esc(name)}'>"
                  f"{esc(name)}</a></b> — {e['rows']:,} rows × "
                  f"{e['cols']} columns"
                  f"<div class='when'>processed {esc(e['processed_at'])}"
                  f"</div></div>")
    if not cards:
        cards = ("<p class='muted'>Nothing here yet — drop your "
                 "first file above.</p>")
    body = f"""
<h1>Anna</h1>
<p class='sub'>Drop a spreadsheet export. She reads it, checks
everything, and reports back — every number traces to a receipt,
and where the data can't support a claim she says so instead of
guessing.</p>
<div class='note'>{esc(tier)}</div>
<form id='f' class='drop' method='post' action='/upload'
 enctype='multipart/form-data'>
  <p><b>Drop your file here</b> — CSV, TSV, text, or a whole
  database (SQLite .db / .sql dump: EVERY table gets processed,
  not just what a query returns). From Excel: File &gt; Save As
  &gt; CSV.</p>
  <input type='file' name='file'
   accept='.csv,.tsv,.txt,.db,.sqlite,.sqlite3,.sql' required>
  <p><button class='btn' type='submit'>Analyze it</button></p>
  <p class='muted'>Runs on this computer only — nothing is uploaded
  anywhere. Small files take under a minute; already-seen files are
  instant.</p>
</form>
<h2>Ask across everything</h2>
<form method='get' action='/ask'>
<input type='text' name='q' placeholder='e.g. biggest customers ·
 returns by region — searches every dataset below'>
</form>
<h2>Your datasets</h2>
{cards}
<p class='muted'><a href='/doc/OWNER_CHECK.md'>How to check a report
in 5 minutes</a> · <a href='/doc/TESTER_GUIDE.md'>Tester guide</a></p>
<script>
const d=document.getElementById('f'),i=d.querySelector('input[type=file]');
['dragover','dragenter'].forEach(ev=>d.addEventListener(ev,e=>{{
 e.preventDefault();d.classList.add('on');}}));
['dragleave','drop'].forEach(ev=>d.addEventListener(ev,e=>{{
 e.preventDefault();d.classList.remove('on');}}));
d.addEventListener('drop',e=>{{i.files=e.dataTransfer.files;
 d.submit();}});
</script>"""
    return page("Anna", body)


def view_status(saved_path):
    with JOBS_LOCK:
        job = JOBS.get(saved_path)
    fn = esc(os.path.basename(saved_path))
    if job is None:
        return page("Anna", "<h1>Unknown job</h1><p><a href='/'>"
                            "back</a></p>")
    if job["done"] and job["error"]:
        return page("Anna", f"""
<h1>That file was refused</h1>
<div class='warn'>{esc(job['error'])}</div>
<p>That's the honest answer, not a crash — fix the file and drop it
again.</p><p><a class='btn' href='/'>Back</a></p>""")
    if job["done"]:
        names = job["names"] or []
        if len(names) == 1:
            q = urllib.parse.quote(names[0])
            return (f"<meta http-equiv='refresh' "
                    f"content='0;url=/d/{q}'>").encode(), True
        links = "".join(
            f"<div class='card'><b><a href='/d/{esc(n)}'>{esc(n)}"
            f"</a></b></div>" for n in names)
        return page("Anna", f"""
<h1>Database processed — {len(names)} tables</h1>
<p class='sub'>Every table in {fn} was processed whole, not just
what a query would return. Each one below is reviewed and asked
about on its own; the question box on the home page searches them
all at once.</p>{links}
<p><a class='btn' href='/'>Home</a></p>""")
    return page("Anna", f"""
<meta http-equiv='refresh' content='2'>
<h1>Reading {fn}…</h1>
<p class='sub'>Intake, checks, every organ, charts, the full report —
this page moves on by itself when she's done. A whole database is
processed table by table; big ones can take a few minutes.</p>""")


def view_dataset(name, question=None):
    state = anna_edge.load_state(STORE, name)
    if not state:
        return page("Anna", "<h1>No such dataset</h1>"
                            "<p><a href='/'>back</a></p>")
    kpis = "".join(
        f"<div class='kpi'><div class='kl'>{esc(k['label'])}</div>"
        f"<div class='kv'>{esc(k['value'])}</div>"
        f"<div class='ks'>{esc(k.get('sub') or '')}</div></div>"
        for k in state["kpis"])
    heads = "".join(f"<li>{md_line(h[2:])}</li>"
                    for h in state["headlines"])
    ans = ""
    if question is not None:
        hits = anna_edge.ask_one(state, question)
        if hits:
            blocks = ""
            for _, title, lines in hits:
                inner = "<br>".join(md_line(ln) for ln in lines
                                    if ln.strip())
                blocks += (f"<details open><summary>"
                           f"{esc(title.lstrip('# '))}</summary>"
                           f"<p>{inner}</p></details>")
            ans = (f"<h2>Answer — verbatim from the receipts</h2>"
                   f"{blocks}")
        else:
            titles = ", ".join(esc(s["title"])
                               for s in state["sections"])
            ans = (f"<h2>Answer</h2><div class='warn'>Nothing in the "
                   f"processed results matches "
                   f"<b>{esc(question)}</b> — that is the honest "
                   f"answer, not a guess. What IS here: {titles}."
                   f"</div>")
    secs = "".join(
        f"<details><summary>{esc(s['title'])}</summary><p>"
        + "<br>".join(md_line(ln) for ln in s["lines"] if ln.strip())
        + "</p></details>"
        for s in state["sections"])
    tier = ("<div class='note'>standalone build — nothing here is "
            "certified, and the full report says so plainly.</div>"
            if state.get("standalone") else "")
    qv = esc(question or "")
    body = f"""
<p><a href='/'>&larr; all datasets</a></p>
<h1>{esc(name)}</h1>
<p class='sub'>{state['rows']:,} rows × {len(state['header'])}
columns · processed {esc(state['processed_at'])}</p>
{tier}
<p><a class='btn' href='/d/{esc(name)}/report' target='_blank'>Open
the full client report</a>
<form class='inline' method='post' action='/d/{esc(name)}/delete'
 onsubmit='return confirm("Remove {esc(name)} and its cached "
 +"results from this computer?")'>
<button class='btn2' type='submit'>Remove</button></form></p>
<div class='kpis'>{kpis}</div>
<h2>Ask about this data</h2>
<form method='get' action='/d/{esc(name)}'>
<input type='text' name='q' value="{qv}" placeholder='e.g. returns
 by region · biggest customers · where does the book not balance'>
</form>
<p class='muted'>Answers are verbatim lines from the processed
receipts — nothing is generated, and no match means she says so.</p>
{ans}
<h2>The headlines</h2><ul>{heads}</ul>
<h2>Everything she found (tap a section)</h2>{secs}
"""
    return page(f"Anna — {name}", body)


def view_ask_all(question):
    idx = anna_edge.load_index(STORE)
    blocks, misses = "", []
    for name in sorted(idx):
        state = anna_edge.load_state(STORE, name)
        if not state:
            continue
        hits = anna_edge.ask_one(state, question or "")
        if not hits:
            misses.append(name)
            continue
        inner = ""
        for _, title, lines in hits[:2]:
            body = "<br>".join(md_line(ln) for ln in lines
                               if ln.strip())
            inner += (f"<details open><summary>"
                      f"{esc(title.lstrip('# '))}</summary>"
                      f"<p>{body}</p></details>")
        blocks += (f"<h2><a href='/d/{esc(name)}'>{esc(name)}</a>"
                   f"</h2>{inner}")
    if not blocks:
        blocks = ("<div class='warn'>Nothing in any processed "
                  "dataset matches that — the honest answer, not a "
                  "guess.</div>")
    elif misses:
        blocks += (f"<p class='muted'>No match in: "
                   f"{esc(', '.join(misses))}</p>")
    qv = esc(question or "")
    return page("Anna — ask", f"""
<p><a href='/'>&larr; home</a></p>
<h1>Ask across everything</h1>
<form method='get' action='/ask'>
<input type='text' name='q' value="{qv}"></form>
<p class='muted'>Answers are verbatim lines from the processed
receipts of every cached dataset.</p>
{blocks}""")


def view_doc(fn):
    path = os.path.join(HERE_DIR, "docs", fn)
    if not safe_name(fn) or not os.path.exists(path):
        return page("Anna", "<h1>No such page</h1>")
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ln.startswith("# "):
            out.append(f"<h1>{esc(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{esc(ln[3:])}</h2>")
        elif ln.startswith("- "):
            out.append(f"<li>{md_line(ln[2:])}</li>")
        elif ln.strip():
            out.append(f"<p>{md_line(ln)}</p>")
    return page(fn, "<p><a href='/'>&larr; back</a></p>"
                + "\n".join(out))


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, data, code=200, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, url):
        self.send_response(303)
        self.send_header("Location", url)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(p)
                 for p in parsed.path.split("/") if p]
        qs = urllib.parse.parse_qs(parsed.query)
        if not parts:
            return self._send(view_home())
        if parts[0] == "status" and len(parts) == 2:
            out = view_status(urllib.parse.unquote(parts[1]))
            if isinstance(out, tuple):
                return self._send(out[0])
            return self._send(out)
        if parts[0] == "doc" and len(parts) == 2:
            return self._send(view_doc(parts[1]))
        if parts[0] == "ask":
            return self._send(view_ask_all(qs.get("q", [""])[0]))
        if parts[0] == "d" and len(parts) >= 2 \
                and safe_name(parts[1]):
            name = parts[1]
            if len(parts) == 3 and parts[2] == "report":
                p = os.path.join(STORE, name, "report.html")
                if os.path.exists(p):
                    return self._send(open(p, "rb").read())
                return self._send(page("Anna", "<h1>No report</h1>"))
            q = qs.get("q", [None])[0]
            return self._send(view_dataset(name, q))
        self._send(page("Anna", "<h1>Not found</h1>"
                                "<p><a href='/'>back</a></p>"), 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        parts = [urllib.parse.unquote(p)
                 for p in self.path.split("/") if p]
        if parts and parts[0] == "upload":
            fn, data = parse_upload(self.headers, body)
            if not fn or data is None:
                return self._send(page("Anna",
                                       "<h1>No file received</h1>"
                                       "<p><a href='/'>back</a></p>"))
            stem, ext = os.path.splitext(fn)
            stem = re.sub(r"[^-\w. ()]", "_", stem) or "data"
            if ext.lower() not in OK_EXTS:
                msg = ("That looks like an Excel workbook — save it "
                       "as CSV first (File &gt; Save As &gt; 'CSV "
                       "(Comma delimited)') and drop it again."
                       if ext.lower() in (".xls", ".xlsx")
                       else f"'{esc(ext)}' files aren't supported — "
                            f"CSV, TSV, or delimited text only.")
                return self._send(page("Anna",
                                       f"<h1>Refused, honestly</h1>"
                                       f"<div class='warn'>{msg}"
                                       f"</div><p><a class='btn' "
                                       f"href='/'>Back</a></p>"))
            os.makedirs(UPLOADS, exist_ok=True)
            saved = os.path.join(UPLOADS, stem + ext.lower())
            with open(saved, "wb") as f:
                f.write(data)
            start_job(saved)
            return self._redirect("/status/"
                                  + urllib.parse.quote(saved))
        if len(parts) == 3 and parts[0] == "d" \
                and parts[2] == "delete" and safe_name(parts[1]):
            name = parts[1]
            shutil.rmtree(os.path.join(STORE, name),
                          ignore_errors=True)
            idx = anna_edge.load_index(STORE)
            if name in idx:
                del idx[name]
                anna_edge.save_index(STORE, idx)
            return self._redirect("/")
        self._send(page("Anna", "<h1>Not found</h1>"), 404)


def main():
    ap = argparse.ArgumentParser(description="anna's local page")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    os.makedirs(STORE, exist_ok=True)
    srv = None
    for port in range(args.port, args.port + 10):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        raise SystemExit("no free port found — close another anna "
                         "window or pass --port")
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"anna is at {url}  (this computer only — Ctrl+C to stop)",
          flush=True)
    if not args.no_browser:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("stopped.")


if __name__ == "__main__":
    main()
