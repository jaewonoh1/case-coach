"""The four agents that make up Case Coach.

- interviewer: runs the case in character, releases exhibits, never leaks the answer.
- structure_grader: scores the candidate's framework for MECE-ness and depth.
- math_checker: verifies the candidate's numbers against the expected answers.
- coach: turns the graders' output into one targeted improvement.

The orchestrator (orchestrator.py) wires these together each turn.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .cases import case_facts_for_interviewer, quant_key
from .config import PROMPTS_DIR
from .llm import chat, chat_json


@lru_cache(maxsize=8)
def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def interviewer_reply(case: dict, phase: str, conversation: list[dict]) -> str:
    """Return the interviewer's in-character reply.

    `conversation` is the running list of {role, content} turns, ending with the
    candidate's latest message.
    """
    messages = [
        {"role": "system", "content": _prompt("interviewer")},
        {
            "role": "system",
            "content": (
                f"CURRENT PHASE: {phase}\n\n"
                f"CASE DETAILS (for your eyes only):\n{case_facts_for_interviewer(case)}"
            ),
        },
        *conversation,
    ]
    return chat(messages, label="interviewer", temperature=0.5)


def opening_line(case: dict) -> str:
    """Interviewer's opening — delivered when a case starts."""
    messages = [
        {"role": "system", "content": _prompt("interviewer")},
        {
            "role": "system",
            "content": (
                "CURRENT PHASE: framework\n\n"
                f"CASE DETAILS (for your eyes only):\n{case_facts_for_interviewer(case)}"
            ),
        },
        {
            "role": "user",
            "content": "[The candidate just sat down. Open the case now.]",
        },
    ]
    return chat(messages, label="interviewer_open", temperature=0.5)


def grade_structure(case: dict, user_msg: str) -> dict:
    """Score the candidate's latest message on structure / MECE / depth."""
    messages = [
        {"role": "system", "content": _prompt("structure_grader")},
        {
            "role": "user",
            "content": (
                f"CASE: {case['title']} ({case.get('type', '')})\n\n"
                f"WHAT STRONG STRUCTURE LOOKS LIKE:\n"
                + "\n".join(f"- {x}" for x in case.get("good_framework", []))
                + f"\n\nCANDIDATE'S LATEST MESSAGE:\n{user_msg}"
            ),
        },
    ]
    return chat_json(
        messages,
        label="structure_grader",
        default={"structure_score": 0, "mece_score": 0, "depth_score": 0, "one_line": ""},
    )


_NUMBER_RE = re.compile(r"\d")


def check_math(case: dict, user_msg: str) -> dict:
    """Verify the candidate's numbers. Skips the call when there are no digits."""
    if not _NUMBER_RE.search(user_msg):
        return {"checks": [], "overall": ""}
    messages = [
        {"role": "system", "content": _prompt("math_checker")},
        {
            "role": "user",
            "content": (
                f"EXPECTED QUANTITATIVE ANSWERS:\n{quant_key(case)}\n\n"
                f"CANDIDATE'S LATEST MESSAGE:\n{user_msg}"
            ),
        },
    ]
    return chat_json(messages, label="math_checker", default={"checks": [], "overall": ""})


def coach_tip(case: dict, user_msg: str, grader: dict, math: dict) -> str:
    """One targeted improvement, synthesizing the graders' output."""
    messages = [
        {"role": "system", "content": _prompt("coach")},
        {
            "role": "user",
            "content": (
                f"CASE: {case['title']} ({case.get('type', '')})\n\n"
                f"STRUCTURE GRADER: {grader}\n\n"
                f"MATH CHECKER: {math}\n\n"
                f"CANDIDATE'S LATEST MESSAGE:\n{user_msg}"
            ),
        },
    ]
    return chat(messages, label="coach", temperature=0.4)
