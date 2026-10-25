"""Thin wrapper around the OpenAI SDK, pointed at the Portkey gateway.

Every agent calls `chat()`; this is the single place that talks to the model, so
token logging and the gpt-6-luna settings live in exactly one spot.
"""

from __future__ import annotations

import json

from openai import APIError, OpenAI

from .config import MODEL, PORTKEY_BASE_URL, REASONING_EFFORT, get_api_key
from .tokens import record_usage

_client: OpenAI | None = None

# Returned when a model call is blocked (e.g. the gateway content filter) or errors
# out, so a single bad turn never crashes the app. chat_json() turns this into its
# default via a failed JSON parse.
FALLBACK = (
    "I can't take that one — let's keep going with your own reasoning. "
    "What's your next step?"
)


def client() -> OpenAI:
    """Return a cached OpenAI client configured for the Portkey gateway."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_api_key(), base_url=PORTKEY_BASE_URL)
    return _client


def chat(
    messages: list[dict],
    *,
    label: str = "",
    temperature: float = 0.4,
    json_mode: bool = False,
) -> str:
    """Send a chat request and return the assistant's text.

    `label` tags the call in the token log (e.g. "interviewer", "grader").
    `json_mode` asks the model to return a single JSON object.
    """
    kwargs: dict = {"model": MODEL, "messages": messages, "temperature": temperature}
    if REASONING_EFFORT:
        # gpt-6-luna is a reasoning model; "none" makes it behave like a fast
        # chat model (matches the course homework agents).
        kwargs["extra_body"] = {"reasoning_effort": REASONING_EFFORT}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client().chat.completions.create(**kwargs)
    except APIError as exc:
        # Content filter, rate limits, transient gateway errors: don't crash the
        # app over one turn. Surface a safe fallback the caller can handle.
        print(f"[llm] call '{label}' failed: {exc}")
        return FALLBACK
    record_usage(label, resp.usage)
    return resp.choices[0].message.content or ""


def chat_json(messages: list[dict], *, label: str = "", default: dict | None = None) -> dict:
    """Like `chat`, but parse the reply as JSON and never raise on bad JSON."""
    raw = chat(messages, label=label, temperature=0.2, json_mode=True)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {"raw": raw}
