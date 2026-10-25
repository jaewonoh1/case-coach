"""The orchestrator: coordinates the four agents through one case session.

It owns the conversation state, advances the case through its phases, runs the
safety checks before any model call, and after each candidate turn fans out to
the grader, math checker, and coach.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import agents, safety, scores
from .tokens import reset as reset_tokens

PHASES = ["framework", "analysis", "recommendation", "done"]

_RECOMMENDATION_CUES = re.compile(
    r"\b(recommend|in summary|to summari|my recommendation|overall,|in conclusion)\b",
    re.IGNORECASE,
)


@dataclass
class TurnResult:
    """Everything the UI needs to render after one candidate turn."""

    interviewer: str = ""
    grader: dict = field(default_factory=dict)
    math: dict = field(default_factory=dict)
    coach: str = ""
    phase: str = "framework"
    refused: bool = False
    halted: bool = False
    note: str = ""


@dataclass
class CaseSession:
    """One run of one case with one candidate."""

    case: dict
    phase: str = "framework"
    turn_count: int = 0
    conversation: list[dict] = field(default_factory=list)
    scores: list[dict] = field(default_factory=list)
    run_id: str = ""
    focus: str | None = None  # weakest dimension to target this session (adapt.py)

    def start(self) -> str:
        """Begin the case; returns the interviewer's opening line."""
        reset_tokens()
        self.run_id = f"{int(time.time())}-{self.case['id']}"
        opening = agents.opening_line(self.case, focus=self.focus)
        self.conversation.append({"role": "assistant", "content": opening})
        return opening

    def submit(self, user_msg: str) -> TurnResult:
        """Process one candidate message and return the full turn result."""
        self.turn_count += 1

        # --- Safety checks run BEFORE any model call ---
        if safety.budget_exceeded():
            return TurnResult(
                phase=self.phase,
                halted=True,
                note="Token budget for this session reached — ending to avoid overspend.",
            )
        if safety.turn_cap_reached(self.turn_count):
            return TurnResult(
                phase=self.phase,
                halted=True,
                note="Turn limit reached — wrap up with your recommendation.",
            )
        if safety.answer_leak_attempt(user_msg):
            # Deterministic defense: refuse without ever calling the model, so the
            # answer cannot leak even if the model would have complied.
            self.conversation.append({"role": "user", "content": user_msg})
            self.conversation.append(
                {"role": "assistant", "content": safety.REFUSAL_MESSAGE}
            )
            return TurnResult(
                interviewer=safety.REFUSAL_MESSAGE,
                phase=self.phase,
                refused=True,
                note="Blocked a prompt-injection / answer-leak attempt.",
            )

        # --- Normal turn: interviewer replies, then the graders evaluate ---
        self.conversation.append({"role": "user", "content": user_msg})
        interviewer = agents.interviewer_reply(self.case, self.phase, self.conversation, focus=self.focus)
        self.conversation.append({"role": "assistant", "content": interviewer})

        grader = agents.grade_structure(self.case, user_msg)
        math = agents.check_math(self.case, user_msg)
        coach = agents.coach_tip(self.case, user_msg, grader, math, focus=self.focus)

        self.scores.append(
            {
                "turn": self.turn_count,
                "structure": grader.get("structure_score", 0),
                "mece": grader.get("mece_score", 0),
                "depth": grader.get("depth_score", 0),
            }
        )
        # Persist to data/scores_log.jsonl so a trial's before/after survives.
        scores.record_scores(self.run_id, self.case["id"], self.turn_count, grader)
        self._advance_phase(user_msg, grader)

        return TurnResult(
            interviewer=interviewer,
            grader=grader,
            math=math,
            coach=coach,
            phase=self.phase,
        )

    def _advance_phase(self, user_msg: str, grader: dict) -> None:
        """Light heuristic to move the case forward."""
        if self.phase == "framework" and grader.get("structure_score", 0) >= 3:
            self.phase = "analysis"
        elif self.phase in ("framework", "analysis") and _RECOMMENDATION_CUES.search(user_msg):
            self.phase = "recommendation"
        elif self.phase == "recommendation":
            self.phase = "done"

    def average_scores(self) -> dict:
        """Mean of each score across turns that had analysis (score > 0)."""
        rows = [s for s in self.scores if s["structure"] > 0]
        if not rows:
            return {"structure": 0, "mece": 0, "depth": 0}
        n = len(rows)
        return {
            "structure": round(sum(r["structure"] for r in rows) / n, 1),
            "mece": round(sum(r["mece"] for r in rows) / n, 1),
            "depth": round(sum(r["depth"] for r in rows) / n, 1),
        }
