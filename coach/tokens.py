"""Token accounting for the tokenomics section of the report.

Every model call routes its `usage` object here. We keep a running per-session
total (shown live in the app) and append one line per call to data/token_log.jsonl
so you have real, logged token counts — the evidence the rubric asks for.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import (
    DATA_DIR,
    PRICE_CACHED_PER_M,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
)

LOG_PATH = DATA_DIR / "token_log.jsonl"

# Running totals for the current app session.
_totals = {"input": 0, "cached": 0, "output": 0, "calls": 0}


def record_usage(label: str, usage) -> None:
    """Add one call's usage to the running totals and append it to the log."""
    if usage is None:
        return
    inp = getattr(usage, "prompt_tokens", 0) or 0
    out = getattr(usage, "completion_tokens", 0) or 0
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0

    _totals["input"] += inp
    _totals["cached"] += cached
    _totals["output"] += out
    _totals["calls"] += 1

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": round(time.time(), 3),
                    "label": label,
                    "input": inp,
                    "cached": cached,
                    "output": out,
                }
            )
            + "\n"
        )


def session_totals() -> dict:
    """Return a copy of the running totals for display."""
    return dict(_totals)


def cost_usd(totals: dict | None = None) -> float:
    """Estimate USD cost from token totals using the configured prices.

    Cached input is billed at the cached rate; the rest of the input at the
    normal rate. Returns 0.0 until you set real prices in .env / config.py.
    """
    t = totals or _totals
    uncached_input = max(t["input"] - t["cached"], 0)
    return (
        uncached_input / 1_000_000 * PRICE_INPUT_PER_M
        + t["cached"] / 1_000_000 * PRICE_CACHED_PER_M
        + t["output"] / 1_000_000 * PRICE_OUTPUT_PER_M
    )


def reset() -> None:
    """Clear the running totals (new case session)."""
    for k in _totals:
        _totals[k] = 0
