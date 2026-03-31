"""
CDR Forensic Analyst — Police Hackathon Prototype
==================================================
60-30-10 Color Rule:
  60% → #0a0e1a  (deep navy)       — backgrounds, containers
  30% → #1c2333  (slate panel)     — cards, sidebars, surfaces
  10% → #f5a623  (electric amber)  — accents, CTAs, highlights
"""

import streamlit as st
import pandas as pd
import re
import logging
import os
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx

# ── Logging / Chain-of-Custody ────────────────────────────────────────────────
LOG_FILE = "chain_of_custody.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def log_query(query: str, result_count: int, investigator: str = "Investigator"):
    msg = f'USER="{investigator}" QUERY="{query}" RESULTS={result_count}'
    logging.info(msg)

# ── Color Palette (60-30-10) ──────────────────────────────────────────────────
# 60% Deep Navy  → #0a0e1a
# 30% Slate      → #1c2333
# 10% Amber      → #f5a623

PLOTLY_TEMPLATE = dict(
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#0a0e1a",
)
PLOTLY_FONT = dict(color="#c8d0e0")
PLOTLY_TITLE = dict(font=dict(size=17, color="#f5a623"))

# ── NLP / Query Parsing ───────────────────────────────────────────────────────
PHONE_RE = re.compile(r"\b(\d{10,15})\b")
DATE_KEYWORDS = {
    "today": 0,
    "yesterday": 1,
    "last week": 7,
    "last month": 30,
    "last 3 days": 3,
    "last 24 hours": 1,
    "past week": 7,
    "past month": 30,
}

def parse_query(query: str):
    q = query.lower()
    phones = PHONE_RE.findall(query)
    phones = list(dict.fromkeys(phones))

    days_back = None
    for kw, days in sorted(DATE_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in q:
            days_back = days
            break

    after_match = re.search(r"after\s+(\d{4}-\d{2}-\d{2})", q)
    before_match = re.search(r"before\s+(\d{4}-\d{2}-\d{2})", q)
    start_date = pd.to_datetime(after_match.group(1)) if after_match else None
    end_date = pd.to_datetime(before_match.group(1)) if before_match else None

    if days_back is not None and start_date is None:
        end_date = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
        start_date = end_date - pd.Timedelta(days=days_back)

    dur_sec = None
    dur_match = re.search(r"(longer|more)\s+than\s+(\d+)\s*(second|minute|min|sec)", q)
    if dur_match:
        val = int(dur_match.group(2))
        unit = dur_match.group(3)
        dur_sec = val * 60 if "min" in unit else val

    return {
        "phones": phones,
        "start_date": start_date,
        "end_date": end_date,
        "min_duration": dur_sec,
    }

# ── Data Filtering ────────────────────────────────────────────────────────────
def filter_df(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    result = df.copy()
    phones = params.get("phones", [])
    if phones:
        mask = pd.Series([False] * len(result), index=result.index)
        for p in phones:
            mask |= (result["caller"].astype(str) == p) | (result["receiver"].astype(str) == p)
        result = result[mask]
    if params.get("start_date") is not None:
        result = result[result["timestamp"] >= params["start_date"]]
    if params.get("end_date") is not None:
        result = result[result["timestamp"] <= params["end_date"]]
    if params.get("min_duration") is not None:
        result = result[result["duration"] >= params["min_duration"]]
    return result.sort_values("timestamp", ascending=False)

# ── Visualizations ────────────────────────────────────────────────────────────
def timeline_chart(df: pd.DataFrame):
    if df.empty:
        return None
    fig = px.scatter(
        df, x="timestamp", y="caller", color="receiver",
        size="duration", size_max=18,
        hover_data=["caller", "receiver", "duration", "timestamp"],
        title="📡 Call Timeline",
        labels={"timestamp": "Time", "caller": "Caller", "duration": "Duration (s)"},
        color_discrete_sequence=["#f5a623", "#e8893a", "#d4721f", "#c05c0c", "#f0b84d",
                                  "#e09830", "#cc7a1a", "#b86000", "#ffc04d", "#ff9500"],
    )
    fig.update_layout(**PLOTLY_TEMPLATE, font=PLOTLY_FONT, title=dict(text="📡 Call Timeline", font=dict(size=17, color="#f5a623")), height=420,
                      legend_title_text="Receiver",
                      xaxis=dict(gridcolor="#1c2333", zerolinecolor="#1c2333"),
                      yaxis=dict(gridcolor="#1c2333", zerolinecolor="#1c2333"))
    return fig

def network_graph(df: pd.DataFrame):
    if df.empty:
        return None
    G = nx.DiGraph()
    for _, row in df.iterrows():
        c, r, dur = str(row["caller"]), str(row["receiver"]), int(row["duration"])
        if G.has_edge(c, r):
            G[c][r]["weight"] += 1
            G[c][r]["total_duration"] += dur
        else:
            G.add_edge(c, r, weight=1, total_duration=dur)

    pos = nx.spring_layout(G, seed=42, k=2.5)
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines",
                            line=dict(width=1.5, color="rgba(245,166,35,0.53)"), hoverinfo="none")

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_deg = [G.degree(n) for n in G.nodes()]
    node_labels = list(G.nodes())

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=node_labels, textposition="top center",
        hovertext=[f"{n} | degree: {G.degree(n)}" for n in G.nodes()],
        hoverinfo="text",
        marker=dict(size=[10 + d * 5 for d in node_deg], color=node_deg,
                    colorscale=[[0, "#1c2333"], [0.5, "#e8893a"], [1, "#f5a623"]],
                    showscale=True, colorbar=dict(title=dict(text="Degree", font=dict(color="#f5a623")), thickness=12,
                    tickfont=dict(color="#c8d0e0")),
                    line=dict(width=1.5, color="#f5a623")),
        textfont=dict(color="#c8d0e0", size=9),
    )

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title=dict(text="🕸️ Caller–Receiver Network", font=dict(size=17, color="#f5a623")),
                        showlegend=False, hovermode="closest",
                        paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
                        font=dict(color="#c8d0e0"),
                        height=500,
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    ))
    return fig

