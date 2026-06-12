"""
╔══════════════════════════════════════════════════════════════════════════╗
║   DVVNL FEEDER-WISE AT&C LOSS ANALYTICS DASHBOARD                       ║
║   Powered by: DuckDB + Streamlit + Plotly                                ║
║   Run: streamlit run app.py                                              ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import duckdb
import io
from datetime import datetime

from config import DB_PATH, APRIL_START, APRIL_END, COLOR_PALETTE, KPI_THRESHOLDS
from queries import load_all_data, process_all

from charts import (
    chart_atc_gauge_bars, chart_zone_radar, chart_treemap_atc,
    chart_treemap_revenue, chart_performance_heatmap, chart_funnel,
    chart_loss_histogram, chart_waterfall_decomposition, chart_energy_sankey
)

# Add after imports in app.py
# ── SESSION STATE OPTIMIZATION ──────────────────────────────────────────────
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.last_filters = None
    st.session_state.cached_df = None

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DVVNL Feeder Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container{
    padding-top:0.5rem !important;
    padding-bottom:0.5rem !important;
    padding-left:2rem !important;
    padding-right:2rem !important;
    max-width:100% !important;
}
[data-testid="stHeader"]{ display:none; }
[data-testid="stToolbar"]{ display:none; }

/* ── HIDE SIDEBAR COMPLETELY ── */
section[data-testid="stSidebar"]{ display:none !important; }
[data-testid="collapsedControl"]{ display:none !important; }

/* ── FILTER BAR ── */
.filter-bar{
    background:linear-gradient(90deg,#1e3a5f,#1d4ed8,#1e3a5f);
    border-radius:12px;
    padding:10px 16px;
    margin:4px 0 8px 0;
    display:flex;
    align-items:center;
    gap:8px;
    flex-wrap:nowrap;
    overflow-x:auto;
}
.filter-bar label{
    color:#bfdbfe !important;
    font-size:11px !important;
    font-weight:700 !important;
    white-space:nowrap;
    margin-bottom:2px !important;
}
.filter-bar .stSelectbox > div,
.filter-bar .stToggle{
    min-width:120px;
}
/* Make filter bar selectboxes compact */
.filter-bar [data-baseweb="select"] > div{
    background:rgba(255,255,255,0.12) !important;
    border:1px solid rgba(255,255,255,0.25) !important;
    color:#ffffff !important;
    font-size:12px !important;
    font-weight:700 !important;
    border-radius:8px !important;
    min-height:34px !important;
    padding:2px 8px !important;
}
.filter-bar [data-baseweb="select"] svg{ fill:#93c5fd !important; }
.filter-bar [data-baseweb="select"] [data-testid="stMarkdownContainer"] p{
    color:#ffffff !important; font-size:12px !important;
}
.filter-bar .stButton > button{
    background:rgba(239,68,68,0.85) !important;
    color:#fff !important;
    border:none !important;
    border-radius:8px !important;
    padding:6px 14px !important;
    font-size:12px !important;
    font-weight:800 !important;
    white-space:nowrap;
    margin-top:18px;
}
</style>
""", unsafe_allow_html=True)



# Global Plotly config — disables slow animations and unnecessary features
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "staticPlot": False,
    "responsive": True,
    "scrollZoom": False,
}
# ── BASE LAYOUT HELPER ──────────────────────────────────────────────────────
def dark_layout(**kwargs):
    base = dict(
        paper_bgcolor="#eef2ff",
        plot_bgcolor="#eef2ff",
        font=dict(family="'Inter', 'Syne', sans-serif", color="#0f172a", size=14),
        margin=dict(l=45, r=20, t=40, b=55),
        legend=dict(bgcolor="#eef2ff", bordercolor="#c7d2fe", borderwidth=1,
                    font=dict(color="#0f172a", size=13)),
        xaxis=dict(gridcolor="#dbeafe", zerolinecolor="#dbeafe", tickfont=dict(color="#475569", size=12)),
        yaxis=dict(gridcolor="#dbeafe", zerolinecolor="#dbeafe", tickfont=dict(color="#475569", size=12)),
    )
    base.update(kwargs)
    return base

