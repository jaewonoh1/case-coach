"""Persist per-turn grading scores so a trial's before/after survives sessions.

The app grades every substantive answer (structure / MECE / depth). Those scores
only live in memory during a run, which makes it hard to show improvement across
sessions. This module appends each graded turn to data/scores_log.jsonl, tagged
with a per-run id, so tools/update_impact.py can compute a real before/after and
chart it for the report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import DATA_DIR

LOG_PATH = DATA_DIR / "scores_log.jsonl"


def record_scores(run_id: str, case_id: str, turn: int, grader: dict) -> None:
    """Append one graded turn. Skips turns with no analysis (structure == 0)."""
    structure = grader.get("structure_score", 0) or 0
    if structure <= 0:
        return
    row = {
        "ts": round(time.time(), 3),
        "run_id": run_id,
        "case": case_id,
        "turn": turn,
        "structure": structure,
        "mece": grader.get("mece_score", 0) or 0,
        "depth": grader.get("depth_score", 0) or 0,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def load_rows() -> list[dict]:
    """Return all logged score rows (oldest first), or [] if none yet."""
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return sorted(rows, key=lambda r: r.get("ts", 0))
