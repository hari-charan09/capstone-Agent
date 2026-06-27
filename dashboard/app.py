import json
import os
import streamlit as st
import pandas as pd

# ─────────────────────────────────────────────
#  Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Phishing Risk Dashboard",
    page_icon="🛡️",
    layout="wide",
)

# ─────────────────────────────────────────────
#  Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Glassmorphic card ── */
.email-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 14px;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.email-card:hover {
    border-color: rgba(255, 255, 255, 0.22);
    box-shadow: 0 4px 32px rgba(0,0,0,0.35);
}

/* ── Subject / sender ── */
.card-subject {
    font-size: 15px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 3px;
    line-height: 1.4;
}
.card-sender {
    font-size: 12px;
    color: #8892a4;
    margin-bottom: 14px;
    font-weight: 400;
}

/* ── Meta row ── */
.meta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}

/* ── Category badges ── */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.badge-phishing  { background: rgba(239,68,68,0.18);  color: #f87171; border: 1px solid rgba(239,68,68,0.35); }
.badge-scam      { background: rgba(245,101,101,0.18); color: #fc8181; border: 1px solid rgba(245,101,101,0.35); }
.badge-spam      { background: rgba(251,146,60,0.18);  color: #fb923c; border: 1px solid rgba(251,146,60,0.35); }
.badge-safe      { background: rgba(34,197,94,0.16);   color: #4ade80; border: 1px solid rgba(34,197,94,0.30); }

/* ── Score pill ── */
.score-pill {
    font-size: 12px;
    font-weight: 700;
    padding: 3px 11px;
    border-radius: 20px;
    background: rgba(139,92,246,0.18);
    color: #a78bfa;
    border: 1px solid rgba(139,92,246,0.35);
}

/* ── Confidence pill ── */
.conf-pill {
    font-size: 12px;
    font-weight: 500;
    color: #94a3b8;
}

/* ── Explanation text ── */
.explanation {
    font-size: 12.5px;
    color: #64748b;
    line-height: 1.55;
    border-left: 3px solid rgba(148,163,184,0.25);
    padding-left: 10px;
    margin-top: 4px;
}

/* ── Summary metric cards ── */
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
}
.metric-value {
    font-size: 32px;
    font-weight: 700;
    line-height: 1.1;
}
.metric-label {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* ── Section header ── */
.section-header {
    font-size: 13px;
    font-weight: 600;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin: 20px 0 10px 0;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.07) !important; margin: 20px 0; }

/* Sidebar refinements */
section[data-testid="stSidebar"] {
    background: rgba(15, 17, 26, 0.9);
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Data loading helpers
# ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@st.cache_data
def load_data():
    results_path  = os.path.join(PROJECT_ROOT, "results.json")

    with open(results_path,  "r", encoding="utf-8") as f:
        results = json.load(f)

    # Extract directly from results.json entries
    rows = []
    for r in results:
        rows.append({
            "email_id":    r["email_id"],
            "subject":     r.get("subject", "—"),
            "sender":      r.get("sender",  "—"),
            "score":       r["score"],
            "category":    r["category"],
            "confidence":  r["confidence"],
            "explanation": r["explanation"],
        })

    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────
#  Load
# ─────────────────────────────────────────────
try:
    df = load_data()
except FileNotFoundError as e:
    st.error(f"⚠️ Could not load data: {e}. Make sure results.json exists.")
    st.stop()


# ─────────────────────────────────────────────
#  Sidebar filters
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Phishing Risk\nDashboard")
    st.markdown("---")

    st.markdown("### Filters")

    all_categories = sorted(df["category"].unique().tolist())
    selected_cats = st.multiselect(
        "Category",
        options=all_categories,
        default=all_categories,
        help="Show only emails in the selected risk categories.",
    )

    min_score = st.slider(
        "Minimum Risk Score",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
        help="Only show emails with a risk score ≥ this value.",
    )

    st.markdown("---")
    if st.button("🔄 Reload data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Capstone · Email Fraud Agent")


# ─────────────────────────────────────────────
#  Apply filters
# ─────────────────────────────────────────────
filtered = df[
    (df["category"].isin(selected_cats)) &
    (df["score"] >= min_score)
].reset_index(drop=True)


# ─────────────────────────────────────────────
#  Page header
# ─────────────────────────────────────────────
st.markdown("# 🛡️ Phishing Risk Dashboard")
st.markdown("Real-time analysis of incoming emails for phishing, scam, spam, and safe classification.")
st.markdown("---")


# ─────────────────────────────────────────────
#  Summary metrics
# ─────────────────────────────────────────────
total     = len(df)
n_phish   = len(df[df["category"] == "phishing"])
n_scam    = len(df[df["category"] == "scam"])
n_spam    = len(df[df["category"] == "spam"])
n_safe    = len(df[df["category"] == "safe"])
avg_score = round(df["score"].mean(), 1)

cols = st.columns(6)
metrics = [
    ("Total Scanned",    total,    "#a78bfa"),
    ("⚠️ Phishing",      n_phish,  "#f87171"),
    ("🚨 Scam",          n_scam,   "#fc8181"),
    ("📬 Spam",          n_spam,   "#fb923c"),
    ("✅ Safe",          n_safe,   "#4ade80"),
    ("Avg Score",        avg_score,"#60a5fa"),
]
for col, (label, value, color) in zip(cols, metrics):
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:{color};">{value}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")


# ─────────────────────────────────────────────
#  Results count
# ─────────────────────────────────────────────
st.markdown(
    f"<div class='section-header'>Showing {len(filtered)} of {total} emails"
    f"{'  ·  filtered' if len(filtered) < total else ''}</div>",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
#  Category → badge HTML
# ─────────────────────────────────────────────
CATEGORY_ICONS = {
    "phishing": "🎣",
    "scam":     "💀",
    "spam":     "📧",
    "safe":     "✅",
}

def category_badge(cat: str) -> str:
    icon = CATEGORY_ICONS.get(cat, "")
    return f'<span class="badge badge-{cat}">{icon} {cat}</span>'

def score_color(score: int) -> str:
    if score >= 81: return "#f87171"
    if score >= 51: return "#fb923c"
    if score >= 21: return "#fbbf24"
    return "#4ade80"


# ─────────────────────────────────────────────
#  Email cards
# ─────────────────────────────────────────────
if filtered.empty:
    st.info("No emails match the current filters.")
else:
    for _, row in filtered.iterrows():
        conf_pct  = int(row["confidence"] * 100)
        s_color   = score_color(row["score"])

        st.markdown(f"""
        <div class="email-card">
            <div class="card-subject">{row['subject']}</div>
            <div class="card-sender">✉️ {row['sender']}</div>
            <div class="meta-row">
                {category_badge(row['category'])}
                <span class="score-pill">Score: <span style="color:{s_color}">{row['score']}</span> / 100</span>
                <span class="conf-pill">Confidence: {conf_pct}%</span>
                <span class="conf-pill" style="color:#475569; font-size:11px;"># {row['email_id']}</span>
            </div>
            <div class="explanation">🔍 {row['explanation']}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Raw data expander
# ─────────────────────────────────────────────
st.markdown("---")
with st.expander("📄 View raw data table"):
    st.dataframe(
        filtered[["email_id", "subject", "sender", "score", "category", "confidence", "explanation"]],
        use_container_width=True,
        hide_index=True,
    )
