"""The scale test: generate → process → independently validate.

    python testing/run_scale_test.py                 # 10k, 100k, 1M rows
    python testing/run_scale_test.py --sizes 10000,50000

For each size: build a seeded dataset with known answers, run the
full pipeline (no audit face — time that separately if needed), then
run the independent validator against the results. Prints wall-clock
seconds and PASS/FAIL per size. Exit 0 = every check at every size
passed.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import anna_edge                    # noqa: E402
import honest_report as hr          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="10000,100000,1000000")
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]

    work = tempfile.mkdtemp(prefix="anna_scale_")
    print(f"engine connected: {hr.engine_available()}   "
          f"work dir: {work}\n")
    summary, any_fail = [], False
    for n in sizes:
        src = os.path.join(work, f"scale_{n}.csv")
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "make_scale_data.py"),
             "--rows", str(n), "--seed", str(args.seed),
             "--out", src],
            capture_output=True, text=True)
        print(r.stdout.strip())
        store = os.path.join(work, f"store_{n}")
        t0 = time.perf_counter()
        names = anna_edge.process_any(src, store, audit=False)
        t_proc = time.perf_counter() - t0
        t0 = time.perf_counter()
        anna_edge.process_any(src, store, audit=False, quiet=True)
        t_cache = time.perf_counter() - t0
        print(f"{n:,} rows: processed in {t_proc:.1f}s "
              f"(cache re-hit {t_cache:.2f}s)")
        v = subprocess.run(
            [sys.executable, os.path.join(HERE, "validate_outputs.py"),
             "--store", store, "--name", names[0],
             "--truths", src + ".truths.json"],
            capture_output=True, text=True)
        print(v.stdout.strip() + "\n")
        ok = v.returncode == 0
        any_fail |= not ok
        summary.append((n, t_proc, t_cache, ok))

    print("=" * 56)
    print(f"{'rows':>12}  {'process':>9}  {'cache hit':>9}  result")
    for n, tp, tc, ok in summary:
        print(f"{n:>12,}  {tp:>8.1f}s  {tc:>8.2f}s  "
              f"{'ALL PASS' if ok else 'FAILURES — see above'}")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