def call_frequency_bar(df: pd.DataFrame):
    if df.empty:
        return None
    freq = (df.groupby("caller").size().reset_index(name="call_count")
            .sort_values("call_count", ascending=False).head(15))
    fig = px.bar(freq, x="caller", y="call_count",
                 title="📊 Top Callers by Volume",
                 color="call_count",
                 color_continuous_scale=[[0, "#1c2333"], [0.5, "#e8893a"], [1, "#f5a623"]],
                 labels={"caller": "Caller Number", "call_count": "# Calls"})
    fig.update_layout(**PLOTLY_TEMPLATE, font=PLOTLY_FONT, height=380,
                      xaxis=dict(gridcolor="#1c2333", tickfont=dict(color="#c8d0e0")),
                      yaxis=dict(gridcolor="#1c2333"))
    return fig

def duration_histogram(df: pd.DataFrame):
    if df.empty:
        return None
    fig = px.histogram(df, x="duration", nbins=30,
                       title="⏱️ Call Duration Distribution",
                       labels={"duration": "Duration (seconds)", "count": "# Calls"},
                       color_discrete_sequence=["#f5a623"])
    fig.update_layout(**PLOTLY_TEMPLATE, font=PLOTLY_FONT, height=360,
                      xaxis=dict(gridcolor="#1c2333"),
                      yaxis=dict(gridcolor="#1c2333"))
    return fig

def hourly_heatmap(df: pd.DataFrame):
    if df.empty:
        return None
    df2 = df.copy()
    df2["hour"] = df2["timestamp"].dt.hour
    df2["day"] = df2["timestamp"].dt.day_name()
    pivot = df2.groupby(["day", "hour"]).size().reset_index(name="calls")
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pivot["day"] = pd.Categorical(pivot["day"], categories=day_order, ordered=True)
    pivot = pivot.sort_values("day")
    fig = px.density_heatmap(pivot, x="hour", y="day", z="calls",
                              title="🗓️ Calls by Day & Hour",
                              color_continuous_scale=[[0, "#0a0e1a"], [0.5, "#e8893a"], [1, "#f5a623"]],
                              labels={"hour": "Hour of Day", "day": "Day", "calls": "# Calls"})
    fig.update_layout(**PLOTLY_TEMPLATE, font=PLOTLY_FONT, height=360,
                      xaxis=dict(gridcolor="#1c2333", dtick=1))
    return fig

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Barlow:wght@400;500;600;700&display=swap');