# ── CUSTOM CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', 'Syne', sans-serif; background-color: #ffffff; color: #0f172a; }
.main, .stApp { background-color: #ffffff; }

.dvvnl-header {
    background: linear-gradient(90deg,#a0bed3,#c7d2fe,#a0bed3);
    border-bottom: 2px solid #a5b4fc;
    padding: 10px 15px;
    border-radius: 16px;
    margin: 2px 0 2px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
}
.dvvnl-title  { font-size:20px; font-weight:900; color:#0f172a; letter-spacing:0.5px; }
.dvvnl-sub    { color:#475569; font-size:16px; line-height:1.5;font-weight:700; }
.live-badge   { background:#93c5fd; border:1px solid #60a5fa; color:#0f172a; padding:6px 16px; border-radius:999px; font-size:13px; font-weight:800; letter-spacing:0.5px; }

.kpi-card     { background:linear-gradient(135deg,#c7d2fe,#8ab3d0); border-radius:18px; padding:20px 14px; border-left:5px solid #4338ca; margin-bottom:12px; box-shadow:0 12px 24px rgba(67,56,202,0.12); }
.kpi-label    { color:#334155; font-size:13px; text-transform:uppercase; font-weight:700; margin-bottom:6px; }
.kpi-value    { font-family:'JetBrains Mono',monospace; font-size:20px; font-weight:600; line-height:1; }

.section-title{ display:flex; justify-content:center; align-items:center; gap:10px; background:#457a9f; color:#ffffff; font-size:20px; font-weight:900; text-transform:uppercase; border:1px solid #457a9f; border-radius:16px; padding:12px 20px; margin:10px auto 12px auto; }

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { font-weight:900; }
.stMarkdown h1 { font-size:36px; }
.stMarkdown h2 { font-size:28px; }
.stMarkdown h3 { font-size:22px; }
.stMarkdown h4 { font-size:18px; }
.stMarkdown strong, .stMarkdown b { font-weight:900; }

[data-testid="stPlotlyChart"] > div:first-child, [data-testid="stPlotlyChart"] section > div:first-child {
    background:#dbeafe !important;
    border:1px solid #457a9f !important;
    border-radius:20px !important;
    padding:20px !important;
    box-shadow:0 20px 40px rgba(15,23,42,0.18) !important;
}
[data-testid="stPlotlyChart"] svg { background:transparent !important; }

.stTabs [data-baseweb="tab-list"] { background:#c7d2fe; border-bottom:1px solid #457a9f; gap:6px; }
.stTabs [data-baseweb="tab"] { color:#334155; background:#dbeafe; border-radius:10px 10px 0 0; font-size:16px; font-weight:900; padding:10px 16px; }
.stTabs [data-baseweb="tab"] span, .stTabs [data-baseweb="tab"] div { font-size:16px !important; font-weight:900 !important; }
.stTabs [aria-selected="true"] { color:#ffffff !important; background:#457a9f !important; font-size:16px; font-weight:900; }

[data-testid="metric-container"] { background:#dbeafe; border:1px solid #457a9f; border-radius:14px; padding:14px 18px; }
[data-testid="metric-container"] label { color:#475569 !important; font-size:12px !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#0f172a !important; font-family:'JetBrains Mono',monospace; }

button, .stButton>button { border-radius:14px !important; transition: transform 0.18s ease, box-shadow 0.18s ease; }
button:hover, .stButton>button:hover { transform: translateY(-1px); box-shadow:0 12px 24px rgba(124,58,237,0.2); }

.st-expander { background:#f8fbff; border:1px solid #c7d2fe; border-radius:18px; }
.st-expander__header { background:#dbeafe; border-bottom:1px solid #c7d2fe; border-radius:18px 18px 0 0; }

#MainMenu, footer, header { visibility:hidden; }

/* ========================================= */
/* === ENHANCED SIDEBAR STYLING === */
/* ========================================= */

/* Sidebar Container */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #eef2ff 0%, #ffffff 40%, #8cb4d0 100%) !important;
    border-right: 2px solid #a5b4fc !important;
    box-shadow: 4px 0 25px rgba(99, 102, 241, 0.08) !important;
    padding: 1.5rem 1.2rem !important;
}

/* Sidebar Headings (h3) */
section[data-testid="stSidebar"] h3 {
    background: linear-gradient(135deg, #507a99, #507a99) !important;
    color: #ffffff !important;
    padding: 12px 16px !important;
    border-radius: 14px !important;
    text-align: center !important;
    font-size: 14px !important;
    font-weight: 800 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25) !important;
    margin-top: 1.5rem !important;
    margin-bottom: 1.2rem !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
}

/* Inputs, Selects, Date Pickers */
section[data-testid="stSidebar"] input, 
section[data-testid="stSidebar"] select, 
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(10px) !important;
    border: 1.5px solid #c7d2fe !important;
    color: #1e293b !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
}

section[data-testid="stSidebar"] input:focus, 
section[data-testid="stSidebar"] select:focus,
section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15) !important;
    background: rgba(255, 255, 255, 1) !important;
}

/* Dropdown Menus */
section[data-testid="stSidebar"] [data-baseweb="menu"] {
    background: rgba(255, 255, 255, 0.98) !important;
    backdrop-filter: blur(10px) !important;
    border: 1.5px solid #c7d2fe !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 20px rgba(0,0,0,0.1) !important;
    padding: 6px !important;
}
section[data-testid="stSidebar"] [data-baseweb="menu"] li {
    color: #1e293b !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    margin: 2px 0 !important;
}
section[data-testid="stSidebar"] [data-baseweb="menu"] li:hover {
    background: #ffffff !important;
    color: #4338ca !important;
}
section[data-testid="stSidebar"] [data-baseweb="menu"] li[aria-selected="true"] {
    background: #c7d2fe !important;
    color: #3730a3 !important;
    font-weight: 800 !important;
}

/* Labels */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span {
    color: #334155 !important;
    font-size: 13.5px !important;
    font-weight: 700 !important;
    margin-bottom: 6px !important;
    letter-spacing: 0.3px !important;
}

/* Buttons */
section[data-testid="stSidebar"] .stButton>button {
    background: linear-gradient(135deg, #507a99, #507a99) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 15px !important;
    font-weight: 800 !important;
    padding: 0.7rem 1rem !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    width: 100% !important;
}

section[data-testid="stSidebar"] .stButton>button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4) !important;
    background: linear-gradient(135deg, #4f46e5, #457a9f) !important;
}

section[data-testid="stSidebar"] .stButton>button:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3) !important;
}

/* Toggles / Switches */
section[data-testid="stSidebar"] .stToggle label span[data-baseweb="checkbox"] {
    background-color: #ffffff !important;
    border: 2px solid #a5b4fc !important;
    transition: all 0.3s ease !important;
}
section[data-testid="stSidebar"] .stToggle input:checked + label span[data-baseweb="checkbox"] {
    background-color: #6366f1 !important;
    border-color: #6366f1 !important;
}
section[data-testid="stSidebar"] .stToggle label span[data-baseweb="checkbox"] > div {
    background-color: #ffffff !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
}

/* Dividers */
section[data-testid="stSidebar"] hr {
    border: none !important;
    height: 2px !important;
    background: linear-gradient(90deg, transparent, #a5b4fc, transparent) !important;
    margin: 1.5rem 0 !important;
    opacity: 0.7 !important;
}

/* Custom Scrollbar */
section[data-testid="stSidebar"]::-webkit-scrollbar { width: 6px; }
section[data-testid="stSidebar"]::-webkit-scrollbar-track { background: transparent; }
section[data-testid="stSidebar"]::-webkit-scrollbar-thumb { background: #a5b4fc; border-radius: 10px; }
section[data-testid="stSidebar"]::-webkit-scrollbar-thumb:hover { background: #818cf8; }

</style>
""", unsafe_allow_html=True)

# ── HELPERS ──────────────────────────────────────────────────────────────────
def fmt_lakh(n):
    if n is None or (isinstance(n, float) and pd.isna(n)): return "—"
    if abs(n) >= 1e7:  return f"{n/1e7:.2f} Cr"
    if abs(n) >= 1e5:  return f"{n/1e5:.2f} L"
    if abs(n) >= 1e3:  return f"{n/1e3:.1f} K"
    return f"{n:.0f}"

def atc_color(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "#64748b"
    if v < KPI_THRESHOLDS["atc_good"]:  return "#22c55e"
    if v < KPI_THRESHOLDS["atc_ok"]:   return "#eab308"
    if v < KPI_THRESHOLDS["atc_high"]: return "#f97316"
    return "#ef4444"

def rating(v):
    if v is None: return "N/A"
    if v < KPI_THRESHOLDS["atc_good"]:  return "✅ GOOD"
    if v < KPI_THRESHOLDS["atc_ok"]:   return "⚠️ OK"
    if v < KPI_THRESHOLDS["atc_high"]: return "🟠 HIGH"
    return "🔴 CRITICAL"


# ── HIERARCHY SUMMARY TABLE FUNCTION ─────────────────────────────────────────
def create_hierarchy_summary(df):
    """Create a summary table showing Zone, Circle, Division, Substations, Feeders, and Feeder Type"""
    
    if df.empty:
        return pd.DataFrame()
    
    # Check if required columns exist
    has_substation = 'substation' in df.columns
    has_division = 'division' in df.columns
    has_circle = 'circle' in df.columns
    has_zone = 'zone' in df.columns
    has_feeder_nature = 'feeder_nature' in df.columns
    
    if not (has_zone and has_circle):
        return pd.DataFrame()
    
    # Create aggregation based on available columns
    if has_division:
        group_cols = ['zone', 'circle', 'division']
    else:
        group_cols = ['zone', 'circle']
    
    # Build aggregation using named columns to avoid renaming issues
    agg_dict = {
        'outgoing_feeder': 'count',
    }
    
    if has_substation:
        agg_dict['substation'] = 'nunique'
    
    # Create the aggregated dataframe with proper column names from the start
    summary_df = df.groupby(group_cols).agg(**{
        'No_of_Feeders': ('outgoing_feeder', 'count'),
        **({'No_of_Substations': ('substation', 'nunique')} if has_substation else {})
    }).reset_index()
    
    # Rename group columns for display
    summary_df = summary_df.rename(columns={
        'zone': '🗺️ Zone',
        'circle': '🏙️ Circle',
        'division': '🏢 Division' if has_division else 'division'
    })
    
    # Drop division column if it exists but wasn't in group_cols
    if not has_division and 'division' in summary_df.columns:
        summary_df = summary_df.drop(columns=['division'])
    
    # Add Feeder Type breakdown if available
    if has_feeder_nature:
        # Create feeder type breakdown using named aggregation
        feeder_type_df = df.groupby(group_cols)['feeder_nature'].apply(
            lambda x: x.value_counts().to_dict()
        ).reset_index(name='feeder_type_breakdown')
        
        # Merge with main summary
        summary_df = summary_df.merge(feeder_type_df, on=group_cols, how='left')
        
        # Format feeder type breakdown as string
        def format_feeder_types(breakdown):
            if not breakdown or pd.isna(breakdown):
                return "—"
            parts = []
            for feeder_type, count in breakdown.items():
                parts.append(f"{feeder_type}: {count}")
            return " | ".join(parts)
        
        summary_df['🌾 Feeder Types'] = summary_df['feeder_type_breakdown'].apply(format_feeder_types)
        summary_df = summary_df.drop(columns=['feeder_type_breakdown'])
    
    # Sort by Zone, then Circle, then Division
    sort_cols = ['🗺️ Zone', '🏙️ Circle']
    if has_division:
        sort_cols.append('🏢 Division')
    summary_df = summary_df.sort_values(sort_cols).reset_index(drop=True)
    
    # Add serial number
    summary_df.insert(0, '#', range(1, len(summary_df) + 1))
    
    return summary_df



def kpi_card(label, value, unit="", color="#2563eb", sub=""):
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color:{color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value}<span style="font-size:14px;color:#64748b"> {unit}</span></div>
        <div style="color:#475569;font-size:11px;margin-top:2px">{sub}</div>
    </div>""", unsafe_allow_html=True)

def export_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Feeder_KPIs")
    return buf.getvalue()

# ── DB CONNECTION (CACHED FOREVER — connection is cheap) ─────────────────────
@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)

# ── RAW DATA LOAD — hits DuckDB ONCE, cached for 10 minutes ──────────────────
@st.cache_data(ttl=600, show_spinner="⚡ Loading from  DB (first load only)...")
def load_raw_data(month_start: str, month_end: str):
    con = get_connection()
    return load_all_data(con, month_start, month_end)

# ── PROCESS DATA — pure pandas, instant on filter change ─────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_processed_data(month_start: str, month_end: str,
                       zone_filter: str, circle_filter: str, nature_filter: str):
    energy_df, billing_df = load_raw_data(month_start, month_end)
    return process_all(energy_df, billing_df, month_start, month_end,
                       zone_filter, circle_filter, nature_filter)

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
# ── FIXED PERIOD ──────────────────────────────────────────────────────────────
month_start = pd.to_datetime(APRIL_START).date()
month_end   = pd.to_datetime(APRIL_END).date()

# ── LOAD FILTER OPTIONS (single cached call) ──────────────────────────────────
try:
    from config import ENERGY_COLS as EC, BILLING_COLS as BC, ENERGY_TABLE, BILLING_TABLE
    _init        = get_processed_data(str(month_start), str(month_end),
                                      "All Zones", "All Circles", "All Types")
    _init_df     = _init['df']
    zones_list   = sorted(_init_df['zone'].dropna().unique().tolist())     if 'zone'     in _init_df.columns else []
    circles_list = sorted(_init_df['circle'].dropna().unique().tolist())   if 'circle'   in _init_df.columns else []
    div_list_all = sorted(_init_df['division'].dropna().unique().tolist()) if 'division' in _init_df.columns else []
except Exception:
    zones_list, circles_list, div_list_all = [], [], []

# ── INITIALIZE FILTER VARIABLES WITH DEFAULTS ─────────────────────────────────
zone_sel = "All Zones"
circle_sel = "All Circles"
division_sel = "All Divisions"
nature_sel = "All Types"
agri_filter = "All"
sort_col = "atc_loss_pct"
sort_asc = False

# Sort options dictionary
sort_options_pct = {
    "ATC LOSS %": "atc_loss_pct",
    "BILLING EFFICIENCY %": "billing_efficiency_pct",
    "COLLECTION EFFICIENCY %": "collection_efficiency_pct",
    "LINE LOSS %": "line_loss_pct",
    "INPUT ENERGY (KWH)": "input_energy_kwh",
    "REVENUE REALIZED": "revenue_realized"
}

# ── LOAD DATA ────────────────────────────────────────────────────────────────
result       = get_processed_data(str(month_start), str(month_end), zone_sel, circle_sel, nature_sel)
df           = result['df'].copy()
unmatched_df = result.get('unmatched_df', pd.DataFrame())

# Safe defaults — prevents NameError if agri filter hasn't run yet
zone_df  = pd.DataFrame()
circ_df  = pd.DataFrame()
div_df   = pd.DataFrame()
nat_df   = pd.DataFrame()
hist_df  = pd.DataFrame()
funnel_data = {}

# ── 1. APPLY DIVISION & AGRICULTURE FILTERS (ONCE) ───────────────────────────
if 'agri_filter' not in locals():
    agri_filter = "All"

if "division" in df.columns and division_sel != "All Divisions":
    df = df[df["division"] == division_sel].reset_index(drop=True)

if agri_filter == "Agriculture":
    df = df[df["feeder_nature"].str.contains("Agri", case=False, na=False)].reset_index(drop=True)
elif agri_filter == "Non-Agriculture":
    df = df[~df["feeder_nature"].str.contains("Agri", case=False, na=True)].reset_index(drop=True)

# ── 2. RECALCULATE AGGREGATES (ONCE - HIGHLY OPTIMIZED) ──────────────────────
def build_agg_dict(cols):
    agg_dict = {}
    if "outgoing_feeder" in cols: agg_dict["outgoing_feeder"] = "count"
    if "input_energy_kwh" in cols: agg_dict["input_energy_kwh"] = "sum"
    if "sold_energy_kwh" in cols: agg_dict["sold_energy_kwh"] = "sum"
    if "net_assessment" in cols: agg_dict["net_assessment"] = "sum"
    if "revenue_realized" in cols: agg_dict["revenue_realized"] = "sum"
    return agg_dict

def calc_kpi_aggs(agg_df):
    inp = agg_df.get("input_energy_kwh", pd.Series([0])).sum()
    sold = agg_df.get("sold_energy_kwh", pd.Series([0])).sum()
    ass = agg_df.get("net_assessment", pd.Series([0])).sum()
    rev = agg_df.get("revenue_realized", pd.Series([0])).sum()
    
    agg_df["line_loss_pct"] = ((inp - sold) / inp * 100) if inp > 0 else 0
    agg_df["billing_efficiency_pct"] = (sold / inp * 100) if inp > 0 else 0
    agg_df["collection_efficiency_pct"] = (rev / ass * 100) if ass > 0 else 0
    be = sold / inp if inp > 0 else 0
    ce = rev / ass if ass > 0 else 0
    agg_df["atc_loss_pct"] = (1 - be * ce) * 100
    return agg_df

# Grand Totals
total_input = float(df["input_energy_kwh"].sum()) if "input_energy_kwh" in df.columns else 0.0
total_sold = float(df["sold_energy_kwh"].sum()) if "sold_energy_kwh" in df.columns else 0.0
total_assessment = float(df["net_assessment"].sum()) if "net_assessment" in df.columns else 0.0
total_revenue = float(df["revenue_realized"].sum()) if "revenue_realized" in df.columns else 0.0

# ── NEW: Calculate Consumer & Outstanding Totals ────────────────────────────
total_consumers = int(df["consumers"].sum()) if "consumers" in df.columns else 0
total_billed = int(df["billed_consumers"].sum()) if "billed_consumers" in df.columns else 0
total_paid = int(df["paid_consumers"].sum()) if "paid_consumers" in df.columns else 0
total_smart = int(df["smart_meter_consumers"].sum()) if "smart_meter_consumers" in df.columns else 0
total_outstanding = float(df["total_outstanding_amount"].sum()) if "total_outstanding_amount" in df.columns else 0.0


be_gt = total_sold / total_input if total_input > 0 else 0
ce_gt = total_revenue / total_assessment if total_assessment > 0 else 0

gt = {
    "atc_loss_pct": round((1 - be_gt * ce_gt) * 100, 2),
    "billing_efficiency_pct": round(be_gt * 100, 2),
    "collection_efficiency_pct": round(ce_gt * 100, 2),
    "line_loss_pct": round(((total_input - total_sold) / total_input * 100), 2) if total_input > 0 else 0,
    "input_energy_kwh": total_input, "sold_energy_kwh": total_sold,
    "net_assessment": total_assessment, "revenue_realized": total_revenue,

     # ── NEW KEYS ADDED HERE ─────────────────────────────────────────────────
    "consumers": total_consumers,
    "billed_consumers": total_billed,
    "paid_consumers": total_paid,
    "smart_meter_consumers": total_smart,
    "total_outstanding_amount": total_outstanding
}



# ── 3. GLOBAL DATA CLEANUP & SORT ────────────────────────────────────────────
numeric_cols = ["input_energy_kwh", "sold_energy_kwh", "line_loss_pct", "billing_efficiency_pct",
                "collection_efficiency_pct", "atc_loss_pct", "net_assessment", "revenue_realized",
                "abr_rs_per_kwh", "avg_collection_rate", "realization_rate", "consumers",
                "billed_consumers", "paid_consumers"]

for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

if "input_energy_kwh" in df.columns:
    df["plot_size_input"] = df["input_energy_kwh"].fillna(1).abs().clip(lower=1)
if "net_assessment" in df.columns:
    df["plot_size_assessment"] = df["net_assessment"].fillna(1).abs().clip(lower=1)

if "outgoing_feeder" in df.columns:
    df = df[df["outgoing_feeder"].notna()].reset_index(drop=True)

if sort_col in df.columns:
    df = df.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

# ── HEADER ───────────────────────────────────────────────────────────────────
# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dvvnl-header">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
    <div class="dvvnl-title">⚡ Feeder-wise AT&amp;C Loss Dashboard</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── HORIZONTAL FILTER BAR (below header, full width) ─────────────────────────
# ── HORIZONTAL FILTER BAR (below header, full width) ─────────────────────────
# ── HORIZONTAL FILTER BAR (below header, full width) ─────────────────────────
# Load base data for filter options once
@st.cache_data(ttl=3600, show_spinner=False)
def get_filter_options():
    """Get unique filter options from full dataset"""
    try:
        result = get_processed_data(str(month_start), str(month_end), "All Zones", "All Circles", "All Types")
        df_full = result['df']
        
        zones_list = sorted(df_full['zone'].dropna().unique().tolist()) if 'zone' in df_full.columns else []
        
        # Create dictionaries for cascading filters
        zone_to_circles = {}
        circle_to_divisions = {}
        
        if 'zone' in df_full.columns and 'circle' in df_full.columns:
            for zone in zones_list:
                circles = df_full[df_full['zone'] == zone]['circle'].dropna().unique().tolist()
                zone_to_circles[zone] = sorted(circles)
        
        if 'circle' in df_full.columns and 'division' in df_full.columns:
            circles_list_all = sorted(df_full['circle'].dropna().unique().tolist())
            for circle in circles_list_all:
                divisions = df_full[df_full['circle'] == circle]['division'].dropna().unique().tolist()
                circle_to_divisions[circle] = sorted(divisions)
        
        return zones_list, zone_to_circles, circle_to_divisions, df_full
    except Exception as e:
        st.error(f"Error loading filter options: {e}")
        return [], {}, {}, pd.DataFrame()

# Load filter options
zones_list, zone_to_circles, circle_to_divisions, df_full = get_filter_options()

# Initialize session state for filters if not exists
if 'filter_zone' not in st.session_state:
    st.session_state.filter_zone = "All Zones"
if 'filter_circle' not in st.session_state:
    st.session_state.filter_circle = "All Circles"
if 'filter_division' not in st.session_state:
    st.session_state.filter_division = "All Divisions"

# ── FILTER BAR WITH CASCADING ────────────────────────────────────────────────
with st.container():
    fc1, fc2, fc3, fc4, fc5, fc6, fc7 = st.columns([2,2,2,2,2,1,5])

    with fc1:
        # Zone filter - when changed, reset circle and division
        new_zone = st.selectbox(
            "🗺️ Zone", 
            ["All Zones"] + zones_list, 
            index=0 if st.session_state.filter_zone == "All Zones" else zones_list.index(st.session_state.filter_zone) if st.session_state.filter_zone in zones_list else 0,
            key="fb_zone"
        )
        
        # Reset circle and division if zone changed
        if new_zone != st.session_state.filter_zone:
            st.session_state.filter_zone = new_zone
            st.session_state.filter_circle = "All Circles"
            st.session_state.filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.filter_zone = new_zone

    # Get available circles based on selected zone
    if st.session_state.filter_zone != "All Zones":
        available_circles = zone_to_circles.get(st.session_state.filter_zone, [])
    else:
        # Get all unique circles from full data
        available_circles = sorted(df_full['circle'].dropna().unique().tolist()) if 'circle' in df_full.columns else []
    
    with fc2:
        new_circle = st.selectbox(
            "🏙️ Circle", 
            ["All Circles"] + available_circles,
            index=0 if st.session_state.filter_circle == "All Circles" else (available_circles.index(st.session_state.filter_circle) + 1 if st.session_state.filter_circle in available_circles else 0),
            key="fb_circle"
        )
        
        # Reset division if circle changed
        if new_circle != st.session_state.filter_circle:
            st.session_state.filter_circle = new_circle
            st.session_state.filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.filter_circle = new_circle

    # Get available divisions based on selected circle
    if st.session_state.filter_circle != "All Circles":
        available_divisions = circle_to_divisions.get(st.session_state.filter_circle, [])
    elif st.session_state.filter_zone != "All Zones":
        # Get all divisions in selected zone
        df_zone = df_full[df_full['zone'] == st.session_state.filter_zone] if st.session_state.filter_zone != "All Zones" else df_full
        available_divisions = sorted(df_zone['division'].dropna().unique().tolist()) if 'division' in df_zone.columns else []
    else:
        available_divisions = sorted(df_full['division'].dropna().unique().tolist()) if 'division' in df_full.columns else []
    
    with fc3:
        new_division = st.selectbox(
            "🏢 Division", 
            ["All Divisions"] + available_divisions,
            index=0 if st.session_state.filter_division == "All Divisions" else (available_divisions.index(st.session_state.filter_division) + 1 if st.session_state.filter_division in available_divisions else 0),
            key="fb_div"
        )
        st.session_state.filter_division = new_division

    # Sort options
    _sort_opts = {
        "AT&C %": "atc_loss_pct",
        "Billing %": "billing_efficiency_pct",
        "Coll %": "collection_efficiency_pct",
        "Line Loss": "line_loss_pct",
        "Input KWH": "input_energy_kwh",
        "Revenue": "revenue_realized",
    }
    
    with fc4:
        sort_col_label = st.selectbox("📊 Sort By", list(_sort_opts.keys()), key="fb_sort")
    sort_col = _sort_opts[sort_col_label]

    with fc5:
        sort_asc = st.toggle("⬆️ Asc", False, key="fb_asc")

    with fc6:
        if st.button("🔄", key="fb_refresh", help="Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    with fc7:
        agri_filter = st.selectbox("🌾 FEEDER Nature ", ["All","Agriculture","Non-Agriculture"], key="agri_filter_unique_key")

# Use the session state filters
zone_sel = st.session_state.filter_zone
circle_sel = st.session_state.filter_circle
division_sel = st.session_state.filter_division

result       = get_processed_data(str(month_start), str(month_end), zone_sel, circle_sel, nature_sel)
df           = result['df'].copy()
unmatched_df = result.get('unmatched_df', pd.DataFrame())    

# ── AFTER FILTER BAR, BEFORE "Overall Summary" ──────────────────────────────
# Build dynamic header based on selected filters
def build_hierarchy_header(zone_sel, circle_sel, division_sel):
    """Build a descriptive header showing current filter hierarchy"""
    hierarchy_parts = []
    
    if zone_sel != "All Zones":
        hierarchy_parts.append(f"🗺️ {zone_sel}")
    if circle_sel != "All Circles":
        hierarchy_parts.append(f"🏙️ {circle_sel}")
    if division_sel != "All Divisions":
        hierarchy_parts.append(f"🏢 {division_sel}")
    
    if hierarchy_parts:
        return " → ".join(hierarchy_parts)
    else:
        return "📊 DVVNL (All Units)"

# Get current selection display
current_hierarchy = build_hierarchy_header(zone_sel, circle_sel, division_sel)

# Display dynamic header
# st.markdown(f"""
# <div style="
#     background: linear-gradient(135deg, #1e3a5f 0%, #2c5f8a 50%, #1e3a5f 100%);
#     border-radius: 14px;
#     padding: 10px 20px;
#     margin: 10px 0 15px 0;
#     text-align: center;
#     box-shadow: 0 4px 12px rgba(0,0,0,0.15);
# ">
#     <div style="display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap;">
#         <span style="font-size: 20px;">📍</span>
#         <span style="color: #ffffff; font-size: 16px; font-weight: 600; letter-spacing: 0.5px;">
#             VIEWING:
#         </span>
#         <span style="
#                 background: rgba(255,255,255,0.2);
#                 padding: 5px 16px;
#                 border-radius: 20px;
#                 color: #fbbf24;
#                 font-size: 16px;
#                 font-weight: 800;
#                 font-family: 'JetBrains Mono', monospace;
#             ">
#             {current_hierarchy}
#         </span>
#         <span style="color: #93c5fd; font-size: 13px;">
#             ({len(df)} Feeders)
#         </span>
#     </div>
# </div>
# """, unsafe_allow_html=True)

# ── GRAND KPIs ────────────────────────────────────────────────────────────────
st.markdown(f'''
            <div class="section-title">
            Viewing: {current_hierarchy} — Overall Summary
            <span style="color: #ffffff; font-size: 13px;">({len(df)} Feeders)</span>
            </div>
        ''', unsafe_allow_html=True)

# ── APPLY FILTER & RECALCULATE ALL AGGREGATES ────────────────────────────────
# 1. Filter the main dataframe
if agri_filter == "Agriculture":
    df = df[df["feeder_nature"].str.contains("Agri", case=False, na=False)].reset_index(drop=True)
elif agri_filter == "Non-Agriculture":
    df = df[~df["feeder_nature"].str.contains("Agri", case=False, na=True)].reset_index(drop=True)

# 2. Recalculate Grand Totals (gt)
total_input = float(df["input_energy_kwh"].sum())
total_sold = float(df["sold_energy_kwh"].sum())
total_assessment = float(df["net_assessment"].sum())
total_revenue = float(df["revenue_realized"].sum())

# ── NEW: Calculate Consumer & Outstanding Totals ────────────────────────────
total_consumers = int(df["consumers"].sum()) if "consumers" in df.columns else 0
total_billed = int(df["billed_consumers"].sum()) if "billed_consumers" in df.columns else 0
total_paid = int(df["paid_consumers"].sum()) if "paid_consumers" in df.columns else 0
total_smart = int(df["smart_meter_consumers"].sum()) if "smart_meter_consumers" in df.columns else 0
total_outstanding = float(df["total_outstanding_amount"].sum()) if "total_outstanding_amount" in df.columns else 0.0

billing_eff_pct = (total_sold / total_input * 100) if total_input > 0 else 0
coll_eff_pct = (total_revenue / total_assessment * 100) if total_assessment > 0 else 0
atc_loss_pct = 100 - (billing_eff_pct * coll_eff_pct / 100)  # Standard AT&C formula
line_loss_pct = ((total_input - total_sold) / total_input * 100) if total_input > 0 else 0

gt = {
    "atc_loss_pct": atc_loss_pct,
    "billing_efficiency_pct": billing_eff_pct,
    "collection_efficiency_pct": coll_eff_pct,
    "line_loss_pct": line_loss_pct,
    "input_energy_kwh": total_input,
    "sold_energy_kwh": total_sold,
    "net_assessment": total_assessment,
    "revenue_realized": total_revenue,

     # ── NEW KEYS ADDED HERE ─────────────────────────────────────────────────
    "consumers": total_consumers,
    "billed_consumers": total_billed,
    "paid_consumers": total_paid,
    "smart_meter_consumers": total_smart,
    "total_outstanding_amount": total_outstanding
}

# 3. Recalculate zone_df
if not df.empty:
    zone_agg = df.groupby("zone").agg(
        feeder_count=("outgoing_feeder", "count"),
        total_input=("input_energy_kwh", "sum"),
        total_sold=("sold_energy_kwh", "sum"),
        total_assessment=("net_assessment", "sum"),
        total_revenue=("revenue_realized", "sum")
    ).reset_index()
    zone_agg["line_loss_pct"] = ((zone_agg["total_input"] - zone_agg["total_sold"]) / zone_agg["total_input"] * 100).fillna(0)
    zone_agg["billing_efficiency_pct"] = (zone_agg["total_sold"] / zone_agg["total_input"] * 100).fillna(0)
    zone_agg["collection_efficiency_pct"] = (zone_agg["total_revenue"] / zone_agg["total_assessment"] * 100).fillna(0)
    zone_agg["atc_loss_pct"] = 100 - (zone_agg["billing_efficiency_pct"] * zone_agg["collection_efficiency_pct"] / 100)
    zone_df = zone_agg
else:
    zone_df = pd.DataFrame()

# 4. Recalculate circ_df
if not df.empty:
    circ_agg = df.groupby(["circle", "zone"]).agg(
        feeder_count=("outgoing_feeder", "count"),
        total_input=("input_energy_kwh", "sum"),
        total_sold=("sold_energy_kwh", "sum"),
        total_assessment=("net_assessment", "sum"),
        total_revenue=("revenue_realized", "sum")
    ).reset_index()
    circ_agg["line_loss_pct"] = ((circ_agg["total_input"] - circ_agg["total_sold"]) / circ_agg["total_input"] * 100).fillna(0)
    circ_agg["billing_efficiency_pct"] = (circ_agg["total_sold"] / circ_agg["total_input"] * 100).fillna(0)
    circ_agg["collection_efficiency_pct"] = (circ_agg["total_revenue"] / circ_agg["total_assessment"] * 100).fillna(0)
    circ_agg["atc_loss_pct"] = 100 - (circ_agg["billing_efficiency_pct"] * circ_agg["collection_efficiency_pct"] / 100)
    circ_df = circ_agg
else:
    circ_df = pd.DataFrame()

# 5. Recalculate nat_df
if not df.empty:
    nat_df = df.groupby("feeder_nature").agg(feeder_count=("outgoing_feeder", "count")).reset_index()
else:
    nat_df = pd.DataFrame()

# 6. Recalculate hist_df (Histogram data)
if not df.empty and "atc_loss_pct" in df.columns:
    bins = [0, 10, 20, 30, 40, 50, 100]
    labels = ["0-10%", "10-20%", "20-30%", "30-40%", "40-50%", ">50%"]
    hist_counts = pd.cut(df["atc_loss_pct"], bins=bins, labels=labels, include_lowest=True).value_counts().reindex(labels, fill_value=0)
    hist_df = pd.DataFrame({"AT&C Loss Range": labels, "Feeder Count": hist_counts.values})
else:
    hist_df = pd.DataFrame()

# 7. Recalculate funnel_data (Dictionary format expected by charts.py)
if not df.empty:
    funnel_data = {
        "Total Consumers": int(df["consumers"].sum()) if "consumers" in df.columns else 0,
        "Billed Consumers": int(df["billed_consumers"].sum()) if "billed_consumers" in df.columns else 0,
        "Paid Consumers": int(df["paid_consumers"].sum()) if "paid_consumers" in df.columns else 0
    }
else:
    funnel_data = {}

# ── RENDER KPI CARDS (Now reflects the filtered data) ────────────────────────
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
for col, lbl, val, unit, color, sub in [
    (c1, "Feeders",           f"{len(df):,}",                          "",   "#2563eb", "Count"),
    (c2, "AT&C Loss",         f"{gt.get('atc_loss_pct',0):.1f}",       "%",  atc_color(gt.get('atc_loss_pct',0)), "Target<15%"),
    (c3, "Billing Eff",       f"{gt.get('billing_efficiency_pct',0):.1f}", "%", "#18492a", "Sold/Input"),
    (c4, "Coll. Eff",         f"{gt.get('collection_efficiency_pct',0):.1f}", "%", "#1b3e77", "Rev/Ass"),
    (c5, "Line Loss",         f"{gt.get('line_loss_pct',0):.1f}",       "%",  "#65330E", "Technical"),
    (c6, "Input Energy",      fmt_lakh(gt.get('input_energy_kwh',0)),   "KWH", "#232e92", "Total Fed"),
    (c7, "Units Sold",        fmt_lakh(gt.get('sold_energy_kwh',0)),    "KWH", "#0A704B", "Billed"),
    
    ]:
    with col:
            kpi_card(lbl, f"{val}", unit, color=color, sub=sub)

e1,e2,e3,e4,e5,e6,e7 = st.columns(7)
for col,lbl,val,color,sub in [
        (e1, "Assessment",        fmt_lakh(gt.get('net_assessment',0)),   "#8a6915", "CA Apr"),
        (e2, "Revenue",           fmt_lakh(gt.get('revenue_realized',0)),  "#0d7c8f", "Paid"),
        (e3,"Consumers",     fmt_lakh(gt.get('consumers',0)),           "#1215a3","Operative"),
        (e4,"Billed",        fmt_lakh(gt.get('billed_consumers',0)),    "#0c6343","April"),    
        (e5,"Paid",          fmt_lakh(gt.get('paid_consumers',0)),      "#06525f","April"),
        (e6,"Smart Meters",  fmt_lakh(gt.get('smart_meter_consumers',0)),"#36118C","Smart"),
        (e7,"Outstanding",   fmt_lakh(gt.get('total_outstanding_amount',0)),  "#7e0d0d","Arrears ₹"),
    ]:
        with col: kpi_card(lbl, val, "", color=color, sub=sub)

# ── CRITICAL ALERTS ──────────────────────────────────────────────────────────
# (Rest of your code continues normally from here...)
# ── CRITICAL ALERTS ──────────────────────────────────────────────────────────
if "atc_loss_pct" in df.columns:
    critical = df[df["atc_loss_pct"] >= KPI_THRESHOLDS["atc_high"]]
    st.markdown(f"🔴 {len(critical)} CRITICAL Feeders (AT&C ≥ {KPI_THRESHOLDS['atc_high']}%)")

# ── TABS ─────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Overview", "🔴 AT&C Deep Dive", "⚡ Energy Analysis",
    "💰 Revenue & Collection", "🏆 Feeder Rankings", "🗺️ Zone Comparison",
    "🌳 Treemap",
    "📋 Data & Export",
    "📐 Slab Analysis"
])

# ══ TAB 1: OVERVIEW ══════════════════════════════════════════════════════════

with tabs[0]:
    
    # Zone-wise ATC Comparison Chart
    st.markdown("### 📊 Zone-wise ATC Comparison")
    if not zone_df.empty and 'zone' in zone_df.columns:
        fig2 = go.Figure()
        for col_n, name, color in [("atc_loss_pct","AT&C %","#ef4444"),("billing_efficiency_pct","Billing Eff %","#22c55e"),("collection_efficiency_pct","Coll Eff %","#3b82f6")]:
            if col_n in zone_df.columns:
                fig2.add_trace(go.Bar(name=name, x=zone_df["zone"], 
                                      y=zone_df[col_n], marker_color=color, text=zone_df[col_n].round(2),
                                      textposition="outside"))
        if len(fig2.data) > 0:
            fig2.update_traces(textposition="outside")
            fig2.update_layout(**dark_layout(barmode="group", height=450))
            st.plotly_chart(fig2, width='stretch', key="tab2_atc_bar", config=PLOTLY_CONFIG)
        else:
            st.info("No zone data available for the current selection")
    else:
        st.info("Zone-wise data not available")
        # Additional statistics cards
    st.markdown("### 📊 Quick Statistics")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        total_zones = df['zone'].nunique() if 'zone' in df.columns else 0
        st.metric("🏢 Total Zones", f"{total_zones:,}")
    
    with stat_col2:
        total_circles = df['circle'].nunique() if 'circle' in df.columns else 0
        st.metric("🏙️ Total Circles", f"{total_circles:,}")
    
    with stat_col3:
        total_divisions = df['division'].nunique() if 'division' in df.columns else 0
        st.metric("🏢 Total Divisions", f"{total_divisions:,}")
    
    with stat_col4:
        total_substations = df['substation'].nunique() if 'substation' in df.columns else 0
        st.metric("🏗️ Total Substations", f"{total_substations:,}")

    # Feeders by Nature Pie Chart
# Feeders by Nature Pie Chart
   
    st.markdown("### 🥧 Feeders by Nature")
    
    total_feeders = nat_df['feeder_count'].sum()
    
    # Create custom labels with count and percentage - bold formatting
    custom_labels = [
        f"<b>{row['feeder_nature']}</b><br><b>{row['feeder_count']:,}</b> <b>({row['feeder_count']/total_feeders*100:.1f}%)</b>"
        for _, row in nat_df.iterrows()
    ]
    
    fig4 = go.Figure(data=[
        go.Pie(
            labels=custom_labels,
            values=nat_df['feeder_count'],
            hole=0.4,
            textposition='outside',
            textfont=dict(size=14, color='#0f172a', weight='bold', family='Arial Black, sans-serif'),
            marker=dict(line=dict(color='#ffffff', width=3)),
            hovertemplate='<b>%{label}</b><br>Feeders: %{value:,.0f}<br>Percentage: %{percent}<extra></extra>',
            insidetextorientation='radial',
            showlegend=True,
            legendgroup='groups',
            legendgrouptitle=dict(text='<b>Feeder Nature Types</b>', font=dict(size=14, weight='bold'))
        )
    ])
    
    # Add center annotation with total - bold and larger
    fig4.add_annotation(
        text=f"<b>TOTAL</b><br><b style='font-size:22px'>{total_feeders:,}</b><br><b>FEEDERS</b>",
        x=0.5, y=0.5,
        font_size=16,
        font_color="#0f172a",
        showarrow=False,
        align="center",
        bordercolor="#457a9f",
        borderwidth=2,
        borderpad=10,
        bgcolor="rgba(255,255,255,0.9)"
    )
    
    # Apply dark_layout
    fig4.update_layout(**dark_layout())
    
    # Update legend with wider spacing and larger font
    fig4.update_layout(
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.05,
            bgcolor="rgba(238, 242, 255, 0.95)",
            bordercolor="#457a9f",
            borderwidth=2,
            font=dict(size=13, color="#0f172a", weight="bold"),
            title=dict(
                text="<b>📊 FEEDER NATURE TYPES</b>",
                font=dict(size=14, color="#0f172a", weight="bold")
            ),
            itemclick="toggle",
            itemdoubleclick="toggleothers",
            tracegroupgap=8,
            itemsizing="constant"
        ),
        margin=dict(l=40, r=250, t=60, b=40),
        height=600,
        width=None
    )
    
    # Make the chart container wider
    st.plotly_chart(fig4, use_container_width=True, key="tab4_feeder_bar", config=PLOTLY_CONFIG)
    
    # Display summary metrics with larger font
    st.markdown("### 📊 Summary Statistics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Feeders", f"{total_feeders:,}", help="Total number of feeders across all nature types")
    with col2:
        st.metric("🏷️ Nature Types", f"{len(nat_df)}", help="Number of distinct feeder nature categories")
    with col3:
        most_common = nat_df.loc[nat_df['feeder_count'].idxmax()] if not nat_df.empty else None
        if most_common is not None:
            st.metric(
                "⭐ Most Common", 
                f"{most_common['feeder_nature']}", 
                f"{most_common['feeder_count']:,} feeders ({most_common['feeder_count']/total_feeders*100:.1f}%)"
            )
    
    # ── HIERARCHY SUMMARY TABLE ──────────────────────────────────────────────
    st.markdown("### 📋 Hierarchy Summary - Zone | Circle | Division Details")
    st.markdown("---")
    
    # Safely create hierarchy summary
    if not df.empty and 'zone' in df.columns and 'circle' in df.columns:
        
        # Prepare data for hierarchy table
        hierarchy_data = []
        
        # Get unique combinations
        if 'division' in df.columns:
            grouped = df.groupby(['zone', 'circle', 'division'], dropna=False)
        else:
            grouped = df.groupby(['zone', 'circle'], dropna=False)
        
        for keys, group in grouped:
            if 'division' in df.columns:
                zone_val, circle_val, division_val = keys
            else:
                zone_val, circle_val = keys
                division_val = None
            
            # Count feeders
            feeder_count = len(group)
            
            # Count substations if available
            substation_count = group['substation'].nunique() if 'substation' in df.columns else 0
            
            # Get feeder types breakdown
            feeder_types = {}
            if 'feeder_nature' in df.columns:
                feeder_types = group['feeder_nature'].value_counts().to_dict()
            
            # Format feeder types string
            feeder_types_str = " | ".join([f"{k}: {v}" for k, v in feeder_types.items()]) if feeder_types else "—"
            
            row = {
                'Zone': str(zone_val) if pd.notna(zone_val) else "Unknown",
                'Circle': str(circle_val) if pd.notna(circle_val) else "Unknown",
                'No. of Feeders': feeder_count,
                'Feeder Types': feeder_types_str
            }
            
            if 'division' in df.columns:
                row['Division'] = str(division_val) if pd.notna(division_val) else "Unknown"
            
            if 'substation' in df.columns:
                row['No. of Substations'] = substation_count
            
            hierarchy_data.append(row)
        
        if hierarchy_data:
            hierarchy_df = pd.DataFrame(hierarchy_data)
            
            # Reorder columns
            if 'division' in df.columns:
                col_order = ['Zone', 'Circle', 'Division', 'No. of Feeders']
                if 'substation' in df.columns:
                    col_order.append('No. of Substations')
                col_order.append('Feeder Types')
            else:
                col_order = ['Zone', 'Circle', 'No. of Feeders']
                if 'substation' in df.columns:
                    col_order.append('No. of Substations')
                col_order.append('Feeder Types')
            
            hierarchy_df = hierarchy_df[col_order]
            
            # Sort
            hierarchy_df = hierarchy_df.sort_values(['Zone', 'Circle']).reset_index(drop=True)
            hierarchy_df.insert(0, '#', range(1, len(hierarchy_df) + 1))
            
            # Style and display
            styled_hierarchy = hierarchy_df.style.set_properties(**{
                'font-weight': 'bold',
                'text-align': 'left'
            }).set_table_styles([
                {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]},
                {'selector': 'td', 'props': [('padding', '8px'), ('border-bottom', '1px solid #c7d2fe')]}
            ])
            
            st.dataframe(styled_hierarchy, use_container_width=True, hide_index=True)
            
            # Download button
            csv_hierarchy = hierarchy_df.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Hierarchy Summary (CSV)",
                data=csv_hierarchy,
                file_name=f"DVVNL_Hierarchy_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No hierarchy data available for the current selection")
    else:
        st.info("Hierarchy data not available (missing zone or circle columns)")
    
    # Expanded detailed view
    with st.expander("🔍 View Detailed Breakdown by Zone/Circle/Division", expanded=False):
        if 'zone' in df.columns and 'circle' in df.columns:
            
            # Zone-wise summary
            st.markdown("#### 📍 Zone-wise Summary")
            try:
                zone_summary = df.groupby('zone').size().reset_index(name='No. of Feeders')
                
                if 'substation' in df.columns:
                    zone_substation = df.groupby('zone')['substation'].nunique().reset_index(name='No. of Substations')
                    zone_summary = zone_summary.merge(zone_substation, on='zone', how='left')
                
                zone_summary['% of Total Feeders'] = (zone_summary['No. of Feeders'] / len(df) * 100).round(1).astype(str) + '%'
                st.dataframe(zone_summary, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Could not create zone summary: {e}")
                        
        else:
            st.info("Zone or Circle columns not available for detailed breakdown")


# ══ TAB 2: AT&C DEEP DIVE ═════════════════════════════════════════════════════

with tabs[1]:

    st.markdown('<div class="section-title">📊 Slab-wise AT&C Loss Analysis - Zone | Circle | Division</div>',
                unsafe_allow_html=True)
    
    # Slab definitions - Updated as requested
    slab_definitions = [
        {"name": "Excellent (<15%)", "min": -float('inf'), "max": 15, "color": "#22c55e", "icon": "✅"},
        {"name": "Good (15-30%)", "min": 15, "max": 30, "color": "#84cc16", "icon": "🟢"},
        {"name": "High (30-50%)", "min": 30, "max": 50, "color": "#eab308", "icon": "⚠️"},
        {"name": "Critical (50-75%)", "min": 50, "max": 75, "color": "#f97316", "icon": "🔴"},
        {"name": "Severe (≥75%)", "min": 75, "max": float('inf'), "color": "#ef4444", "icon": "💀"}
    ]
    
    # Function to classify AT&C into slab - No unknown category
    def get_slab(atc_value):
        if pd.isna(atc_value):
            # Assign to Excellent if no value (assume good performance)
            return "Excellent (<15%)"
        for slab in slab_definitions:
            if slab["min"] <= atc_value < slab["max"]:
                return slab["name"]
        return "Excellent (<15%)"  # Default fallback
    
    # Create slab column
    df['slab'] = df['atc_loss_pct'].apply(get_slab)
    
    # Layout: Side by side selection
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown("#### 🗺️ Zone-wise Analysis")
        show_zone = st.checkbox("Show Zone-wise Summary", value=True, key="show_zone_slab")
    
    with col2:
        st.markdown("#### 🏙️ Circle-wise Analysis")
        show_circle = st.checkbox("Show Circle-wise Summary", value=True, key="show_circle_slab")
    
    with col3:
        st.markdown("#### 🏢 Division-wise Analysis")
        show_division = st.checkbox("Show Division-wise Summary", value=True, key="show_division_slab")
    
    st.markdown("---")
    
    # ── 1. ZONE-WISE SLAB SUMMARY ──────────────────────────────────────────────
    if show_zone and 'zone' in df.columns:
        st.markdown("### 🗺️ Zone-wise Slab Distribution")
        
        # Create zone-wise slab summary (counts only, no percentages initially)
        zone_slab_summary = df.groupby(['zone', 'slab']).size().unstack(fill_value=0).reset_index()
        
        # Calculate total feeders per zone
        zone_totals = df.groupby('zone').size().reset_index(name='Total Feeders')
        
        # Merge all data
        zone_summary = zone_totals.merge(zone_slab_summary, on='zone', how='left')
        
        # Fill any missing slab columns with 0
        for slab in slab_definitions:
            if slab["name"] not in zone_summary.columns:
                zone_summary[slab["name"]] = 0
        
        # Calculate percentages for each slab
        for slab in slab_definitions:
            slab_name = slab["name"]
            zone_summary[f'{slab_name} %'] = (zone_summary[slab_name] / zone_summary['Total Feeders'] * 100).round(1)
        
        # Reorder columns - NO AVG AT&C column
        cols = ['zone', 'Total Feeders']
        for slab in slab_definitions:
            cols.append(slab["name"])
            cols.append(f'{slab["name"]} %')
        
        zone_summary = zone_summary[[c for c in cols if c in zone_summary.columns]]
        
        # Sort by Total Feeders (descending)
        zone_summary = zone_summary.sort_values('Total Feeders', ascending=False)
        
        # Display with styling
        st.dataframe(
            zone_summary.style
            .format({
                'Total Feeders': '{:,.0f}',
                **{slab["name"]: '{:,.0f}' for slab in slab_definitions},
                **{f'{slab["name"]} %': '{:.1f}%' for slab in slab_definitions}
            })
            .set_properties(**{'font-weight': 'bold'})
            .set_table_styles([
                {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
            ]),
            use_container_width=True,
            hide_index=True
        )
        
        # Download button for zone summary
        csv_zone = zone_summary.to_csv(index=False).encode()
        st.download_button(
            label="📥 Download Zone-wise Slab Summary (CSV)",
            data=csv_zone,
            file_name=f"DVVNL_Zone_Slab_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("---")
    
    # ── 2. CIRCLE-WISE SLAB SUMMARY ────────────────────────────────────────────
    if show_circle and 'circle' in df.columns and 'zone' in df.columns:
        st.markdown("### 🏙️ Circle-wise Slab Distribution ")
        
        # Create circle-wise slab summary
        circle_slab_summary = df.groupby(['zone', 'circle', 'slab']).size().unstack(fill_value=0).reset_index()
        
        # Calculate total feeders per circle
        circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Feeders')
        
        # Merge all data
        circle_summary = circle_totals.merge(circle_slab_summary, on=['zone', 'circle'], how='left')
        
        # Fill any missing slab columns with 0
        for slab in slab_definitions:
            if slab["name"] not in circle_summary.columns:
                circle_summary[slab["name"]] = 0
        
        # Calculate percentages for each slab
        for slab in slab_definitions:
            slab_name = slab["name"]
            circle_summary[f'{slab_name} %'] = (circle_summary[slab_name] / circle_summary['Total Feeders'] * 100).round(1)
        
        # Reorder columns - NO AVG AT&C column
        cols = ['zone', 'circle', 'Total Feeders']
        for slab in slab_definitions:
            cols.append(slab["name"])
            cols.append(f'{slab["name"]} %')
        
        circle_summary = circle_summary[[c for c in cols if c in circle_summary.columns]]
        
        # Sort by Total Feeders (descending) and show top 20
        circle_summary = circle_summary.sort_values('Total Feeders', ascending=False)
        
        # Display with styling
        st.dataframe(
            circle_summary.style
            .format({
                'Total Feeders': '{:,.0f}',
                **{slab["name"]: '{:,.0f}' for slab in slab_definitions},
                **{f'{slab["name"]} %': '{:.1f}%' for slab in slab_definitions}
            })
            .set_properties(**{'font-weight': 'bold'})
            .set_table_styles([
                {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
            ]),
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Showing Circles by feeder count. Total circles: {circle_summary['circle'].nunique() if not circle_summary.empty else 0}")
        
        # Download button for circle summary
        csv_circle = circle_summary.to_csv(index=False).encode()
        st.download_button(
            label="📥 Download Circle-wise Slab Summary (CSV)",
            data=csv_circle,
            file_name=f"DVVNL_Circle_Slab_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("---")
    
    # ── 3. DIVISION-WISE SLAB SUMMARY ──────────────────────────────────────────
    if show_division and 'division' in df.columns and 'circle' in df.columns:
        st.markdown("### 🏢 Division-wise Slab Distribution (Feeders)")
        
        # Create division-wise slab summary
        div_slab_summary = df.groupby(['zone', 'circle', 'division', 'slab']).size().unstack(fill_value=0).reset_index()
        
        # Calculate total feeders per division
        div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Feeders')
        
        # Merge all data
        div_summary = div_totals.merge(div_slab_summary, on=['zone', 'circle', 'division'], how='left')
        
        # Fill any missing slab columns with 0
        for slab in slab_definitions:
            if slab["name"] not in div_summary.columns:
                div_summary[slab["name"]] = 0
        
        # Calculate percentages for each slab
        for slab in slab_definitions:
            slab_name = slab["name"]
            div_summary[f'{slab_name} %'] = (div_summary[slab_name] / div_summary['Total Feeders'] * 100).round(1)
        
        # Reorder columns - NO AVG AT&C column
        cols = ['zone', 'circle', 'division', 'Total Feeders']
        for slab in slab_definitions:
            cols.append(slab["name"])
            cols.append(f'{slab["name"]} %')
        
        div_summary = div_summary[[c for c in cols if c in div_summary.columns]]
        
        # Sort by Total Feeders (descending) and show top 30
        div_summary = div_summary.sort_values('Total Feeders', ascending=False)
        
        # Display with styling
        st.dataframe(
            div_summary.style
            .format({
                'Total Feeders': '{:,.0f}',
                **{slab["name"]: '{:,.0f}' for slab in slab_definitions},
                **{f'{slab["name"]} %': '{:.1f}%' for slab in slab_definitions}
            })
            .set_properties(**{'font-weight': 'bold'})
            .set_table_styles([
                {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
            ]),
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Showing divisions by feeder count. Total divisions: {div_summary['division'].nunique() if not div_summary.empty else 0}")
        
        # Download button for division summary
        csv_division = div_summary.to_csv(index=False).encode()
        st.download_button(
            label="📥 Download Division-wise Slab Summary (CSV)",
            data=csv_division,
            file_name=f"DVVNL_Division_Slab_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("---")
    
    # ── SUMMARY STATISTICS CARDS ───────────────────────────────────────────────
    st.markdown("### 📊 Overall Slab Statistics")
    
    # Calculate overall slab distribution
    slab_counts = df['slab'].value_counts()
    total_feeders = len(df)
    
    # Ensure all slabs are represented
    for slab in slab_definitions:
        if slab["name"] not in slab_counts.index:
            slab_counts[slab["name"]] = 0
    
    # Display slab distribution as metrics
    cols = st.columns(len(slab_definitions))
    for idx, slab in enumerate(slab_definitions):
        if idx < len(cols):
            with cols[idx]:
                count = slab_counts.get(slab["name"], 0)
                percentage = (count / total_feeders * 100) if total_feeders > 0 else 0
                st.metric(
                    label=f"{slab['icon']} {slab['name']}",
                    value=f"{count:,} Feeders",
                    delta=f"{percentage:.1f}% of total",
                    delta_color="normal"
                )
    
    # Additional insights (without AT&C averages)
    st.markdown("---")
    st.markdown("### 📈 Key Insights")
    
    insight_col1, insight_col2, insight_col3 = st.columns(3)
    
    with insight_col1:
        # Zone with most feeders in Excellent category
        if 'zone' in df.columns:
            excellent_zone = df[df['slab'] == "Excellent (<15%)"]['zone'].mode()
            if not excellent_zone.empty:
                excellent_count = df[(df['slab'] == "Excellent (<15%)") & (df['zone'] == excellent_zone.iloc[0])].shape[0]
                st.success(f"✅ **Best Performing Zone:** {excellent_zone.iloc[0]}\n\n{excellent_count} feeders in Excellent slab")
            else:
                st.info("No zone with Excellent performance")
    
    with insight_col2:
        # Zone with most feeders in Severe category
        if 'zone' in df.columns:
            severe_zone = df[df['slab'] == "Severe (≥75%)"]['zone'].mode()
            if not severe_zone.empty:
                severe_count = df[(df['slab'] == "Severe (≥75%)") & (df['zone'] == severe_zone.iloc[0])].shape[0]
                st.warning(f"⚠️ **Needs Improvement:** {severe_zone.iloc[0]}\n\n{severe_count} feeders in Severe slab")
            else:
                st.info("No zone with Severe performance")
    
    with insight_col3:
        # Most common slab overall
        most_common_slab = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
        most_common_count = slab_counts.max() if not slab_counts.empty else 0
        st.info(f"📊 **Most Common Slab:** {most_common_slab}\n\n{most_common_count:,} Feeders ({most_common_count/total_feeders*100:.1f}%)")

# ══ TAB 3: ENERGY ════════════════════════════════════════════════════════════
with tabs[2]:

    st.markdown('<div class="section-title">📉 Slab-wise Line Loss Analysis - Zone | Circle | Division</div>',
                unsafe_allow_html=True)
    
    # Line Loss Slab definitions - FIXED for negative and >100 values
    line_loss_slabs = [
        {"name": "Excellent (<10%)", "min": -float('inf'), "max": 10, "color": "#22c55e", "icon": "✅"},
        {"name": "Good (10-15%)", "min": 10, "max": 15, "color": "#84cc16", "icon": "🟢"},
        {"name": "Moderate (15-25%)", "min": 15, "max": 25, "color": "#eab308", "icon": "⚠️"},
        {"name": "High (25-40%)", "min": 25, "max": 40, "color": "#f97316", "icon": "🔴"},
        {"name": "Severe (≥40%)", "min": 40, "max": float('inf'), "color": "#ef4444", "icon": "💀"}
    ]
    
    # Function to classify Line Loss into slab - Handles negative and >100 correctly
    def get_line_loss_slab(ll_value):
        if pd.isna(ll_value):
            return "Excellent (<10%)"  # Default for missing values
        # Ensure numeric value
        try:
            value = float(ll_value)
        except (ValueError, TypeError):
            return "Excellent (<10%)"
        
        # Check each slab
        for slab in line_loss_slabs:
            if slab["min"] <= value < slab["max"]:
                return slab["name"]
        # Fallback - if value is extremely large, it will be caught by Severe (≥40%)
        return "Severe (≥40%)"
    
    # Create line loss slab column - check if column exists
    if 'line_loss_pct' in df.columns:
        df['line_loss_slab'] = df['line_loss_pct'].apply(get_line_loss_slab)
        
        # Layout: Side by side selection
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            st.markdown("#### 🗺️ Zone-wise Analysis")
            show_zone_ll = st.checkbox("Show Zone-wise Summary", value=True, key="show_zone_line_loss")
        
        with col2:
            st.markdown("#### 🏙️ Circle-wise Analysis")
            show_circle_ll = st.checkbox("Show Circle-wise Summary", value=True, key="show_circle_line_loss")
        
        with col3:
            st.markdown("#### 🏢 Division-wise Analysis")
            show_division_ll = st.checkbox("Show Division-wise Summary", value=True, key="show_division_line_loss")
        
        st.markdown("---")
        
        # ── 1. ZONE-WISE LINE LOSS SLAB SUMMARY ─────────────────────────────────
        if show_zone_ll and 'zone' in df.columns:
            st.markdown("### 🗺️ Zone-wise Line Loss Distribution")
            
            # Create zone-wise slab summary
            zone_slab_summary = df.groupby(['zone', 'line_loss_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per zone
            zone_totals = df.groupby('zone').size().reset_index(name='Total Feeders')
            
            # Merge all data
            zone_summary = zone_totals.merge(zone_slab_summary, on='zone', how='left')
            
            # Fill any missing slab columns with 0
            for slab in line_loss_slabs:
                if slab["name"] not in zone_summary.columns:
                    zone_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in line_loss_slabs:
                slab_name = slab["name"]
                zone_summary[f'{slab_name} %'] = (zone_summary[slab_name] / zone_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'Total Feeders']
            for slab in line_loss_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            zone_summary = zone_summary[[c for c in cols if c in zone_summary.columns]]
            
            # Sort by Total Feeders (descending)
            zone_summary = zone_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                zone_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            # Download button for zone summary
            csv_zone = zone_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Zone-wise Line Loss Summary (CSV)",
                data=csv_zone,
                file_name=f"DVVNL_Zone_LineLoss_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── 2. CIRCLE-WISE LINE LOSS SLAB SUMMARY ────────────────────────────────
        if show_circle_ll and 'circle' in df.columns and 'zone' in df.columns:
            st.markdown("### 🏙️ Circle-wise Line Loss Distribution (Top 20 by Feeders)")
            
            # Create circle-wise slab summary
            circle_slab_summary = df.groupby(['zone', 'circle', 'line_loss_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per circle
            circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Feeders')
            
            # Merge all data
            circle_summary = circle_totals.merge(circle_slab_summary, on=['zone', 'circle'], how='left')
            
            # Fill any missing slab columns with 0
            for slab in line_loss_slabs:
                if slab["name"] not in circle_summary.columns:
                    circle_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in line_loss_slabs:
                slab_name = slab["name"]
                circle_summary[f'{slab_name} %'] = (circle_summary[slab_name] / circle_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'circle', 'Total Feeders']
            for slab in line_loss_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            circle_summary = circle_summary[[c for c in cols if c in circle_summary.columns]]
            
            # Sort by Total Feeders (descending) and show top 20
            circle_summary = circle_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                circle_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            st.caption(f"Showing top 20 circles by feeder count. Total circles: {circle_summary['circle'].nunique() if not circle_summary.empty else 0}")
            
            # Download button for circle summary
            csv_circle = circle_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Circle-wise Line Loss Summary (CSV)",
                data=csv_circle,
                file_name=f"DVVNL_Circle_LineLoss_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── 3. DIVISION-WISE LINE LOSS SLAB SUMMARY ──────────────────────────────
        if show_division_ll and 'division' in df.columns and 'circle' in df.columns:
            st.markdown("### 🏢 Division-wise Line Loss Distribution (Top 30 by Feeders)")
            
            # Create division-wise slab summary
            div_slab_summary = df.groupby(['zone', 'circle', 'division', 'line_loss_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per division
            div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Feeders')
            
            # Merge all data
            div_summary = div_totals.merge(div_slab_summary, on=['zone', 'circle', 'division'], how='left')
            
            # Fill any missing slab columns with 0
            for slab in line_loss_slabs:
                if slab["name"] not in div_summary.columns:
                    div_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in line_loss_slabs:
                slab_name = slab["name"]
                div_summary[f'{slab_name} %'] = (div_summary[slab_name] / div_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'circle', 'division', 'Total Feeders']
            for slab in line_loss_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            div_summary = div_summary[[c for c in cols if c in div_summary.columns]]
            
            # Sort by Total Feeders (descending) and show top 30
            div_summary = div_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                div_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            st.caption(f"Showing top 30 divisions by feeder count. Total divisions: {div_summary['division'].nunique() if not div_summary.empty else 0}")
            
            # Download button for division summary
            csv_division = div_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Division-wise Line Loss Summary (CSV)",
                data=csv_division,
                file_name=f"DVVNL_Division_LineLoss_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── SUMMARY STATISTICS CARDS ───────────────────────────────────────────────
        st.markdown("### 📊 Overall Line Loss Statistics")
        
        # Calculate overall slab distribution
        slab_counts = df['line_loss_slab'].value_counts()
        total_feeders = len(df)
        
        # Ensure all slabs are represented
        for slab in line_loss_slabs:
            if slab["name"] not in slab_counts.index:
                slab_counts[slab["name"]] = 0
        
        # Display slab distribution as metrics
        cols = st.columns(len(line_loss_slabs))
        for idx, slab in enumerate(line_loss_slabs):
            if idx < len(cols):
                with cols[idx]:
                    count = slab_counts.get(slab["name"], 0)
                    percentage = (count / total_feeders * 100) if total_feeders > 0 else 0
                    st.metric(
                        label=f"{slab['icon']} {slab['name']}",
                        value=f"{count:,} Feeders",
                        delta=f"{percentage:.1f}% of total",
                        delta_color="normal"
                    )
        
        # Additional insights
        st.markdown("---")
        st.markdown("### 📈 Key Insights")
        
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        
        with insight_col1:
            # Zone with most feeders in Excellent category
            if 'zone' in df.columns:
                excellent_zones = df[df['line_loss_slab'] == "Excellent (<10%)"]['zone'].value_counts()
                if not excellent_zones.empty:
                    best_zone = excellent_zones.index[0]
                    excellent_count = excellent_zones.iloc[0]
                    st.success(f"✅ **Best Zone (Line Loss):** {best_zone}\n\n{excellent_count} feeders with <10% line loss")
                else:
                    st.info("No zone with Excellent line loss performance")
        
        with insight_col2:
            # Zone with most feeders in Severe category
            if 'zone' in df.columns:
                severe_zones = df[df['line_loss_slab'] == "Severe (≥40%)"]['zone'].value_counts()
                if not severe_zones.empty:
                    worst_zone = severe_zones.index[0]
                    severe_count = severe_zones.iloc[0]
                    st.warning(f"⚠️ **Needs Improvement (Line Loss):** {worst_zone}\n\n{severe_count} feeders with ≥40% line loss")
                else:
                    st.info("No zone with Severe line loss performance")
        
        with insight_col3:
            # Most common slab overall
            most_common_slab = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
            most_common_count = slab_counts.max() if not slab_counts.empty else 0
            st.info(f"📊 **Most Common Slab:** {most_common_slab}\n\n{most_common_count:,} Feeders ({most_common_count/total_feeders*100:.1f}%)")
        
        # Technical Note
        st.markdown("---")
        st.markdown("### 💡 Understanding Line Loss")
        st.info("""
        **Line Loss (Technical Loss)** represents the energy lost during transmission and distribution.
        
        **Slab Definitions:**
        - ✅ **Excellent (<10%)** - Optimal performance
        - 🟢 **Good (10-15%)** - Acceptable range
        - ⚠️ **Moderate (15-25%)** - Needs attention
        - 🔴 **High (25-40%)** - Requires immediate action
        - 💀 **Severe (≥40%)** - Critical infrastructure issues
        
        **Note:** Negative line loss values are included in the Excellent category.
        """)
    
    else:
        st.warning("⚠️ Line Loss data (line_loss_pct column) not available in the dataset. Please check your data source.")
# ══ TAB 4: REVENUE ════════════════════════════════════════════════════════════


with tabs[3]:

    if funnel_data:
        st.markdown("**Consumer Billing → Payment**")
        st.plotly_chart(chart_funnel(funnel_data), width='stretch', key="tab8_funnel_chart",config=PLOTLY_CONFIG)

    st.markdown('<div class="section-title">💰 Slab-wise Collection Efficiency Analysis - Zone | Circle | Division</div>',
                unsafe_allow_html=True)
    
    # Collection Efficiency Slab definitions - Fixed for >100 and negative values
    collection_slabs = [
        {"name": "Excellent (≥95%)", "min": 95, "max": float('inf'), "color": "#22c55e", "icon": "✅"},
        {"name": "Good (85-95%)", "min": 85, "max": 95, "color": "#84cc16", "icon": "🟢"},
        {"name": "Moderate (70-85%)", "min": 70, "max": 85, "color": "#eab308", "icon": "⚠️"},
        {"name": "Poor (50-70%)", "min": 50, "max": 70, "color": "#f97316", "icon": "🔴"},
        {"name": "Critical (<50%)", "min": -float('inf'), "max": 50, "color": "#ef4444", "icon": "💀"}
    ]
    
    # Function to classify Collection Efficiency into slab - Handles >100 and negative correctly
    def get_collection_slab(ce_value):
        if pd.isna(ce_value):
            return "Poor (50-70%)"  # Default for missing values
        # Ensure numeric value
        try:
            value = float(ce_value)
        except (ValueError, TypeError):
            return "Poor (50-70%)"
        
        # Check each slab
        for slab in collection_slabs:
            if slab["min"] <= value < slab["max"]:
                return slab["name"]
        # Fallback - if value is extremely high, it will be caught by Excellent (≥95%)
        return "Excellent (≥95%)"
    
    # Create collection efficiency slab column - check if column exists
    if 'collection_efficiency_pct' in df.columns:
        df['collection_slab'] = df['collection_efficiency_pct'].apply(get_collection_slab)
        
        # Layout: Side by side selection
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            st.markdown("#### 🗺️ Zone-wise Analysis")
            show_zone_ce = st.checkbox("Show Zone-wise Summary", value=True, key="show_zone_collection")
        
        with col2:
            st.markdown("#### 🏙️ Circle-wise Analysis")
            show_circle_ce = st.checkbox("Show Circle-wise Summary", value=True, key="show_circle_collection")
        
        with col3:
            st.markdown("#### 🏢 Division-wise Analysis")
            show_division_ce = st.checkbox("Show Division-wise Summary", value=True, key="show_division_collection")
        
        st.markdown("---")
        
        # ── 1. ZONE-WISE COLLECTION EFFICIENCY SLAB SUMMARY ─────────────────────────
        if show_zone_ce and 'zone' in df.columns:
            st.markdown("### 🗺️ Zone-wise Collection Efficiency Distribution")
            
            # Create zone-wise slab summary
            zone_slab_summary = df.groupby(['zone', 'collection_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per zone
            zone_totals = df.groupby('zone').size().reset_index(name='Total Feeders')
            
            # Merge all data
            zone_summary = zone_totals.merge(zone_slab_summary, on='zone', how='left')
            
            # Fill any missing slab columns with 0
            for slab in collection_slabs:
                if slab["name"] not in zone_summary.columns:
                    zone_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in collection_slabs:
                slab_name = slab["name"]
                zone_summary[f'{slab_name} %'] = (zone_summary[slab_name] / zone_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'Total Feeders']
            for slab in collection_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            zone_summary = zone_summary[[c for c in cols if c in zone_summary.columns]]
            
            # Sort by Total Feeders (descending)
            zone_summary = zone_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                zone_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in collection_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in collection_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            # Download button for zone summary
            csv_zone = zone_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Zone-wise Collection Efficiency Summary (CSV)",
                data=csv_zone,
                file_name=f"DVVNL_Zone_Collection_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── 2. CIRCLE-WISE COLLECTION EFFICIENCY SLAB SUMMARY ───────────────────────
        if show_circle_ce and 'circle' in df.columns and 'zone' in df.columns:
            st.markdown("### 🏙️ Circle-wise Collection Efficiency Distribution (Top 20 by Feeders)")
            
            # Create circle-wise slab summary
            circle_slab_summary = df.groupby(['zone', 'circle', 'collection_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per circle
            circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Feeders')
            
            # Merge all data
            circle_summary = circle_totals.merge(circle_slab_summary, on=['zone', 'circle'], how='left')
            
            # Fill any missing slab columns with 0
            for slab in collection_slabs:
                if slab["name"] not in circle_summary.columns:
                    circle_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in collection_slabs:
                slab_name = slab["name"]
                circle_summary[f'{slab_name} %'] = (circle_summary[slab_name] / circle_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'circle', 'Total Feeders']
            for slab in collection_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            circle_summary = circle_summary[[c for c in cols if c in circle_summary.columns]]
            
            # Sort by Total Feeders (descending) and show top 20
            circle_summary = circle_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                circle_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in collection_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in collection_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            st.caption(f"Showing top 20 circles by feeder count. Total circles: {circle_summary['circle'].nunique() if not circle_summary.empty else 0}")
            
            # Download button for circle summary
            csv_circle = circle_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Circle-wise Collection Efficiency Summary (CSV)",
                data=csv_circle,
                file_name=f"DVVNL_Circle_Collection_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── 3. DIVISION-WISE COLLECTION EFFICIENCY SLAB SUMMARY ─────────────────────
        if show_division_ce and 'division' in df.columns and 'circle' in df.columns:
            st.markdown("### 🏢 Division-wise Collection Efficiency Distribution (Top 30 by Feeders)")
            
            # Create division-wise slab summary
            div_slab_summary = df.groupby(['zone', 'circle', 'division', 'collection_slab']).size().unstack(fill_value=0).reset_index()
            
            # Calculate total feeders per division
            div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Feeders')
            
            # Merge all data
            div_summary = div_totals.merge(div_slab_summary, on=['zone', 'circle', 'division'], how='left')
            
            # Fill any missing slab columns with 0
            for slab in collection_slabs:
                if slab["name"] not in div_summary.columns:
                    div_summary[slab["name"]] = 0
            
            # Calculate percentages for each slab
            for slab in collection_slabs:
                slab_name = slab["name"]
                div_summary[f'{slab_name} %'] = (div_summary[slab_name] / div_summary['Total Feeders'] * 100).round(1)
            
            # Reorder columns
            cols = ['zone', 'circle', 'division', 'Total Feeders']
            for slab in collection_slabs:
                cols.append(slab["name"])
                cols.append(f'{slab["name"]} %')
            
            div_summary = div_summary[[c for c in cols if c in div_summary.columns]]
            
            # Sort by Total Feeders (descending) and show top 30
            div_summary = div_summary.sort_values('Total Feeders', ascending=False)
            
            # Display with styling
            st.dataframe(
                div_summary.style
                .format({
                    'Total Feeders': '{:,.0f}',
                    **{slab["name"]: '{:,.0f}' for slab in collection_slabs},
                    **{f'{slab["name"]} %': '{:.1f}%' for slab in collection_slabs}
                })
                .set_properties(**{'font-weight': 'bold'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background', '#457a9f'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ]),
                use_container_width=True,
                hide_index=True
            )
            
            st.caption(f"Showing top 30 divisions by feeder count. Total divisions: {div_summary['division'].nunique() if not div_summary.empty else 0}")
            
            # Download button for division summary
            csv_division = div_summary.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Division-wise Collection Efficiency Summary (CSV)",
                data=csv_division,
                file_name=f"DVVNL_Division_Collection_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
        
        # ── SUMMARY STATISTICS CARDS ───────────────────────────────────────────────
        st.markdown("### 📊 Overall Collection Efficiency Statistics")
        
        # Calculate overall slab distribution
        slab_counts = df['collection_slab'].value_counts()
        total_feeders = len(df)
        
        # Ensure all slabs are represented
        for slab in collection_slabs:
            if slab["name"] not in slab_counts.index:
                slab_counts[slab["name"]] = 0
        
        # Display slab distribution as metrics
        cols = st.columns(len(collection_slabs))
        for idx, slab in enumerate(collection_slabs):
            if idx < len(cols):
                with cols[idx]:
                    count = slab_counts.get(slab["name"], 0)
                    percentage = (count / total_feeders * 100) if total_feeders > 0 else 0
                    st.metric(
                        label=f"{slab['icon']} {slab['name']}",
                        value=f"{count:,} Feeders",
                        delta=f"{percentage:.1f}% of total",
                        delta_color="normal"
                    )
        
        # Additional insights
        st.markdown("---")
        st.markdown("### 📈 Key Insights")
        
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        
        with insight_col1:
            # Zone with most feeders in Excellent category
            if 'zone' in df.columns:
                excellent_zones = df[df['collection_slab'] == "Excellent (≥95%)"]['zone'].value_counts()
                if not excellent_zones.empty:
                    best_zone = excellent_zones.index[0]
                    excellent_count = excellent_zones.iloc[0]
                    st.success(f"✅ **Best Zone (Collection):** {best_zone}\n\n{excellent_count} feeders with ≥95% collection efficiency")
                else:
                    st.info("No zone with Excellent collection efficiency")
        
        with insight_col2:
            # Zone with most feeders in Critical category
            if 'zone' in df.columns:
                critical_zones = df[df['collection_slab'] == "Critical (<50%)"]['zone'].value_counts()
                if not critical_zones.empty:
                    worst_zone = critical_zones.index[0]
                    critical_count = critical_zones.iloc[0]
                    st.warning(f"⚠️ **Needs Improvement (Collection):** {worst_zone}\n\n{critical_count} feeders with <50% collection efficiency")
                else:
                    st.info("No zone with Critical collection efficiency")
        
        with insight_col3:
            # Most common slab overall
            most_common_slab = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
            most_common_count = slab_counts.max() if not slab_counts.empty else 0
            st.info(f"📊 **Most Common Slab:** {most_common_slab}\n\n{most_common_count:,} Feeders ({most_common_count/total_feeders*100:.1f}%)")
        
        # Educational Note
        st.markdown("---")
        st.markdown("### 💡 Understanding Collection Efficiency")
        st.info("""
        **Collection Efficiency** measures the effectiveness of revenue collection from billed consumers.
        
        **Slab Definitions:**
        - ✅ **Excellent (≥95%)** - Outstanding collection performance
        - 🟢 **Good (85-95%)** - Acceptable collection rate
        - ⚠️ **Moderate (70-85%)** - Needs improvement
        - 🔴 **Poor (50-70%)** - Significant collection issues
        - 💀 **Critical (<50%)** - Severe collection problems
        
        **Note:** 
        - Values >100% (over-collection) are included in Excellent category
        - Negative values (refunds/credits) are included in Critical category
        """)
    
    else:
        st.warning("⚠️ Collection Efficiency data (collection_efficiency_pct column) not available in the dataset. Please check your data source.")



# ══ TAB 5: RANKINGS ══════════════════════════════════════════════════════════
with tabs[4]:
    n_top = st.slider("Top / Bottom N Feeders", 3, 20, 10)
    col1, col2 = st.columns(2)
    with col1:
        top = df.nsmallest(n_top, "atc_loss_pct") if "atc_loss_pct" in df.columns else df.head(n_top)
        st.markdown(f"**🏆 Best {n_top} — Lowest AT&C**")
        fig = px.bar(top, y="outgoing_feeder", x="atc_loss_pct", orientation="h",
                     color="atc_loss_pct", color_continuous_scale=[[0,"#22c55e"],[1,"#eab308"]],
                     hover_data=["zone","billing_efficiency_pct","collection_efficiency_pct"])
        fig.update_layout(**dark_layout(showlegend=False))
        st.plotly_chart(fig, width='stretch', key="tab5_best_atc_bar",config=PLOTLY_CONFIG)
    with col2:
        bot = df.nlargest(n_top, "atc_loss_pct") if "atc_loss_pct" in df.columns else df.tail(n_top)
        st.markdown(f"**🔴 Worst {n_top} — Highest AT&C**")
        fig2 = px.bar(bot, y="outgoing_feeder", x="atc_loss_pct", orientation="h",
                      color="atc_loss_pct", color_continuous_scale=[[0,"#f97316"],[1,"#ef4444"]],
                      hover_data=["zone","billing_efficiency_pct","collection_efficiency_pct"])
        fig2.update_layout(**dark_layout(showlegend=False))
        st.plotly_chart(fig2,  width='stretch', key="tab5_worst_atc_bar",config=PLOTLY_CONFIG)

    st.markdown("**Full KPI Ranking Table**")
    rank_cols = ["outgoing_feeder","zone","circle","feeder_nature","line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct","input_energy_kwh","revenue_realized"]
    avail_rank = [c for c in rank_cols if c in df.columns]
    df_rank = df[avail_rank].copy()
    df_rank.insert(0, "#", range(1, len(df_rank)+1))
    if "atc_loss_pct" in df_rank.columns:
        df_rank["Rating"] = df_rank["atc_loss_pct"].apply(rating)
    fmt_pct = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"] if c in df_rank.columns}
    fmt_num = {c:"{:,.0f}" for c in ["input_energy_kwh","revenue_realized"] if c in df_rank.columns}
    st.dataframe(df_rank.style.format({**fmt_pct, **fmt_num})
                 .background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in df_rank.columns else [], cmap="RdYlGn_r"),
                 width='stretch', hide_index=True)

# ══ TAB 6: ZONE COMPARISON ════════════════════════════════════════════════════
with tabs[5]:
    col1, col2 = st.columns(2)
    with col1:
        if not zone_df.empty:
            st.markdown("**Radar: Multi-KPI Zone Comparison**")
            st.plotly_chart(chart_zone_radar(zone_df), width='stretch', key="tab6_zone_radar",config=PLOTLY_CONFIG)
    with col2:
        if not zone_df.empty and "atc_loss_pct" in zone_df.columns:
            st.markdown("**Zone AT&C Loss**")
            z_s = zone_df.sort_values("atc_loss_pct", ascending=True)
            fig = go.Figure(go.Bar(y=z_s["zone"], x=z_s["atc_loss_pct"], orientation="h",
                                   marker_color=[atc_color(v) for v in z_s["atc_loss_pct"]],
                                   text=z_s["atc_loss_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside"))
            fig.update_layout(**dark_layout())
            st.plotly_chart(fig, width='stretch', key="tab6_zone_atc_loss",config=PLOTLY_CONFIG)
    if not circ_df.empty:
        st.markdown("**Circle-wise KPI**")
        circ_cols = [c for c in ["circle","zone","feeder_count","atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in circ_df.columns]
        pct_cols  = {c:"{:.1f}%" for c in ["atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in circ_df.columns}
#        st.write(circ_df.columns.tolist())
#        print(circ_df.columns.tolist())
        st.dataframe(circ_df[circ_cols].sort_values("atc_loss_pct", ascending=False).style
                     .format(pct_cols)
                     .background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in circ_df.columns else [], cmap="RdYlGn_r"),
                     width='stretch',hide_index=True)


        # NEW: Division-wise KPI Heatmap
        if not div_df.empty:
            st.markdown("**Division-wise KPI Heatmap**")
            div_cols = [c for c in ["division","circle","feeder_count","atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in div_df.columns]
            div_pct_cols = {c:"{:.1f}%" for c in ["atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in div_df.columns}
            st.dataframe(div_df[div_cols].sort_values("atc_loss_pct", ascending=False).style
                         .format(div_pct_cols)
                         .background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in div_df.columns else [], cmap="RdYlGn_r"),
                         width='stretch', hide_index=True)


# ══ TAB 7: TREEMAP ════════════════════════════════════════════════════════════
with tabs[6]:
# ══ TAB 13: TREE HIERARCHY ANALYTICAL DASHBOARD ════════════════════════════════

    st.markdown('<div class="section-title">🌳 Tree Hierarchy Analytical Dashboard - Zone | Circle | Division | Substation | Feeder</div>',
                unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
        <span style="color: #0f172a; font-size: 14px;">
        📌 <b>Management Insights:</b> Drill down from Zone to Feeder level to identify performance bottlenecks, 
        revenue leakage points, and operational inefficiencies across the hierarchy.
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # ── HIERARCHY LEVEL SELECTOR ──────────────────────────────────────────────────
    st.markdown("### 📊 Select Hierarchy Level for Analysis")
    
    level_col1, level_col2, level_col3, level_col4 = st.columns([2, 2, 2, 4])
    
    with level_col1:
        hierarchy_level = st.selectbox(
            "📌 View Level",
            ["Zone Level", "Circle Level", "Division Level", "Substation Level", "Feeder Level"],
            key="tree_hierarchy_level"
        )
    
    with level_col2:
        # Sort options
        sort_by = st.selectbox(
            "📊 Sort By",
            ["AT&C Loss %", "Collection Efficiency %", "Line Loss %", "Input Energy", "Revenue", "Outstanding Amount"],
            key="tree_sort_by"
        )
    
    with level_col3:
        sort_order = st.radio(
            "Sort Order",
            ["Highest to Lowest", "Lowest to Highest"],
            horizontal=True,
            key="tree_sort_order"
        )
    
    with level_col4:
        show_top_n = st.slider("Show Top N Records", 10, 100, 50, key="tree_show_top")
    
    st.markdown("---")
    
    # ── FUNCTION TO CREATE HIERARCHY DATAFRAME ────────────────────────────────────
    def create_hierarchy_dataframe(df, level):
        """Create aggregated dataframe at specified hierarchy level"""
        
        if level == "Zone Level" and 'zone' in df.columns:
            group_cols = ['zone']
            display_cols = ['Zone']
            
        elif level == "Circle Level" and 'circle' in df.columns:
            group_cols = ['zone', 'circle']
            display_cols = ['Zone', 'Circle']
            
        elif level == "Division Level" and 'division' in df.columns:
            group_cols = ['zone', 'circle', 'division']
            display_cols = ['Zone', 'Circle', 'Division']
            
        elif level == "Substation Level" and 'substation' in df.columns:
            group_cols = ['zone', 'circle', 'division', 'substation']
            display_cols = ['Zone', 'Circle', 'Division', 'Substation']
            
        elif level == "Feeder Level":
            group_cols = ['zone', 'circle', 'division', 'substation', 'outgoing_feeder']
            display_cols = ['Zone', 'Circle', 'Division', 'Substation', 'Feeder']
        else:
            return pd.DataFrame(), []
        
        # Aggregation dictionary
        agg_dict = {
            'input_energy_kwh': 'sum',
            'sold_energy_kwh': 'sum',
            'net_assessment': 'sum',
            'revenue_realized': 'sum',
            'consumers': 'sum',
            'billed_consumers': 'sum',
            'paid_consumers': 'sum',
            'smart_meter_consumers': 'sum',
            'total_outstanding_amount': 'sum'
        }
        
        
        # Perform aggregation
        hierarchy_df = df.groupby(group_cols).agg(agg_dict).reset_index()
        # Convert to float to handle negative values properly
        for col in ['input_energy_kwh', 'sold_energy_kwh', 'net_assessment', 'revenue_realized']:
            if col in hierarchy_df.columns:
                hierarchy_df[col] = hierarchy_df[col].astype(float)
    
    # Calculate weighted KPIs after aggregation
    # Line Loss %
        hierarchy_df['line_loss_pct'] = 0.0
        mask = hierarchy_df['input_energy_kwh'] > 0
        hierarchy_df.loc[mask, 'line_loss_pct'] = (
        (hierarchy_df.loc[mask, 'input_energy_kwh'] - hierarchy_df.loc[mask, 'sold_energy_kwh']).astype(float) / 
        hierarchy_df.loc[mask, 'input_energy_kwh'].astype(float) * 100
    ).round(2)
    
    # Billing Efficiency %
        hierarchy_df['billing_efficiency_pct'] = 0.0
        hierarchy_df.loc[mask, 'billing_efficiency_pct'] = (
        hierarchy_df.loc[mask, 'sold_energy_kwh'].astype(float) / 
        hierarchy_df.loc[mask, 'input_energy_kwh'].astype(float) * 100
    ).round(2)
    
    # Collection Efficiency %
        hierarchy_df['collection_efficiency_pct'] = 0.0
        mask2 = hierarchy_df['net_assessment'] > 0
        hierarchy_df.loc[mask2, 'collection_efficiency_pct'] = (
        hierarchy_df.loc[mask2, 'revenue_realized'].astype(float) / 
        hierarchy_df.loc[mask2, 'net_assessment'].astype(float) * 100
    ).round(2)
    
    # AT&C Loss %
        hierarchy_df['atc_loss_pct'] = (
        100.0 - (hierarchy_df['billing_efficiency_pct'].astype(float) * 
                 hierarchy_df['collection_efficiency_pct'].astype(float) / 100.0)
    ).round(2).fillna(0)
    
    # Ensure no negative values cause issues (but preserve negative line losses if they exist)
    # For AT&C and Collection Efficiency, clip to reasonable ranges
        hierarchy_df['collection_efficiency_pct'] = hierarchy_df['collection_efficiency_pct'].clip(0, 100)
        hierarchy_df['billing_efficiency_pct'] = hierarchy_df['billing_efficiency_pct'].clip(0, 100)
         # Rename columns
        hierarchy_df = hierarchy_df.rename(columns={
            'zone': 'Zone',
            'circle': 'Circle',
            'division': 'Division',
            'substation': 'Substation',
            'outgoing_feeder': 'Feeder',
            'input_energy_kwh': 'Input Energy (KWH)',
            'sold_energy_kwh': 'Sold Energy (KWH)',
            'net_assessment': 'Assessment (₹)',
            'revenue_realized': 'Revenue (₹)',
            'consumers': 'Total Consumers',
            'billed_consumers': 'Billed Consumers',
            'paid_consumers': 'Paid Consumers',
            'smart_meter_consumers': 'Smart Meters',
            'total_outstanding_amount': 'Outstanding (₹)',
            'line_loss_pct': 'Line Loss %',
            'billing_efficiency_pct': 'Billing Eff %',
            'collection_efficiency_pct': 'Collection Eff %',
            'atc_loss_pct': 'AT&C Loss %'
        })
        
        # Round percentage columns
        for col in ['Line Loss %', 'Billing Eff %', 'Collection Eff %', 'AT&C Loss %']:
            if col in hierarchy_df.columns:
                hierarchy_df[col] = hierarchy_df[col].round(2)
        
        return hierarchy_df, display_cols
    
    # ── CREATE HIERARCHY DATAFRAME ───────────────────────────────────────────────
    hierarchy_df, display_cols = create_hierarchy_dataframe(df, hierarchy_level)
    
    if not hierarchy_df.empty:
        
        # ── SORTING ───────────────────────────────────────────────────────────────
        sort_column_map = {
            "AT&C Loss %": "AT&C Loss %",
            "Collection Efficiency %": "Collection Eff %",
            "Line Loss %": "Line Loss %",
            "Input Energy": "Input Energy (KWH)",
            "Revenue": "Revenue (₹)",
            "Outstanding Amount": "Outstanding (₹)"
        }
        
        sort_col = sort_column_map.get(sort_by, "AT&C Loss %")
        
        if sort_col in hierarchy_df.columns:
            ascending = (sort_order == "Lowest to Highest")
            hierarchy_df = hierarchy_df.sort_values(sort_col, ascending=ascending)
        
        # Limit to top N
        hierarchy_df = hierarchy_df.head(show_top_n)
        
        # ── DISPLAY COLUMNS IN ORDER ──────────────────────────────────────────────
        all_columns = display_cols + [
            'AT&C Loss %', 'Collection Eff %', 'Line Loss %', 'Billing Eff %',
            'Input Energy (KWH)', 'Sold Energy (KWH)',
            'Assessment (₹)', 'Revenue (₹)',
            'Total Consumers', 'Billed Consumers', 'Paid Consumers', 'Smart Meters',
            'Outstanding (₹)'
        ]
        
        # Keep only columns that exist
        display_columns = [col for col in all_columns if col in hierarchy_df.columns]
        hierarchy_df = hierarchy_df[display_columns]
        
        # ── MAIN DATA TABLE ───────────────────────────────────────────────────────
        st.markdown(f"### 📋 {hierarchy_level} Analytical Data (Top {len(hierarchy_df)} Records)")
        
        # Format the dataframe for display
        formatted_df = hierarchy_df.copy()
        
        # Format percentage columns
        pct_cols = ['AT&C Loss %', 'Collection Eff %', 'Line Loss %', 'Billing Eff %']
        for col in pct_cols:
            if col in formatted_df.columns:
                formatted_df[col] = formatted_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        
        # Format currency columns using fmt_lakh
        currency_cols = ['Assessment (₹)', 'Revenue (₹)', 'Outstanding (₹)']
        for col in currency_cols:
            if col in formatted_df.columns:
                formatted_df[col] = formatted_df[col].apply(lambda x: fmt_lakh(x) if pd.notna(x) and x > 0 else "₹0")
        
        # Format energy columns using fmt_lakh
        energy_cols = ['Input Energy (KWH)', 'Sold Energy (KWH)']
        for col in energy_cols:
            if col in formatted_df.columns:
                formatted_df[col] = formatted_df[col].apply(lambda x: fmt_lakh(x) if pd.notna(x) else "0")
        
        # Format count columns with commas
        count_cols = ['Total Consumers', 'Billed Consumers', 'Paid Consumers', 'Smart Meters']
        for col in count_cols:
            if col in formatted_df.columns:
                formatted_df[col] = formatted_df[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
        
        # Display the dataframe with bold formatting
        st.dataframe(
            formatted_df.style.set_properties(**{'font-weight': 'bold', 'text-align': 'left'}),
            use_container_width=True,
            hide_index=True
        )
        
        # ── DOWNLOAD BUTTONS ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📥 Export Data")
        
        dl_col1, dl_col2 = st.columns(2)
        
        with dl_col1:
            csv_data = hierarchy_df.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Current View (CSV)",
                data=csv_data,
                file_name=f"DVVNL_Tree_Hierarchy_{hierarchy_level.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with dl_col2:
            # Full data download
            full_df, _ = create_hierarchy_dataframe(df, hierarchy_level)
            full_csv = full_df.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Full Data (CSV)",
                data=full_csv,
                file_name=f"DVVNL_Tree_Hierarchy_{hierarchy_level.replace(' ', '_')}_Full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    else:
        st.warning(f"⚠️ No data available for {hierarchy_level}. Please check if required columns exist in the dataset.")
        st.info("""
        **Required Columns for each level:**
        - Zone Level: 'zone' column
        - Circle Level: 'zone', 'circle' columns
        - Division Level: 'zone', 'circle', 'division' columns
        - Substation Level: 'zone', 'circle', 'division', 'substation' columns
        - Feeder Level: 'zone', 'circle', 'division', 'substation', 'outgoing_feeder' columns
        """)

# ══ TAB 8: DATA & EXPORT ═════════════════════════════════════════════════════
with tabs[7]:
    all_cols     = df.columns.tolist()
    default_cols = [c for c in ["outgoing_feeder","zone","circle","feeder_nature","input_energy_kwh","sold_energy_kwh",
                    "line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct",
                    "net_assessment","revenue_realized","billed_consumers","paid_consumers"] if c in all_cols]
    show_cols = st.multiselect("Columns to display:", all_cols, default=default_cols)
    search    = st.text_input("🔍 Search feeder / zone:", "")

    df_disp = df.copy()
    if search:
        # ⚡ FAST VECTORIZED SEARCH (Replaces the slow row-by-row apply)
        mask = df_disp.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
        df_disp = df_disp[mask]
    df_disp = df_disp[show_cols] if show_cols else df_disp


    pct_fmt = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"] if c in df_disp.columns}
    num_fmt = {c:"{:,.0f}"  for c in ["input_energy_kwh","sold_energy_kwh","net_assessment","revenue_realized"] if c in df_disp.columns}
    st.dataframe(df_disp.style.format({**pct_fmt, **num_fmt}), width='stretch', hide_index=True)
    st.caption(f"Showing {len(df_disp)} of {len(df)} feeders")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📥 Download CSV", df.to_csv(index=False).encode(),
                           f"DVVNL_Feeder_ATC_{month_start}_{month_end}.csv", "text/csv", width='stretch')
    with c2:
        st.download_button("📊 Download Excel", export_excel(df),
                           f"DVVNL_Feeder_ATC_{month_start}_{month_end}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
    with c3:
        if not unmatched_df.empty:
            st.download_button("⚠️ Unmatched Feeders CSV", unmatched_df.to_csv(index=False).encode(),
                               "DVVNL_Unmatched_Feeders.csv", "text/csv", width='stretch')
        else:
            st.success("✅ All feeders matched!")

    st.markdown("---")

# ══ TAB 9: SLAB ANALYSIS ════════════════════════════════════════════════════
with tabs[8]:
 
    st.markdown('<div class="section-title">📐 Slab-wise Abstract — AT&C | Billing Eff | Collection Eff</div>',
                unsafe_allow_html=True)
 
    # ── SLAB DEFINITIONS ──────────────────────────────────────────────────────
    ATC_SLABS = [
        {"label": "Below 15%",    "min": -999, "max": 15,   "color": "#22c55e", "bg": "#f0fdf4", "text": "✅ GOOD"},
        {"label": "15% – 30%",   "min": 15,   "max": 30,   "color": "#84cc16", "bg": "#f7fee7", "text": "🟢 OK"},
        {"label": "30% – 50%",   "min": 30,   "max": 50,   "color": "#eab308", "bg": "#fefce8", "text": "⚠️ HIGH"},
        {"label": "50% – 75%",   "min": 50,   "max": 75,   "color": "#f97316", "bg": "#fff7ed", "text": "🟠 CRITICAL"},
        {"label": "Above 75%",   "min": 75,   "max": 9999, "color": "#ef4444", "bg": "#fef2f2", "text": "🔴 SEVERE"},
    ]
 
    BE_SLABS = [
        {"label": "Above 90%",   "min": 90,   "max": 9999, "color": "#22c55e", "bg": "#f0fdf4", "text": "✅ EXCELLENT"},
        {"label": "75% – 90%",   "min": 75,   "max": 90,   "color": "#84cc16", "bg": "#f7fee7", "text": "🟢 GOOD"},
        {"label": "60% – 75%",   "min": 60,   "max": 75,   "color": "#eab308", "bg": "#fefce8", "text": "⚠️ AVERAGE"},
        {"label": "40% – 60%",   "min": 40,   "max": 60,   "color": "#f97316", "bg": "#fff7ed", "text": "🟠 POOR"},
        {"label": "Below 40%",   "min": -999, "max": 40,   "color": "#ef4444", "bg": "#fef2f2", "text": "🔴 CRITICAL"},
    ]
 
    CE_SLABS = [
        {"label": "Above 95%",   "min": 95,   "max": 9999, "color": "#22c55e", "bg": "#f0fdf4", "text": "✅ EXCELLENT"},
        {"label": "85% – 95%",   "min": 85,   "max": 95,   "color": "#84cc16", "bg": "#f7fee7", "text": "🟢 GOOD"},
        {"label": "70% – 85%",   "min": 70,   "max": 85,   "color": "#eab308", "bg": "#fefce8", "text": "⚠️ AVERAGE"},
        {"label": "50% – 70%",   "min": 50,   "max": 70,   "color": "#f97316", "bg": "#fff7ed", "text": "🟠 POOR"},
        {"label": "Below 50%",   "min": -999, "max": 50,   "color": "#ef4444", "bg": "#fef2f2", "text": "🔴 CRITICAL"},
    ]
 
    def get_slab_df(df_in, col, slabs):
        """Classify feeders into slabs for a given KPI column."""
        rows = []
        for s in slabs:
            mask = (df_in[col] >= s["min"]) & (df_in[col] < s["max"])
            grp  = df_in[mask]
            cnt  = len(grp)
            if cnt == 0:
                rows.append({**s, "feeder_count": 0,
                              "input_kwh": 0, "sold_kwh": 0,
                              "assessment": 0, "revenue": 0,
                              "avg_kpi": 0, "_df": grp})
                continue
            inp  = grp["input_energy_kwh"].sum()
            sold = grp["sold_energy_kwh"].sum()
            ass  = grp["net_assessment"].sum()
            rev  = grp["revenue_realized"].sum()
            be   = sold/inp  if inp  > 0 else 0
            ce   = rev/ass   if ass  > 0 else 0
            atc  = (1 - be*ce) * 100
            rows.append({
                **s,
                "feeder_count":  cnt,
                "input_kwh":     round(inp,  2),
                "sold_kwh":      round(sold, 2),
                "assessment":    round(ass,  2),
                "revenue":       round(rev,  2),
                "avg_kpi":       round(grp[col].mean(), 1),
                "line_loss_pct": round((inp-sold)/inp*100, 2) if inp>0 else 0,
                "billing_eff":   round(be*100, 2),
                "collection_eff":round(ce*100, 2),
                "atc":           round(atc,  2),
                "_df":           grp,
            })
        return rows
 
    def fmt_cr(n):
        if abs(n) >= 1e7: return f"₹{n/1e7:.2f} Cr"
        if abs(n) >= 1e5: return f"₹{n/1e5:.2f} L"
        return f"₹{n:,.0f}"
 
    def fmt_kwh(n):
        if abs(n) >= 1e6: return f"{n/1e6:.2f} MU"
        if abs(n) >= 1e3: return f"{n/1e3:.1f} KU"
        return f"{n:,.0f} KWH"
 
    # ── SLAB SELECTOR ─────────────────────────────────────────────────────────
    slab_type = st.radio(
        "Select KPI for Slab Analysis:",
        ["🔴 AT&C Loss %", "⚡ Billing Efficiency %", "💰 Collection Efficiency %"],
        horizontal=True,
        key="slab_type_radio"
    )
 
    if slab_type == "🔴 AT&C Loss %":
        slabs_def = ATC_SLABS
        kpi_col   = "atc_loss_pct"
        kpi_label = "AT&C Loss %"
    elif slab_type == "⚡ Billing Efficiency %":
        slabs_def = BE_SLABS
        kpi_col   = "billing_efficiency_pct"
        kpi_label = "Billing Eff %"
    else:
        slabs_def = CE_SLABS
        kpi_col   = "collection_efficiency_pct"
        kpi_label = "Collection Eff %"
 
    # Build slab data from current filtered df
    slab_rows = get_slab_df(df, kpi_col, slabs_def)
    total_feeders = len(df)
 
    # ── ABSTRACT SUMMARY CARDS ────────────────────────────────────────────────
    st.markdown(f"### 📊 {kpi_label} Slab Abstract — {total_feeders} Feeders")
 
    # Color-coded markup boxes (like the image)
    markup_cols = st.columns(len(slabs_def))
    for i, (col_widget, s) in enumerate(zip(markup_cols, slab_rows)):
        cnt  = s["feeder_count"]
        pct  = round(cnt / total_feeders * 100, 1) if total_feeders > 0 else 0
        with col_widget:
            st.markdown(f"""
            <div style="
                background:{s['bg']};
                border:3px solid {s['color']};
                border-radius:16px;
                padding:16px 10px;
                text-align:center;
                cursor:pointer;
                box-shadow:0 4px 16px {s['color']}33;
                margin-bottom:8px;
            ">
                <div style="font-size:36px;font-weight:900;color:{s['color']};
                            font-family:'JetBrains Mono',monospace;line-height:1">
                    {cnt}
                </div>
                <div style="font-size:11px;color:#64748b;font-weight:700;margin-top:2px">
                    {s['label']}
                </div>
                <div style="font-size:13px;font-weight:800;color:{s['color']};margin-top:4px">
                    {s['text']}
                </div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px">
                    {pct}% of feeders
                </div>
                <div style="font-size:11px;color:#64748b;margin-top:6px;font-weight:700">
                    Avg {kpi_label}: {s['avg_kpi']}%
                </div>
            </div>
            """, unsafe_allow_html=True)
 
    st.markdown("---")
 
    # ── SLAB SELECTION DROPDOWN (clickable) ───────────────────────────────────
    slab_options = [f"{s['text']}  {s['label']}  ({s['feeder_count']} feeders)" for s in slab_rows]
    selected_slab_label = st.selectbox(
        "🔍 Click a slab to view feeder details:",
        ["— Select a slab —"] + slab_options,
        key="slab_detail_select"
    )
 
    # ── SLAB DETAIL TABLE ─────────────────────────────────────────────────────
    if selected_slab_label != "— Select a slab —":
        slab_idx  = slab_options.index(selected_slab_label)
        sel_slab  = slab_rows[slab_idx]
        slab_df   = sel_slab["_df"].copy()
 
        st.markdown(f"""
        <div style="background:{sel_slab['bg']};border:2px solid {sel_slab['color']};
                    border-radius:14px;padding:14px 20px;margin:8px 0 16px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                <div>
                    <span style="font-size:22px;font-weight:900;color:{sel_slab['color']}">{sel_slab['text']}  {sel_slab['label']}</span>
                    <span style="font-size:14px;color:#64748b;margin-left:10px">{sel_slab['feeder_count']} Feeders  |  Avg {kpi_label}: {sel_slab['avg_kpi']}%</span>
                </div>
                <div style="display:flex;gap:16px;flex-wrap:wrap">
                    <span style="font-size:13px;color:#475569">Input: <b>{fmt_kwh(sel_slab['input_kwh'])}</b></span>
                    <span style="font-size:13px;color:#475569">Sold: <b>{fmt_kwh(sel_slab['sold_kwh'])}</b></span>
                    <span style="font-size:13px;color:#475569">Assessment: <b>{fmt_cr(sel_slab['assessment'])}</b></span>
                    <span style="font-size:13px;color:#475569">Revenue: <b>{fmt_cr(sel_slab['revenue'])}</b></span>
                </div>
            </div>
            <div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap">
                <span style="font-size:12px;color:#475569">AT&C: <b style="color:{'#22c55e' if sel_slab['atc']<15 else '#f97316' if sel_slab['atc']<50 else '#ef4444'}">{sel_slab['atc']:.1f}%</b></span>
                <span style="font-size:12px;color:#475569">Billing Eff: <b style="color:#22c55e">{sel_slab['billing_eff']:.1f}%</b></span>
                <span style="font-size:12px;color:#475569">Collection Eff: <b style="color:#3b82f6">{sel_slab['collection_eff']:.1f}%</b></span>
                <span style="font-size:12px;color:#475569">Line Loss: <b style="color:#f97316">{sel_slab['line_loss_pct']:.1f}%</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)
 
        # Charts for selected slab
        if not slab_df.empty:
            c1, c2 = st.columns(2)
 
            with c1:
                st.markdown(f"**{kpi_label} distribution within slab**")
                fig_hist = px.histogram(
                    slab_df, x=kpi_col, nbins=20,
                    color_discrete_sequence=[sel_slab["color"]],
                    labels={kpi_col: kpi_label}
                )
                fig_hist.update_layout(**dark_layout(showlegend=False))
                st.plotly_chart(fig_hist, width='stretch', key="slab_hist_kpi",config=PLOTLY_CONFIG)
 
            with c2:
                st.markdown("**Zone breakdown within slab**")
                if "zone" in slab_df.columns:
                    zone_grp = slab_df.groupby("zone").agg(
                        feeder_count=("outgoing_feeder","count"),
                        avg_atc=("atc_loss_pct","mean"),
                        avg_be=("billing_efficiency_pct","mean"),
                        avg_ce=("collection_efficiency_pct","mean"),
                    ).reset_index().round(1)
                    fig_zone = px.bar(
                        zone_grp, y="zone", x="feeder_count",
                        orientation="h",
                        color="avg_atc",
                        color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                        text="feeder_count",
                        labels={"feeder_count":"Feeders","avg_atc":"Avg AT&C %"}
                    )
                    fig_zone.update_traces(textposition="outside")
                    fig_zone.update_layout(**dark_layout(showlegend=False))
                    st.plotly_chart(fig_zone, width='stretch', key="slab_zone_bar",config=PLOTLY_CONFIG)
 
            # # AT&C bar for feeders in slab
            # st.markdown(f"**AT&C Loss % — Feeders in '{sel_slab['label']}' Slab**")
            # slab_sorted = slab_df.sort_values("atc_loss_pct", ascending=False)
            # fig_atc = px.bar(
            #     slab_sorted, x="outgoing_feeder", y="atc_loss_pct",
            #     color="atc_loss_pct",
            #     color_continuous_scale=[[0,"#22c55e"],[0.4,"#eab308"],[0.7,"#f97316"],[1,"#ef4444"]],
            #     range_color=[0,100],
            #     hover_data=["zone","billing_efficiency_pct","collection_efficiency_pct",
            #                 "input_energy_kwh","revenue_realized"],
            #     labels={"atc_loss_pct":"AT&C Loss %","outgoing_feeder":"Feeder"}
            # )
            # fig_atc.update_layout(**dark_layout(xaxis_tickangle=-45, showlegend=False,
            #                                     height=max(350, len(slab_df)*18)))
            # st.plotly_chart(fig_atc, width='stretch', key="slab_atc_bar",config=PLOTLY_CONFIG)
 
            # Full detail table
            st.markdown(f"**📋 Feeder Detail Table — {len(slab_df)} Feeders**")
            detail_cols = [c for c in [
                "outgoing_feeder","zone","circle","division","feeder_nature",
                "input_energy_kwh","sold_energy_kwh","line_loss_pct",
                "billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct",
                "net_assessment","revenue_realized",
                "consumers","billed_consumers","paid_consumers"
            ] if c in slab_df.columns]
 
            disp = slab_df[detail_cols].copy()
            disp.insert(0,"#", range(1, len(disp)+1))
 
            pf = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct",
                                          "collection_efficiency_pct","atc_loss_pct"]
                  if c in disp.columns}
            nf = {c:"{:,.0f}" for c in ["input_energy_kwh","sold_energy_kwh",
                                          "net_assessment","revenue_realized"]
                  if c in disp.columns}
 
            st.dataframe(
                disp.sort_values("atc_loss_pct", ascending=False)
                    .style.format({**pf, **nf})
                    .background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in disp.columns else [],
                                         cmap="RdYlGn_r"),
                width='stretch', hide_index=True
            )
 
            # Download slab data
            st.download_button(
                f"📥 Download '{sel_slab['label']}' Slab Data",
                slab_df[detail_cols].to_csv(index=False).encode(),
                f"DVVNL_Slab_{kpi_col}_{sel_slab['label'].replace('%','').replace(' ','_')}.csv",
                "text/csv",
                width='stretch'
            )
 
    # ── ALL SLABS SUMMARY TABLE ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 All Slabs Summary Table")
 
    summary_rows = []
    for s in slab_rows:
        pct = round(s['feeder_count']/total_feeders*100, 1) if total_feeders > 0 else 0
        summary_rows.append({
            "Slab":           s["label"],
            "Status":         s["text"],
            "Feeders":        s["feeder_count"],
            "% of Total":     f"{pct}%",
            f"Avg {kpi_label}": f"{s['avg_kpi']}%",
            "Input Energy":   fmt_kwh(s["input_kwh"]),
            "Units Sold":     fmt_kwh(s["sold_kwh"]),
            "Assessment":     fmt_cr(s["assessment"]),
            "Revenue":        fmt_cr(s["revenue"]),
            "AT&C %":         f"{s['atc']:.1f}%",
            "Billing Eff %":  f"{s['billing_eff']:.1f}%",
            "Coll Eff %":     f"{s['collection_eff']:.1f}%",
            "Line Loss %":    f"{s['line_loss_pct']:.1f}%",
        })
 
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, width='stretch', hide_index=True)
 
    # ── CROSS-SLAB CHART ──────────────────────────────────────────────────────
    st.markdown("### 📈 Cross-Slab KPI Comparison")
    
 
    
    st.markdown("**Feeder Count by Slab**")
    fig_cnt = px.bar(
            summary_df, x="Slab", y="Feeders",
            color="Slab",
            color_discrete_sequence=[s["color"] for s in slab_rows],
            text="Feeders"
        )
    fig_cnt.update_traces(textposition="outside")
    fig_cnt.update_layout(**dark_layout(showlegend=False))
    st.plotly_chart(fig_cnt, width='stretch', key="slab_count_bar", config=PLOTLY_CONFIG)
 
    
 
    # Dual-metric: All 3 KPIs side by side per slab
    st.markdown("**AT&C + Billing Eff + Collection Eff by Slab**")
    kpi_compare = []
    for s in slab_rows:
        if s["feeder_count"] > 0:
            kpi_compare += [
                {"Slab": s["label"], "KPI": "AT&C Loss %",        "Value": s["atc"],            "color": "#ef4444"},
                {"Slab": s["label"], "KPI": "Billing Eff %",       "Value": s["billing_eff"],    "color": "#22c55e"},
                {"Slab": s["label"], "KPI": "Collection Eff %",    "Value": s["collection_eff"], "color": "#3b82f6"},
            ]
    if kpi_compare:
        kpi_df = pd.DataFrame(kpi_compare)
        fig_kpi = px.bar(
            kpi_df, x="Slab", y="Value", color="KPI",
            barmode="group",
            color_discrete_map={
                "AT&C Loss %":     "#ef4444",
                "Billing Eff %":   "#22c55e",
                "Collection Eff %":"#3b82f6"
            },
            labels={"Value":"%","Slab":"Slab"}
        )
        fig_kpi.update_layout(**dark_layout())
        st.plotly_chart(fig_kpi, width='stretch', key="slab_kpi_compare", config=PLOTLY_CONFIG)


    st.markdown("**Grand Total Row (computed from aggregates)**")
    st.dataframe(pd.DataFrame([gt]), width='stretch',hide_index=True)