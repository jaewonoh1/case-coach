#!/usr/bin/env python3
"""Fill the Impact section of report.html and slides.html from logged scores.

After running a few cases in the app, run from the repo root:

    python tools/update_impact.py                      # preview the numbers
    python tools/update_impact.py --apply              # write them into the files
    python tools/update_impact.py --apply --quote "…" --note "…"

It reads data/scores_log.jsonl (written by the app), computes your per-case
average structure / MECE / depth, the before (first case) vs. after (latest case)
figures, builds a dependency-free SVG trend chart, and fills the data-fill tokens
and the Figure 6 chart slot. Re-run after more cases to refresh.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from coach.cases import load_cases  # noqa: E402
from coach.scores import load_rows  # noqa: E402

REPORT = Path(os.getenv("CASE_COACH_REPORT", REPO / "report.html"))
SLIDES = Path(os.getenv("CASE_COACH_SLIDES", REPO / "slides.html"))


def _type_map() -> dict[str, str]:
    return {c["id"]: c.get("type", c["id"]) for c in load_cases()}


def aggregate(rows: list[dict]) -> list[dict]:
    """Collapse per-turn rows into per-case (run) averages, oldest first."""
    runs: dict[str, dict] = {}
    for r in rows:
        rid = r["run_id"]
        d = runs.setdefault(
            rid, {"case": r["case"], "ts": r["ts"], "structure": [], "mece": [], "depth": []}
        )
        d["structure"].append(r["structure"])
        d["mece"].append(r["mece"])
        d["depth"].append(r["depth"])
    seq = []
    for rid in sorted(runs, key=lambda k: runs[k]["ts"]):
        d = runs[rid]
        n = len(d["structure"])
        seq.append(
            {
                "case": d["case"],
                "ts": d["ts"],
                "structure": round(sum(d["structure"]) / n, 1),
                "mece": round(sum(d["mece"]) / n, 1),
                "depth": round(sum(d["depth"]) / n, 1),
            }
        )
    return seq


def svg_chart(seq: list[dict]) -> str:
    """A small, dependency-free line chart of scores across cases (y in 0..5)."""
    W, H, padL, padR, padT, padB = 560, 240, 40, 16, 20, 34
    plotW, plotH = W - padL - padR, H - padT - padB
    n = len(seq)

    def x(i: int) -> float:
        return padL + (plotW * (i / max(n - 1, 1)))

    def y(v: float) -> float:
        return padT + plotH * (1 - v / 5)

    colors = {"structure": "#00356B", "mece": "#286DC0", "depth": "#7FB0E6"}
    p = [
        f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" '
        'font-family="Helvetica Neue, Arial, sans-serif">'
    ]
    for gv in range(6):
        gy = y(gv)
        p.append(f'<line x1="{padL}" y1="{gy:.1f}" x2="{W-padR}" y2="{gy:.1f}" stroke="#e6edf4"/>')
        p.append(f'<text x="{padL-6}" y="{gy+3:.1f}" text-anchor="end" font-size="10" fill="#8a97a5">{gv}</text>')
    for i in range(n):
        p.append(f'<text x="{x(i):.1f}" y="{H-padB+16}" text-anchor="middle" font-size="10" fill="#5a6b7b">Case {i+1}</text>')
    for key, col in colors.items():
        pts = " ".join(f"{x(i):.1f},{y(s[key]):.1f}" for i, s in enumerate(seq))
        p.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.5" points="{pts}"/>')
        for i, s in enumerate(seq):
            p.append(f'<circle cx="{x(i):.1f}" cy="{y(s[key]):.1f}" r="3" fill="{col}"/>')
    lx = padL
    for key, col in colors.items():
        p.append(f'<rect x="{lx}" y="{padT-10}" width="10" height="10" fill="{col}"/>')
        p.append(f'<text x="{lx+14}" y="{padT-1}" font-size="10" fill="#5a6b7b">{key}</text>')
        lx += 95
    p.append("</svg>")
    return "".join(p)


def fill_tokens(html: str, values: dict) -> str:
    for k, v in values.items():
        html = re.sub(f'(data-fill="{k}"[^>]*>)[^<]*(</)', lambda m: m.group(1) + str(v) + m.group(2), html)
    return html


def fill_chart(html: str, svg: str) -> str:
    return re.sub(
        r'(<div id="trial-chart"[^>]*>).*?(</div>)',
        lambda m: '<div id="trial-chart">' + svg + "</div>",
        html,
        flags=re.DOTALL,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill the Impact section from logged scores.")
    ap.add_argument("--apply", action="store_true", help="write the changes into report.html + slides.html")
    ap.add_argument("--quote", default=None, help="your one-line reflection for the report + slides")
    ap.add_argument("--note", default=None, help="one sentence on what changed")
    ap.add_argument("--log", default=None, help="override the scores log path (for testing)")
    args = ap.parse_args()

    if args.log:
        rows = [json.loads(l) for l in Path(args.log).read_text().splitlines() if l.strip()]
        rows = sorted(rows, key=lambda r: r.get("ts", 0))
    else:
        rows = load_rows()

    if not rows:
        print("No scores logged yet. Run a few cases in the app first (writes data/scores_log.jsonl).")
        return

    seq = aggregate(rows)
    n = len(seq)
    types = _type_map()
    casetypes = ", ".join(dict.fromkeys(types.get(s["case"], s["case"]) for s in seq))
    days = max(1, round((seq[-1]["ts"] - seq[0]["ts"]) / 86400))
    first, last = seq[0], seq[-1]

    values = {
        "days": days,
        "ncases": n,
        "casetypes": casetypes,
        "struct_before": first["structure"],
        "struct_after": last["structure"],
        "mece_before": first["mece"],
        "mece_after": last["mece"],
    }
    if args.quote:
        values["quote"] = f'"{args.quote}"'
        values["quote_slide"] = f'"{args.quote}"'
    if args.note:
        values["note"] = args.note

    print("=== Trial stats ===")
    print(f"cases: {n}   span: ~{days} day(s)   types: {casetypes}")
    for i, s in enumerate(seq):
        print(f"  Case {i+1} ({types.get(s['case'], s['case'])}): structure {s['structure']}  mece {s['mece']}  depth {s['depth']}")
    print(f"before -> after:  structure {first['structure']} -> {last['structure']}   mece {first['mece']} -> {last['mece']}")

    if not args.apply:
        print("\n(preview only; re-run with --apply to write report.html + slides.html)")
        return

    svg = svg_chart(seq)
    for path in (REPORT, SLIDES):
        html = path.read_text()
        html = fill_tokens(html, values)
        if path == REPORT:
            html = fill_chart(html, svg)
        path.write_text(html)
        print(f"updated {path.name}")
    print("Done. Re-run after more cases to refresh.")


if __name__ == "__main__":
    main()
