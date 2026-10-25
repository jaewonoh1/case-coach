"""Case Coach — Streamlit app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from coach import safety, tokens
from coach.cases import get_case, load_cases
from coach.orchestrator import CaseSession

st.set_page_config(page_title="Case Coach", page_icon="📊", layout="wide")

# --- Yale blue + white styling -------------------------------------------------
YALE_BLUE = "#00356B"
st.markdown(
    f"""
    <style>
      .stApp {{ background: #ffffff; }}
      h1, h2, h3 {{ color: {YALE_BLUE}; }}
      .cc-title {{ font-size: 2rem; font-weight: 800; color: {YALE_BLUE}; margin-bottom: 0; }}
      .cc-sub {{ color: #44607d; margin-top: 0; }}
      .cc-pill {{ display:inline-block; padding: 2px 10px; border-radius: 999px;
                 background: {YALE_BLUE}; color: #fff; font-size: 0.8rem; font-weight:600; }}
      .cc-pill-warn {{ background:#b00020; }}
      .stButton>button {{ background:{YALE_BLUE}; color:#fff; border:0; border-radius:8px; font-weight:600; }}
      div[data-testid="stMetricValue"] {{ color:{YALE_BLUE}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="cc-title">📊 Case Coach</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="cc-sub">A multi-agent mock case interviewer — interviewer, '
    "math checker, structure grader, and coach.</p>",
    unsafe_allow_html=True,
)

# --- Session state -------------------------------------------------------------
if "session" not in st.session_state:
    st.session_state.session = None
if "last" not in st.session_state:
    st.session_state.last = None

cases = load_cases()
case_labels = {f"{c['title']}  ·  {c['type']} ({c['difficulty']})": c["id"] for c in cases}

# --- Sidebar: setup, safety, tokenomics ---------------------------------------
with st.sidebar:
    st.header("Start a case")
    choice = st.selectbox("Choose a case", list(case_labels.keys()))
    if st.button("▶ Start / restart case", use_container_width=True):
        case = get_case(case_labels[choice])
        sess = CaseSession(case=case)
        with st.spinner("The interviewer is opening the case…"):
            sess.start()
        st.session_state.session = sess
        st.session_state.last = None
        st.rerun()

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
    st.markdown(
        f'<span class="cc-pill">Case: {sess.case["title"]}</span> '
        f'<span class="cc-pill">Phase: {sess.phase}</span>',
        unsafe_allow_html=True,
    )
    st.write("")
    for turn in sess.conversation:
        role = "assistant" if turn["role"] == "assistant" else "user"
        avatar = "🧑‍💼" if role == "assistant" else "🎓"
        with st.chat_message(role, avatar=avatar):
            st.write(turn["content"])

with coach_col:
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

# --- Candidate input ----------------------------------------------------------
prompt = st.chat_input("Your answer…")
if prompt:
    with st.spinner("Thinking…"):
        st.session_state.last = sess.submit(prompt)
    st.rerun()
