"""Central configuration for Case Coach.

One place for: where the project lives, which model to use, and how to reach it
through the Portkey gateway. Every agent talks to the AI through this config, so
the model and gateway are defined exactly once.

Per the course rules, the app looks for a `.env` in the repo folder first, then
in the folder one level above it. First definition of a variable wins.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent      # case-coach/coach/
REPO_DIR = PACKAGE_DIR.parent                      # case-coach/
PARENT_DIR = REPO_DIR.parent                       # one level above the repo

PROMPTS_DIR = REPO_DIR / "prompts"
CASES_DIR = REPO_DIR / "cases"
DATA_DIR = REPO_DIR / "data"

# Course rule: repo .env first, then one level up. load_dotenv does not override
# variables that are already set, so the repo copy takes precedence.
load_dotenv(REPO_DIR / ".env")
load_dotenv(PARENT_DIR / ".env")

# The course key only permits gpt-6-luna; keep it overridable for local testing
# but default to the allowed model.
MODEL = os.getenv("CASE_COACH_MODEL", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# gpt-6-luna is a reasoning model; the course's homework agents run it with
# reasoning effort "none" so it behaves like a fast chat model. Set to "" to omit.
REASONING_EFFORT = os.getenv("CASE_COACH_REASONING_EFFORT", "none")

# Safety limits (see coach/safety.py).
MAX_TURNS = int(os.getenv("CASE_COACH_MAX_TURNS", "40"))
TOKEN_BUDGET = int(os.getenv("CASE_COACH_TOKEN_BUDGET", "300000"))

# Pricing for the tokenomics report, in USD per 1M tokens. Defaults are the
# course gpt-6-luna rates (MGT 409 lecture 11 tokenomics module; OpenAI standard
# short-context rates). Override in .env if the rates change.
PRICE_INPUT_PER_M = float(os.getenv("PRICE_INPUT_PER_M", "0.10"))
PRICE_CACHED_PER_M = float(os.getenv("PRICE_CACHED_PER_M", "0.01"))
PRICE_OUTPUT_PER_M = float(os.getenv("PRICE_OUTPUT_PER_M", "0.50"))


def get_api_key() -> str:
    """Return the Portkey API key, or raise a clear error if it is missing."""
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY not found. Add it to a .env file in the case-coach "
            "folder or one level above it (see .env.example)."
        )
    return key
