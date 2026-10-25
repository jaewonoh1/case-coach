"""Adaptive weakness-targeting — the project's novelty twist.

Case Coach doesn't just run cases; it reads your logged scores across every past
session, finds the dimension you are weakest at (structure, MECE-ness, or depth),
and focuses the next case on it: the interviewer presses harder there and the
coach prioritizes tips for it. Because scores persist (coach/scores.py), this is a
real cross-session learning loop, not a single-session gimmick.
"""

from __future__ import annotations

from .scores import load_rows

DIMENSIONS = ["structure", "mece", "depth"]
LABELS = {"structure": "Structure", "mece": "MECE-ness", "depth": "Depth / insight"}

_FOCUS_INSTRUCTION = {
    "structure": (
        "FOCUS THIS SESSION — STRUCTURE: push the candidate to lay out a clear, "
        "labeled, top-down structure before analyzing. Call out unstructured jumps "
        "and ask them to organize their thinking into explicit buckets first."
    ),
    "mece": (
        "FOCUS THIS SESSION — MECE: probe hard for overlaps and gaps in the "
        "candidate's buckets. Ask 'what's missing?' and 'do those overlap?' to train "
        "mutually-exclusive, collectively-exhaustive thinking."
    ),
    "depth": (
        "FOCUS THIS SESSION — DEPTH: push for hypotheses and 'so what?' reasoning. "
        "Don't accept surface-level observations; make the candidate draw an "
        "implication from each point."
    ),
}


def dimension_averages(extra_rows: list[dict] | None = None) -> dict[str, float]:
    """Average score per dimension across all logged turns (+ any in-session rows)."""
    rows = load_rows() + list(extra_rows or [])
    out: dict[str, float] = {}
    for d in DIMENSIONS:
        vals = [r[d] for r in rows if r.get(d)]
        if vals:
            out[d] = round(sum(vals) / len(vals), 1)
    return out


def weakest_dimension(extra_rows: list[dict] | None = None) -> dict | None:
    """Return the weakest dimension and the supporting averages, or None if no data."""
    avgs = dimension_averages(extra_rows)
    if not avgs:
        return None
    dim = min(avgs, key=avgs.get)
    return {"dim": dim, "label": LABELS[dim], "avg": avgs[dim], "averages": avgs}


def focus_instruction(dim: str | None) -> str:
    """The extra agent instruction for a focused session (empty if no focus)."""
    return _FOCUS_INSTRUCTION.get(dim or "", "")
