"""Load the case bank from cases/*.json."""

from __future__ import annotations

import json
from functools import lru_cache

from .config import CASES_DIR


@lru_cache(maxsize=1)
def load_cases() -> list[dict]:
    """Return every case in the bank, sorted by title."""
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            cases.append(json.load(f))
    return sorted(cases, key=lambda c: c.get("title", ""))


def get_case(case_id: str) -> dict:
    """Return one case by id, or raise if it is not found."""
    for case in load_cases():
        if case["id"] == case_id:
            return case
    raise KeyError(f"No case with id '{case_id}'.")


def case_facts_for_interviewer(case: dict) -> str:
    """Render the full case (including the hidden answer) for the interviewer's
    system prompt. The interviewer is instructed never to reveal the hidden parts;
    safety.py is the deterministic backstop."""
    parts = [
        f"CASE TITLE: {case['title']}",
        f"TYPE: {case.get('type', '')}",
        "",
        "PROMPT (read/paraphrase this to open the case):",
        case["prompt"],
        "",
        "BACKGROUND FACTS (share only if the candidate asks a relevant question):",
    ]
    parts += [f"- {b}" for b in case.get("background", [])]

    if case.get("clarifying_answers"):
        parts += ["", "ANSWERS TO LIKELY CLARIFYING QUESTIONS:"]
        parts += [f"- {q}: {a}" for q, a in case["clarifying_answers"].items()]

    if case.get("exhibits"):
        parts += ["", "EXHIBITS (release one ONLY when the candidate asks for relevant data):"]
        for ex in case["exhibits"]:
            parts.append(f"- [{ex['id']}] {ex['name']}: {ex['description']} | DATA: {ex['data']}")

    parts += ["", "HIDDEN — NEVER REVEAL THESE DIRECTLY:"]
    parts += ["GOOD FRAMEWORK (what strong structure looks like):"]
    parts += [f"- {x}" for x in case.get("good_framework", [])]
    parts += ["EXPECTED QUANTITATIVE ANSWERS:"]
    for q in case.get("quant", []):
        parts.append(f"- {q['question']} -> {q['expected']} (work: {q.get('work', '')})")
    parts += [f"MODEL RECOMMENDATION: {case.get('recommendation', '')}"]
    return "\n".join(parts)


def quant_key(case: dict) -> str:
    """Just the expected quantitative answers, for the math-checker agent."""
    if not case.get("quant"):
        return "No quantitative questions in this case."
    lines = []
    for q in case["quant"]:
        rng = q.get("range")
        rng_txt = f" acceptable range {rng}" if rng else ""
        lines.append(f"- {q['question']}: expected {q['expected']}{rng_txt}")
    return "\n".join(lines)