/* ── 60% Base: Deep Navy #0a0e1a ── */
html, body, [class*="css"], .main, .block-container {
  font-family: 'Barlow', sans-serif !important;
  background-color: #0a0e1a !important;
  color: #c8d0e0 !important;
}
.block-container { padding-top: 1.2rem !important; max-width: 1400px !important; }

/* ── Banner ── */
.banner {
  background: linear-gradient(135deg, #1c2333 0%, #0a0e1a 70%);
  border: 1px solid #2a3347;
  border-left: 5px solid #f5a623;
  padding: 1.4rem 2rem;
  border-radius: 10px;
  margin-bottom: 1.5rem;
  position: relative;
  overflow: hidden;
}
.banner::before {
  content: '';
  position: absolute;
  top: -30px; right: -30px;
  width: 120px; height: 120px;
  background: radial-gradient(circle, #f5a62320 0%, transparent 70%);
  border-radius: 50%;
}
.banner h1 {
  font-family: 'IBM Plex Mono', monospace;
  color: #f5a623;
  font-size: 1.75rem;
  margin: 0;
  letter-spacing: 3px;
}
.banner p { color: #8896a8; margin: 0.3rem 0 0; font-size: 0.92rem; }
.banner .badge {
  display: inline-block;
  background: #f5a62318;
  border: 1px solid #f5a62344;
  color: #f5a623;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.72rem;
  padding: 0.15rem 0.6rem;
  border-radius: 4px;
  margin-top: 0.5rem;
  letter-spacing: 1px;
}

/* ── 30% Panels: Slate #1c2333 ── */
.metric-row { display: flex; gap: 0.8rem; margin: 1rem 0; flex-wrap: wrap; }
.metric-card {
  background: #1c2333;
  border: 1px solid #2a3347;
  border-radius: 10px;
  padding: 1rem 1.4rem;
  flex: 1;
  min-width: 130px;
  text-align: center;
  transition: border-color 0.2s;
}
.metric-card:hover { border-color: #f5a62366; }
.metric-card .val {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.9rem;
  color: #f5a623;
  font-weight: 600;
  line-height: 1;
}
.metric-card .label {
  color: #8896a8;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-top: 0.3rem;
}

/* ── 10% Accent: Amber #f5a623 ── */
.stButton > button {
  background: #f5a623 !important;
  color: #0a0e1a !important;
  border: none !important;
  font-family: 'Barlow', sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 1px !important;
  border-radius: 6px !important;
  padding: 0.45rem 1.4rem !important;
  transition: opacity 0.2s, transform 0.1s !important;
}
.stButton > button:hover {
  opacity: 0.88 !important;
  transform: translateY(-1px) !important;
}

/* Query input */
.stTextInput > div > div > input {
  background-color: #1c2333 !important;
  border: 1px solid #2a3347 !important;
  color: #c8d0e0 !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.9rem !important;
  border-radius: 6px !important;
}
.stTextInput > div > div > input:focus {
  border-color: #f5a623 !important;
  box-shadow: 0 0 0 2px #f5a62322 !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background-color: #1c2333 !important;
  border-right: 1px solid #2a3347 !important;
}
[data-testid="stSidebar"] .stMarkdown { color: #8896a8 !important; }
[data-testid="stSidebar"] .stTextInput > div > div > input {
  background-color: #0a0e1a !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  background: #1c2333;
  border: 1px dashed #2a3347;
  border-radius: 8px;
}
[data-testid="stFileUploader"]:hover { border-color: #f5a62366; }

/* Info boxes */
.info-box {
  background: #0a0e1a;
  border: 1px solid #1c3a5c;
  border-left: 3px solid #4a90e2;
  border-radius: 8px;
  padding: 0.9rem 1.2rem;
  margin: 0.7rem 0;
  font-size: 0.88rem;
  color: #90b4e0;
}
.warn-box {
  background: #1a1000;
  border: 1px solid #3d2800;
  border-left: 3px solid #f5a623;
  border-radius: 8px;
  padding: 0.9rem 1.2rem;
  margin: 0.7rem 0;
  font-size: 0.88rem;
  color: #f5a623;
}
.success-box {
  background: #0a1a0a;
  border: 1px solid #1a3d1a;
  border-left: 3px solid #4caf50;
  border-radius: 8px;
  padding: 0.9rem 1.2rem;
  margin: 0.7rem 0;
  font-size: 0.88rem;
  color: #7ee787;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.4rem;
  background: transparent !important;
  border-bottom: 1px solid #2a3347;
  padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
  background: #1c2333 !important;
  border: 1px solid #2a3347 !important;
  border-bottom: none !important;
  border-radius: 6px 6px 0 0 !important;
  color: #8896a8 !important;
  font-family: 'Barlow', sans-serif !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  padding: 0.5rem 1rem !important;
}
.stTabs [aria-selected="true"] {
  background: #f5a623 !important;
  color: #0a0e1a !important;
  border-color: #f5a623 !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
  border-radius: 8px;
  border: 1px solid #2a3347;
  overflow: hidden;
}

/* Chain of custody log */
.log-box {
  background: #0a0e1a;
  border: 1px solid #2a3347;
  border-radius: 8px;
  padding: 1rem;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.75rem;
  color: #4caf50;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.6;
}

/* Param chips */
.param-chip {
  display: inline-block;
  background: #f5a62318;
  border: 1px solid #f5a62344;
  border-radius: 20px;
  padding: 0.2rem 0.8rem;
  margin: 0.2rem;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.78rem;
  color: #f5a623;
}

/* Section header */
.section-header {
  font-family: 'IBM Plex Mono', monospace;
  color: #f5a623;
  font-size: 1rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  border-bottom: 1px solid #2a3347;
  padding-bottom: 0.4rem;
  margin: 1.2rem 0 0.8rem;
}

/* Expander */
.streamlit-expanderHeader {
  background: #1c2333 !important;
  border: 1px solid #2a3347 !important;
  border-radius: 8px !important;
  color: #c8d0e0 !important;
  font-family: 'Barlow', sans-serif !important;
  font-weight: 600 !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
  background: #1c2333 !important;
  border: 1px solid #2a3347 !important;
  color: #c8d0e0 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0e1a; }
::-webkit-scrollbar-thumb { background: #2a3347; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #f5a62366; }
</style>
"""

# ── Streamlit Main ────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="CDR Forensic Analyst",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # Banner
    st.markdown("""
    <div class="banner">
      <h1>🔍 CDR FORENSIC ANALYST</h1>
      <p>Telecom Intelligence · Call Detail Record Analysis · Evidence-Grade Audit Trail</p>
      <span class="badge">POLICE HACKATHON PROTOTYPE</span>
      <span class="badge" style="margin-left:0.5rem; border-color:#4caf5044; color:#4caf50; background:#4caf5018;">SECURE · LOGGED · AUDITABLE</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="section-header">⚙️ Configuration</div>', unsafe_allow_html=True)
        investigator = st.text_input("Investigator Name / Badge #", value="Det. Smith #4421")
        case_id = st.text_input("Case ID", value="CASE-2026-0042")

        st.markdown('<div class="section-header">📂 Upload CDR Dataset</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Upload CSV (caller, receiver, timestamp, duration)",
            type=["csv"],
            help="Columns required: caller, receiver, timestamp, duration"
        )

        st.markdown('<div class="section-header">💡 Query Examples</div>', unsafe_allow_html=True)
        examples = [
            "Show calls from 9876543210 last week",
            "Calls between 9123456789 and 9876543210",
            "All calls longer than 120 seconds last month",
            "Calls from 9000011111 after 2024-12-01",
            "Show calls yesterday",
            "Calls before 2026-03-01",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex[:25]}"):
                st.session_state["query_text"] = ex

        st.markdown('<div class="section-header">📋 About</div>', unsafe_allow_html=True)
        st.markdown("""
        <small style='color:#8896a8; line-height:1.6'>
        Stack: Streamlit · Pandas · Plotly · NetworkX<br><br>
        Color rule: 60% Navy · 30% Slate · 10% Amber<br><br>
        All queries logged for chain-of-custody.<br>
        All data is synthetic & for demo only.
        </small>
        """, unsafe_allow_html=True)

    # ── Load Data ─────────────────────────────────────────────────────────────
    df = None

    def load_and_clean(raw_df):
        raw_df.columns = raw_df.columns.str.strip().str.lower()
        raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
        raw_df["caller"] = raw_df["caller"].astype(str).str.strip()
        raw_df["receiver"] = raw_df["receiver"].astype(str).str.strip()
        raw_df["duration"] = pd.to_numeric(raw_df["duration"], errors="coerce").fillna(0).astype(int)
        return raw_df

    if uploaded_file:
        try:
            df = load_and_clean(pd.read_csv(uploaded_file))
            st.session_state["df"] = df
            st.markdown(f"""
            <div class="success-box">
              ✅ Dataset loaded — <strong>{len(df):,}</strong> records 
              spanning {df['timestamp'].min().date()} → {df['timestamp'].max().date()}
            </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.markdown(f'<div class="warn-box">⚠️ Failed to parse CSV: {e}</div>', unsafe_allow_html=True)
    elif "df" in st.session_state:
        df = st.session_state["df"]
    else:
        st.markdown("""
        <div class="info-box">
          ℹ️ No dataset loaded. Upload a CSV in the sidebar or load the sample dataset below.
        </div>""", unsafe_allow_html=True)
        col_load, col_info = st.columns([1, 3])
        with col_load:
            if st.button("🗂️ Load Sample Dataset"):
                sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_cdr.csv")
                if os.path.exists(sample_path):
                    df = load_and_clean(pd.read_csv(sample_path))
                    st.session_state["df"] = df
                    st.rerun()
                else:
                    st.error("sample_cdr.csv not found. Run generate_sample.py first.")
        with col_info:
            st.markdown("""
            <div class="info-box">
              Required CSV columns: <code>caller</code>, <code>receiver</code>, <code>timestamp</code>, <code>duration</code>
            </div>""", unsafe_allow_html=True)

    # ── Overview Metrics ──────────────────────────────────────────────────────
    if df is not None:
        total_calls = len(df)
        unique_callers = df["caller"].nunique()
        unique_numbers = pd.concat([df["caller"], df["receiver"]]).nunique()
        avg_dur = int(df["duration"].mean())
        max_dur = int(df["duration"].max())
        date_span = (df["timestamp"].max() - df["timestamp"].min()).days

        st.markdown(f"""
        <div class="metric-row">
          <div class="metric-card"><div class="val">{total_calls:,}</div><div class="label">Total Calls</div></div>
          <div class="metric-card"><div class="val">{unique_callers}</div><div class="label">Unique Callers</div></div>
          <div class="metric-card"><div class="val">{unique_numbers}</div><div class="label">Unique Numbers</div></div>
          <div class="metric-card"><div class="val">{avg_dur}s</div><div class="label">Avg Duration</div></div>
          <div class="metric-card"><div class="val">{max_dur}s</div><div class="label">Max Duration</div></div>
          <div class="metric-card"><div class="val">{date_span}d</div><div class="label">Date Span</div></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Query Interface ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🗣️ Natural Language Query</div>', unsafe_allow_html=True)
    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "",
            value=st.session_state.get("query_text", ""),
            placeholder='e.g. "Show calls between 9876543210 and 9123456789 last week"',
            label_visibility="collapsed",
        )
    with col_btn:
        run_query = st.button("🔍 Analyze", use_container_width=True)

    if query and df is not None and (run_query or st.session_state.get("last_query") != query):
        st.session_state["last_query"] = query
        params = parse_query(query)

        # Show parsed parameters as chips
        chips_html = '<div style="margin:0.6rem 0">'
        if params["phones"]:
            for p in params["phones"]:
                chips_html += f'<span class="param-chip">📱 {p}</span>'
        if params["start_date"]:
            chips_html += f'<span class="param-chip">📅 from {params["start_date"].date()}</span>'
        if params["end_date"]:
            chips_html += f'<span class="param-chip">📅 to {params["end_date"].date()}</span>'
        if params["min_duration"]:
            chips_html += f'<span class="param-chip">⏱ >{params["min_duration"]}s</span>'
        if not any([params["phones"], params["start_date"], params["min_duration"]]):
            chips_html += '<span class="param-chip">⚠️ no filters — showing all</span>'
        chips_html += '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)

        filtered = filter_df(df, params)
        log_query(f'[{case_id}] {query}', len(filtered), investigator)

        if filtered.empty:
            st.markdown('<div class="warn-box">⚠️ No records match the query criteria.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="success-box">✅ Found <strong>{len(filtered):,}</strong> matching records.</div>', unsafe_allow_html=True)

            tabs = st.tabs(["📋 Results", "📡 Timeline", "🕸️ Network", "📊 Frequency", "⏱️ Duration", "🗓️ Heatmap", "🔒 Custody"])

            # Tab 0: Results Table
            with tabs[0]:
                display_df = filtered[["timestamp", "caller", "receiver", "duration"]].rename(
                    columns={"timestamp": "Timestamp", "caller": "Caller",
                             "receiver": "Receiver", "duration": "Duration (s)"}
                )
                st.dataframe(display_df, use_container_width=True, height=420)
                col_dl1, col_dl2 = st.columns([1, 4])
                with col_dl1:
                    csv_export = filtered.to_csv(index=False).encode()
                    st.download_button(
                        "⬇️ Export CSV",
                        data=csv_export,
                        file_name=f"cdr_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            # Tab 1: Timeline
            with tabs[1]:
                fig_tl = timeline_chart(filtered)
                if fig_tl:
                    st.plotly_chart(fig_tl, use_container_width=True)
                    st.markdown('<small style="color:#8896a8">Bubble size = call duration. Color = receiver number.</small>', unsafe_allow_html=True)

            # Tab 2: Network Graph
            with tabs[2]:
                if len(filtered) > 500:
                    st.markdown('<div class="warn-box">⚠️ Large dataset — showing network for first 500 records to maintain performance.</div>', unsafe_allow_html=True)
                    net_df = filtered.head(500)
                else:
                    net_df = filtered
                fig_net = network_graph(net_df)
                if fig_net:
                    st.plotly_chart(fig_net, use_container_width=True)
                    st.markdown('<small style="color:#8896a8">Node size & color = call degree (connections). Amber = high activity.</small>', unsafe_allow_html=True)

            # Tab 3: Frequency Bar
            with tabs[3]:
                fig_bar = call_frequency_bar(filtered)
                if fig_bar:
                    st.plotly_chart(fig_bar, use_container_width=True)
                # Also show top pairs
                st.markdown('<div class="section-header" style="font-size:0.85rem">Top Caller–Receiver Pairs</div>', unsafe_allow_html=True)
                pairs = (filtered.groupby(["caller", "receiver"])
                         .agg(calls=("duration", "count"), total_dur=("duration", "sum"))
                         .reset_index().sort_values("calls", ascending=False).head(10))
                st.dataframe(pairs, use_container_width=True, height=260)

            # Tab 4: Duration Histogram
            with tabs[4]:
                fig_hist = duration_histogram(filtered)
                if fig_hist:
                    st.plotly_chart(fig_hist, use_container_width=True)
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("Mean Duration", f"{int(filtered['duration'].mean())}s")
                with col_s2:
                    st.metric("Median Duration", f"{int(filtered['duration'].median())}s")
                with col_s3:
                    st.metric("Std Dev", f"{int(filtered['duration'].std())}s")

            # Tab 5: Hourly Heatmap
            with tabs[5]:
                fig_heat = hourly_heatmap(filtered)
                if fig_heat:
                    st.plotly_chart(fig_heat, use_container_width=True)
                    st.markdown('<small style="color:#8896a8">Amber = high activity. Useful for detecting unusual call patterns (night-time, weekends).</small>', unsafe_allow_html=True)

            # Tab 6: Chain of Custody
            with tabs[6]:
                st.markdown('<div class="section-header">🔒 Chain of Custody Log</div>', unsafe_allow_html=True)
                st.markdown("""
                <div class="info-box">
                  All queries are appended to <code>chain_of_custody.log</code> with timestamp, 
                  investigator badge, case ID, query text, and result count. 
                  In production, make this file append-only (<code>chmod a-w</code>).
                </div>""", unsafe_allow_html=True)
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r") as f:
                        log_content = f.read()
                    st.markdown(f'<div class="log-box">{log_content}</div>', unsafe_allow_html=True)
                    col_log1, _ = st.columns([1, 4])
                    with col_log1:
                        st.download_button(
                            "⬇️ Download Full Log",
                            data=log_content.encode(),
                            file_name=f"custody_log_{case_id}_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            use_container_width=True,
                        )
                else:
                    st.info("Log file will be created after first query.")

    elif df is None and query:
        st.markdown('<div class="warn-box">⚠️ Please upload or load a CDR dataset first.</div>', unsafe_allow_html=True)

    # ── Full Dataset Explorer ─────────────────────────────────────────────────
    if df is not None:
        with st.expander("🗃️ Full Dataset Explorer"):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filter_caller = st.text_input("Filter by Caller", placeholder="e.g. 9876543210", key="exp_caller")
            with col_f2:
                filter_receiver = st.text_input("Filter by Receiver", placeholder="e.g. 9123456789", key="exp_receiver")
            with col_f3:
                sort_col = st.selectbox("Sort by", ["timestamp", "duration", "caller", "receiver"], key="exp_sort")

            exp_df = df.copy()
            if filter_caller:
                exp_df = exp_df[exp_df["caller"].str.contains(filter_caller, na=False)]
            if filter_receiver:
                exp_df = exp_df[exp_df["receiver"].str.contains(filter_receiver, na=False)]
            exp_df = exp_df.sort_values(sort_col, ascending=(sort_col == "timestamp"))
            st.dataframe(exp_df.head(500), use_container_width=True, height=380)
            st.caption(f"Showing first 500 of {len(exp_df):,} records matching explorer filters.")

        # ── Suspect Analysis ──────────────────────────────────────────────────
        with st.expander("🚨 Suspect / High-Activity Numbers"):
            top_n = st.slider("Top N numbers by call volume", 3, 20, 5, key="suspect_n")
            all_nums = pd.concat([
                df["caller"].value_counts().rename("as_caller"),
                df["receiver"].value_counts().rename("as_receiver")
            ], axis=1).fillna(0)
            all_nums["total"] = all_nums["as_caller"] + all_nums["as_receiver"]
            top_suspects = all_nums.sort_values("total", ascending=False).head(top_n).reset_index()
            top_suspects.columns = ["Phone Number", "Calls Made", "Calls Received", "Total Activity"]
            st.dataframe(top_suspects, use_container_width=True)

            fig_susp = px.bar(top_suspects, x="Phone Number", y=["Calls Made", "Calls Received"],
                              title=f"📊 Top {top_n} Most Active Numbers",
                              barmode="stack",
                              color_discrete_sequence=["#f5a623", "#1c2333"],
                              labels={"value": "# Calls", "variable": "Direction"})
            fig_susp.update_layout(**PLOTLY_TEMPLATE, font=PLOTLY_FONT, height=350,
                                   xaxis=dict(gridcolor="#1c2333"),
                                   yaxis=dict(gridcolor="#1c2333"),
                                   legend=dict(font=dict(color="#c8d0e0")))
            st.plotly_chart(fig_susp, use_container_width=True)


if __name__ == "__main__":
    main()
