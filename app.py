"""Case Coach — Streamlit app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from coach import adapt, agents, safety, tokens
from coach.cases import get_case, load_cases
from coach.orchestrator import CaseSession

# Optional browser voice input (Chrome/Edge). Falls back to text if unavailable.
try:
    from streamlit_mic_recorder import speech_to_text

    VOICE_INPUT = True
except Exception:
    VOICE_INPUT = False


def speak(text: str) -> None:
    """Have the browser read `text` aloud via the Web Speech API (no API/model)."""
    components.html(
        f"""
        <script>
          const u = new SpeechSynthesisUtterance({json.dumps(text)});
          u.rate = 1.0;
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(u);
        </script>
        """,
        height=0,
    )

st.set_page_config(page_title="Case Coach", page_icon="📊", layout="wide")

# --- Yale blue + white styling -------------------------------------------------
YALE_BLUE = "#00356B"
st.markdown(
    """
    <style>
      :root { --yale:#00356B; --yale2:#286DC0; --soft:#eef4fb; --ink:#17222e; --line:#d9e1ea; }
      .stApp { background:#ffffff; }
      html, body, [class*="css"] { font-family:"Inter","Helvetica Neue",Arial,sans-serif; }
      h1, h2, h3 { color:var(--yale); }
      /* Hero header */
      .cc-hero { background:linear-gradient(135deg,#00356B 0%,#0a4a8f 55%,#286DC0 100%);
                 color:#fff; padding:22px 26px; border-radius:16px; margin-bottom:16px;
                 box-shadow:0 8px 24px rgba(0,53,107,0.18); }
      .cc-hero .cc-title { font-size:2rem; font-weight:800; color:#fff; margin:0; letter-spacing:-0.5px; }
      .cc-hero .cc-sub { color:#d6e5f6; margin:6px 0 0; font-size:1rem; line-height:1.4; }
      /* Pills */
      .cc-pill { display:inline-block; padding:3px 12px; border-radius:999px; background:var(--yale);
                 color:#fff; font-size:0.78rem; font-weight:600; margin-right:6px; }
      .cc-pill-warn { background:#b00020; }
      /* Buttons */
      .stButton>button { background:var(--yale); color:#fff; border:0; border-radius:10px; font-weight:600;
                         padding:0.5rem 1rem; transition:all .15s ease; }
      .stButton>button:hover { background:#0a4a8f; transform:translateY(-1px);
                               box-shadow:0 4px 12px rgba(0,53,107,0.25); color:#fff; }
      /* Chat bubbles */
      [data-testid="stChatMessage"] { background:var(--soft); border:1px solid var(--line);
                                      border-radius:12px; padding:8px 14px; margin-bottom:8px; }
      /* Metrics as cards */
      [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:12px;
                                 padding:10px 12px; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
      div[data-testid="stMetricValue"] { color:var(--yale); font-weight:800; }
      /* Sidebar */
      section[data-testid="stSidebar"] { background:#f7fafd; border-right:1px solid var(--line); }
      .stAlert { border-radius:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="cc-hero">'
    '<p class="cc-title">📊 Case Coach</p>'
    '<p class="cc-sub">An adaptive multi-agent case-interview coach — it runs the case, grades your '
    "math and structure, coaches one fix at a time, and targets your weakest skill across sessions.</p>"
    "</div>",
    unsafe_allow_html=True,
)

# --- Session state -------------------------------------------------------------
if "session" not in st.session_state:
    st.session_state.session = None
if "last" not in st.session_state:
    st.session_state.last = None
if "debrief" not in st.session_state:
    st.session_state.debrief = None
if "voice" not in st.session_state:
    st.session_state.voice = False
if "spoken_text" not in st.session_state:
    st.session_state.spoken_text = None

cases = load_cases()
case_labels = {f"{c['title']}  ·  {c['type']} ({c['difficulty']})": c["id"] for c in cases}

# --- Sidebar: setup, safety, tokenomics ---------------------------------------
with st.sidebar:
    st.header("Start a case")
    choice = st.selectbox("Choose a case", list(case_labels.keys()))

    # Adaptive focus: read past scores and target your weakest dimension.
    weak = adapt.weakest_dimension()
    focus_on = False
    if weak:
        avgs = "  ·  ".join(f"{adapt.LABELS[d]} {v}" for d, v in weak["averages"].items())
        st.markdown(f"🎯 **Adaptive focus** — your weakest area is **{weak['label']}** (avg {weak['avg']}/5).")
        st.caption(f"Across your history: {avgs}")
        focus_on = st.checkbox(f"Target {weak['label']} this case", value=True)
    else:
        st.caption("🎯 Adaptive focus activates after your first graded case.")

    if st.button("▶ Start / restart case", use_container_width=True):
        case = get_case(case_labels[choice])
        sess = CaseSession(case=case, focus=(weak["dim"] if (weak and focus_on) else None))
        with st.spinner("The interviewer is opening the case…"):
            sess.start()
        st.session_state.session = sess
        st.session_state.last = None
        st.session_state.debrief = None
        st.rerun()

    # End-of-case debrief: breakdown of scores + written feedback.
    cur = st.session_state.session
    if cur is not None and cur.scores:
        if st.button("📋 End case & get summary", use_container_width=True):
            with st.spinner("Writing your debrief…"):
                st.session_state.debrief = agents.debrief(
                    cur.case, cur.conversation, cur.average_scores()
                )
            st.rerun()

    st.divider()
    st.subheader("🔊 Voice mode")
    st.session_state.voice = st.toggle(
        "Read the interviewer aloud", value=st.session_state.voice
    )
    if VOICE_INPUT:
        st.caption("Interviewer speaks; use the 🎤 mic below the chat to answer by voice (Chrome/Edge).")
    else:
        st.caption("Interviewer can speak aloud. For voice *input*, `pip install streamlit-mic-recorder` and use Chrome/Edge.")

    st.divider()
    st.subheader("🛡️ Safety limits")
    lim = safety.limits()
    st.caption(
        f"Max turns per session: **{lim['max_turns']}**  \n"
        f"Token budget per session: **{lim['token_budget']:,}**  \n"
        "Prompt-injection / answer-leak attempts are blocked before any model call."
    )

    st.divider()
    st.subheader("💸 Tokenomics (this session)")
    t = tokens.session_totals()
    c1, c2 = st.columns(2)
    c1.metric("Input tokens", f"{t['input']:,}")
    c2.metric("Output tokens", f"{t['output']:,}")
    c1.metric("Cached input", f"{t['cached']:,}")
    c2.metric("Model calls", f"{t['calls']:,}")
    cost = tokens.cost_usd(t)
    st.metric("Est. cost (USD)", f"${cost:,.4f}")
    st.caption("Set real gpt-6-luna prices in .env to populate cost. Full per-call log: data/token_log.jsonl")

# --- Main area ----------------------------------------------------------------
sess: CaseSession | None = st.session_state.session

if sess is None:
    st.info("Pick a case in the sidebar and click **Start** to begin your mock interview.")
    st.stop()

chat_col, coach_col = st.columns([2, 1])

with chat_col:
    focus_pill = (
        f' <span class="cc-pill">🎯 Focus: {adapt.LABELS[sess.focus]}</span>'
        if sess.focus
        else ""
    )
    st.markdown(
        f'<span class="cc-pill">Case: {sess.case["title"]}</span> '
        f'<span class="cc-pill">Phase: {sess.phase}</span>{focus_pill}',
        unsafe_allow_html=True,
    )
    st.write("")
    for turn in sess.conversation:
        role = "assistant" if turn["role"] == "assistant" else "user"
        avatar = "🧑‍💼" if role == "assistant" else "🎓"
        with st.chat_message(role, avatar=avatar):
            st.write(turn["content"])

with coach_col:
    dbf = st.session_state.debrief
    if dbf and dbf.get("headline"):
        st.subheader("📋 Case debrief")
        avg = sess.average_scores()
        d1, d2, d3 = st.columns(3)
        d1.metric("Structure", avg["structure"])
        d2.metric("MECE", avg["mece"])
        d3.metric("Depth", avg["depth"])
        st.success(dbf["headline"])
        if dbf.get("strengths"):
            st.markdown("**What you did well**")
            for s in dbf["strengths"]:
                st.markdown(f"- {s}")
        if dbf.get("improvements"):
            st.markdown("**To work on next**")
            for s in dbf["improvements"]:
                st.markdown(f"- {s}")
        if dbf.get("verdict"):
            st.caption(f"Verdict: {dbf['verdict']}")
        st.divider()

    st.subheader("🎯 Coach")
    last = st.session_state.last
    if last is None:
        st.caption("Your coaching feedback and live scores will appear here after your first answer.")
    else:
        if last.refused or last.halted:
            st.markdown(f'<span class="cc-pill cc-pill-warn">{last.note}</span>', unsafe_allow_html=True)
        if last.coach:
            st.info(last.coach)
        g = last.grader or {}
        if g.get("structure_score", 0):
            m1, m2, m3 = st.columns(3)
            m1.metric("Structure", g.get("structure_score", 0))
            m2.metric("MECE", g.get("mece_score", 0))
            m3.metric("Depth", g.get("depth_score", 0))
            if g.get("one_line"):
                st.caption(g["one_line"])
        checks = (last.math or {}).get("checks", [])
        if checks:
            st.markdown("**🔢 Math check**")
            for ch in checks:
                icon = {"correct": "✅", "close": "🟡", "wrong": "❌"}.get(ch.get("verdict"), "ℹ️")
                st.caption(f"{icon} {ch.get('claim', '')} — {ch.get('note', '')}")

    avg = sess.average_scores()
    if avg["structure"]:
        st.divider()
        st.markdown("**Average scores this case**")
        a1, a2, a3 = st.columns(3)
        a1.metric("Structure", avg["structure"])
        a2.metric("MECE", avg["mece"])
        a3.metric("Depth", avg["depth"])
        if len(sess.scores) >= 2:
            df = pd.DataFrame(sess.scores).set_index("turn")[["structure", "mece", "depth"]]
            st.line_chart(df)

# --- Voice output: read the latest interviewer message aloud ------------------
if st.session_state.voice and sess.conversation:
    latest_ai = next(
        (t["content"] for t in reversed(sess.conversation) if t["role"] == "assistant"),
        None,
    )
    if latest_ai and latest_ai != st.session_state.spoken_text:
        st.session_state.spoken_text = latest_ai
        speak(latest_ai)

# --- Candidate input (voice or text) ------------------------------------------
answer = None
if VOICE_INPUT:
    spoken = speech_to_text(
        language="en",
        start_prompt="🎤 Speak your answer",
        stop_prompt="⏹ Stop & send",
        just_once=True,
        use_container_width=True,
        key=f"stt_{sess.turn_count}",
    )
    if spoken:
        answer = spoken

typed = st.chat_input("Your answer… (or use the mic above)")
if typed:
    answer = typed

if answer:
    with st.spinner("Thinking…"):
        st.session_state.last = sess.submit(answer)
    st.rerun()
