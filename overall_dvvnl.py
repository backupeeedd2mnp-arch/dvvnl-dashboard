"""
overall_dvvnl.py — DVVNL Overall Performance Dashboard
========================================================
Aggregates data from feeder and substation sources to provide
unified division, circle, and zone analytics.

Data Source: DVVNL_OVERALL_APRIL26.csv (to be placed in same folder)

UNITS NOTE:
  - input_energy_kwh / sold_energy_kwh in CSV  → Million Units (MU)  [stored as-is]
  - net_assessment / revenue_realized in CSV    → Lakhs (₹ L)         [stored as-is]
"""

from operator import gt as op_gt

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import io
from datetime import datetime
import os

from charts import dark_layout, atc_color, chart_zone_radar, chart_funnel


st.set_page_config(
    page_title="DVVNL Overall Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
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
</style>
""", unsafe_allow_html=True)
# ── UNIT CONSTANTS ─────────────────────────────────────────────────────────────
# CSV columns are in MU and Lakhs — helpers convert for display only
MU_COL   = 1           # columns already in MU  → no division needed
LAKH_COL = 1           # columns already in Lakhs → no division needed
LAKH_TO_CR = 100       # 1 Crore = 100 Lakhs
# Real Rate (₹/kWh) = (Revenue in Lakhs × 1e5) / (Energy in MU × 1e6)
#                   = Revenue × 1e5 / (Energy × 1e6) = Revenue / (Energy × 10)
RATE_FACTOR = 10       # revenue(L) / (energy(MU) * RATE_FACTOR)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def fmt_lakh(n):
    if n is None or (isinstance(n, float) and pd.isna(n)): return "—"
    if abs(n) >= 1e7: return f"{n/1e7:.2f} Cr"
    if abs(n) >= 1e5: return f"{n/1e5:.2f} L"
    if abs(n) >= 1e3: return f"{n/1e3:.1f} K"
    return f"{n:.0f}"

def rating(v):
    if v is None: return "N/A"
    if v < 15.0: return "✅ GOOD"
    if v < 30.0: return "⚠️ OK"
    if v < 50.0: return "🟠 HIGH"
    return "🔴 CRITICAL"

def kpi_card(label, value, unit="", color="#2563eb", sub=""):
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#c7d2fe,#8ab3d0);border-radius:18px;
                padding:16px 14px;border-left:5px solid {color};margin-bottom:10px;
                box-shadow:0 8px 20px {color}22;">
        <div style="color:#334155;font-size:11px;text-transform:uppercase;
                    font-weight:700;letter-spacing:1.5px;margin-bottom:4px">{label}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:20px;
                    font-weight:700;color:{color}">{value}<span style="font-size:12px;
                    color:#64748b"> {unit}</span></div>
        <div style="color:#475569;font-size:10px;margin-top:2px">{sub}</div>
    </div>""", unsafe_allow_html=True)

def export_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Overall_KPIs")
    return buf.getvalue()

def build_hierarchy_header(zone_sel, circle_sel, division_sel, level_filter, total_units):
    hierarchy_parts = []
    if zone_sel != "All Zones":
        hierarchy_parts.append(f'<span style="color: #60a5fa;">🗺️ {zone_sel}</span>')
    if circle_sel != "All Circles":
        hierarchy_parts.append(f'<span style="color: #34d399;">🏙️ {circle_sel}</span>')
    if division_sel != "All Divisions":
        hierarchy_parts.append(f'<span style="color: #fbbf24;">🏢 {division_sel}</span>')
    if hierarchy_parts:
        hierarchy_display = " → ".join(hierarchy_parts)
        level_text = f"View: {level_filter} Level"
    else:
        hierarchy_display = "🏢 DVVNL (All Units)"
        level_text = f"View: {level_filter} Level"
    return f"""
    <div style="background:linear-gradient(135deg,rgb(86 117 157) 0%,rgb(54 64 95) 50%,rgb(81 117 165) 100%);
                border-radius:16px;padding:12px 24px;margin:10px 0 20px 0;
                box-shadow:0 6px 16px rgba(0,0,0,0.15);border:1px solid rgba(255,255,255,0.15);">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="background:rgba(255,255,255,0.15);border-radius:50%;width:40px;height:40px;
                            display:flex;align-items:center;justify-content:center;font-size:22px;">📊</div>
                <div>
                    <div style="color:#93c5fd;font-size:11px;font-weight:700;letter-spacing:1.5px;">CURRENT VIEW</div>
                    <div style="color:#ffffff;font-size:18px;font-weight:800;">{hierarchy_display}</div>
                </div>
            </div>
            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="text-align:center;">
                    <div style="color:#93c5fd;font-size:10px;font-weight:600;">TOTAL UNITS</div>
                    <div style="color:#fbbf24;font-size:22px;font-weight:900;">{total_units:,}</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:#93c5fd;font-size:10px;font-weight:600;">AGGREGATION LEVEL</div>
                    <div style="color:#34d399;font-size:14px;font-weight:700;">{level_text}</div>
                </div>
            </div>
        </div>
        <div style="margin-top:10px;height:2px;background:linear-gradient(90deg,transparent,#60a5fa,#fbbf24,transparent);border-radius:2px;"></div>
    </div>"""

# ── SECTION HEADER HELPER ─────────────────────────────────────────────────────
def section_hdr(title, color="#1e3a5f"):
    st.markdown(f"""
    <div style="background:{color};color:#fff;font-size:15px;font-weight:800;
                border-radius:10px;padding:8px 16px;margin:18px 0 10px 0;">
        {title}
    </div>""", unsafe_allow_html=True)

# ── MANAGEMENT INSIGHT BOX ────────────────────────────────────────────────────
def insight_box(text, kind="info"):
    colors = {"info":"#dbeafe:#1e40af", "warn":"#fef9c3:#92400e", "danger":"#fee2e2:#991b1b", "good":"#dcfce7:#166534"}
    bg, fg = colors.get(kind, colors["info"]).split(":")
    st.markdown(f"""
    <div style="background:{bg};border-left:4px solid {fg};border-radius:8px;
                padding:10px 14px;margin:8px 0;color:{fg};font-size:13px;">
        {text}
    </div>""", unsafe_allow_html=True)

# ── RECALCULATE KPIs for any aggregated dataframe ─────────────────────────────
def recalc_kpis(d):
    """Given a df with energy(MU) and finance(Lakhs) cols, recompute all KPIs in-place."""
    d = d.copy()
    inp = d['input_energy_kwh'] if 'input_energy_kwh' in d.columns else None
    sld = d['sold_energy_kwh']  if 'sold_energy_kwh'  in d.columns else None
    ass = d['net_assessment']   if 'net_assessment'   in d.columns else None
    rev = d['revenue_realized'] if 'revenue_realized' in d.columns else None

    if inp is not None and sld is not None:
        d['billing_efficiency_pct'] = np.where(inp > 0, sld / inp * 100, 0)
        d['line_loss_pct']          = np.where(inp > 0, (inp - sld) / inp * 100, 0)
    if ass is not None and rev is not None:
        d['collection_efficiency_pct'] = np.where(ass > 0, rev / ass * 100, 0)
    if 'billing_efficiency_pct' in d.columns and 'collection_efficiency_pct' in d.columns:
        d['atc_loss_pct'] = (100 - d['billing_efficiency_pct'] * d['collection_efficiency_pct'] / 100).clip(0, 100)
    # Rates  — energy in MU, finance in Lakhs  →  ₹/kWh = Lakh/(MU*10)
    if rev is not None and inp is not None:
        d['real_rate'] = np.where(inp > 0, rev / (inp * RATE_FACTOR), 0).round(2)
    if ass is not None and sld is not None:
        d['abr'] = np.where(sld > 0, ass / (sld * RATE_FACTOR), 0).round(2)
    return d

# ── STYLED DATAFRAME DISPLAY ──────────────────────────────────────────────────
def styled_kpi_table(df_in, name_col, title=""):
    cols_order = [name_col, 'input_energy_kwh', 'sold_energy_kwh',
                  'billing_efficiency_pct', 'line_loss_pct',
                  'net_assessment', 'revenue_realized',
                  'collection_efficiency_pct', 'atc_loss_pct',
                  'real_rate', 'abr']
    display_rename = {
        name_col: name_col.title(),
        'input_energy_kwh': 'Input (MU)',
        'sold_energy_kwh': 'Sold (MU)',
        'billing_efficiency_pct': 'Billing Eff %',
        'line_loss_pct': 'Line Loss %',
        'net_assessment': 'Assessment (₹L)',
        'revenue_realized': 'Revenue (₹L)',
        'collection_efficiency_pct': 'Collection %',
        'atc_loss_pct': 'AT&C Loss %',
        'real_rate': 'Real Rate (₹/kWh)',
        'abr': 'ABR (₹/kWh)',
    }
    present = [c for c in cols_order if c in df_in.columns]
    out = df_in[present].copy().rename(columns=display_rename)
    if title:
        st.markdown(f"**{title}**")
    fmt = {}
    for old, new in display_rename.items():
        if new in out.columns:
            if 'MU' in new:    fmt[new] = '{:,.2f}'
            elif '₹L' in new:  fmt[new] = '₹{:,.2f}'
            elif '%' in new:   fmt[new] = '{:.2f}%'
            elif '₹/kWh' in new: fmt[new] = '₹{:.2f}'
    styled = out.style.format(fmt)
    if 'AT&C Loss %' in out.columns:
        styled = styled.background_gradient(subset=['AT&C Loss %'], cmap='RdYlGn_r', vmin=0, vmax=60)
    if 'Line Loss %' in out.columns:
        styled = styled.background_gradient(subset=['Line Loss %'], cmap='OrRd', vmin=0, vmax=40)
    if 'Collection %' in out.columns:
        styled = styled.background_gradient(subset=['Collection %'], cmap='RdYlGn', vmin=60, vmax=100)
    st.dataframe(styled, use_container_width=True, hide_index=True)

# ── SAMPLE CSV GENERATOR ──────────────────────────────────────────────────────
def generate_sample_csv():
    np.random.seed(42)
    zones   = ['East Zone', 'West Zone', 'North Zone', 'South Zone', 'Central Zone']
    circles = {'East Zone':['Varanasi','Mirzapur'], 'West Zone':['Agra','Mathura'],
               'North Zone':['Lucknow','Unnao'], 'South Zone':['Allahabad','Kaushambi'],
               'Central Zone':['Kanpur','Fatehpur']}
    rows = []
    for z in zones:
        for c in circles[z]:
            for d_num in range(1, 4):
                div = f"{c[:3].upper()}-D{d_num}"
                inp = round(np.random.uniform(50, 300), 2)   # MU
                sld = round(inp * np.random.uniform(0.55, 0.92), 2)
                ass = round(sld * np.random.uniform(5.5, 8.5) * RATE_FACTOR, 2)  # Lakhs
                rev = round(ass * np.random.uniform(0.72, 0.97), 2)
                rows.append({'zone': z, 'circle': c, 'division': div,
                             'input_energy_kwh': inp, 'sold_energy_kwh': sld,
                             'net_assessment': ass, 'revenue_realized': rev,
                             'consumers': np.random.randint(8000, 40000),
                             'billed_consumers': np.random.randint(6000, 35000),
                             'paid_consumers': np.random.randint(5000, 30000),
                             'smart_meter_consumers': np.random.randint(500, 8000),
                             'total_outstanding_amount': round(np.random.uniform(100, 2000), 2)})
    return pd.DataFrame(rows)

def create_sample_csv_file():
    df = generate_sample_csv()
    df.to_csv("DVVNL_OVERALL_APRIL26.csv", index=False)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}

ATC_SLABS = [
    {"label": "Below 15%",  "min": -999, "max": 15,   "color": "#22c55e", "bg": "#f0fdf4", "text": "✅ GOOD"},
    {"label": "15% – 30%",  "min": 15,   "max": 30,   "color": "#84cc16", "bg": "#f7fee7", "text": "🟢 OK"},
    {"label": "30% – 50%",  "min": 30,   "max": 50,   "color": "#eab308", "bg": "#fefce8", "text": "⚠️ HIGH"},
    {"label": "50% – 75%",  "min": 50,   "max": 75,   "color": "#f97316", "bg": "#fff7ed", "text": "🟠 CRITICAL"},
    {"label": "Above 75%",  "min": 75,   "max": 9999, "color": "#ef4444", "bg": "#fef2f2", "text": "🔴 SEVERE"},
]


def render():
    """Main render function for DVVNL Overall Performance Dashboard"""

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DVVNL_OVERALL_APRIL26.csv")

    # ── LOAD DATA ─────────────────────────────────────────────────────────────
    @st.cache_data(ttl=600, show_spinner="⚡ Loading DVVNL Overall Data...")
    def load_overall_data():
        if not os.path.exists(csv_path):
            return pd.DataFrame()
        df = pd.read_csv(csv_path)
        df.columns = [c.lower().strip() for c in df.columns]
        col_map = {
            'zone':['zone','zones'], 'circle':['circle','circles'],
            'division':['division','divisions','div_code'],
            'substation':['substation','substation_name'],
            'feeder':['feeder','feeder_name','outgoing_feeder'],
            'input_energy_kwh':['input_energy_kwh','total_input','input_energy','energy_input'],
            'sold_energy_kwh':['sold_energy_kwh','sold_energy','units_sold','billed_energy'],
            'net_assessment':['net_assessment','assessment','total_assessment','current_assessment'],
            'revenue_realized':['revenue_realized','revenue','collection','paid_amount'],
            'consumers':['consumers','total_consumers','operative_consumers'],
            'billed_consumers':['billed_consumers','billed_count'],
            'paid_consumers':['paid_consumers','paid_count'],
            'smart_meter_consumers':['smart_meter_consumers','smart_meters','smart_consumers'],
            'total_outstanding_amount':['total_outstanding_amount','outstanding_amount','outstanding'],
        }
        for target, alts in col_map.items():
            if target not in df.columns:
                for a in alts:
                    if a in df.columns:
                        df[target] = df[a]; break
        df = recalc_kpis(df)
        num_cols = ['input_energy_kwh','sold_energy_kwh','net_assessment','revenue_realized',
                    'consumers','billed_consumers','paid_consumers','smart_meter_consumers',
                    'total_outstanding_amount','billing_efficiency_pct','collection_efficiency_pct',
                    'line_loss_pct','atc_loss_pct','real_rate','abr']
        for c in num_cols:
            if c in df.columns:
                df[c] = df[c].fillna(0)
        return df

    df_raw = load_overall_data()

    if df_raw.empty:
        st.error(f"❌ CSV file not found: {csv_path}")
        st.info("Please create 'DVVNL_OVERALL_APRIL26.csv' with required columns.")
        if st.button("📥 Generate Sample CSV", use_container_width=True):
            df_s = generate_sample_csv()
            df_s.to_csv(csv_path, index=False)
            st.success(f"✅ Sample CSV created at: {csv_path}")
            st.rerun()
        return

    # ── CASCADING FILTER OPTIONS ──────────────────────────────────────────────
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_filter_options():
        zones = sorted(df_raw['zone'].dropna().unique().tolist()) if 'zone' in df_raw.columns else []
        z2c, c2d = {}, {}
        if 'zone' in df_raw.columns and 'circle' in df_raw.columns:
            for z in zones:
                z2c[z] = sorted(df_raw[df_raw['zone']==z]['circle'].dropna().unique().tolist())
        if 'circle' in df_raw.columns and 'division' in df_raw.columns:
            for c in df_raw['circle'].dropna().unique():
                c2d[c] = sorted(df_raw[df_raw['circle']==c]['division'].dropna().unique().tolist())
        return zones, z2c, c2d

    all_zones, zone_to_circles, circle_to_divisions = get_filter_options()

    for k,v in [('ov_filter_zone',"All Zones"),('ov_filter_circle',"All Circles"),('ov_filter_division',"All Divisions")]:
        if k not in st.session_state: st.session_state[k] = v


    # ── HEADER ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,rgb(73 144 192),rgb(141 174 216),rgb(240,249,255));
                border-bottom:2px solid #a5b4fc;padding:14px 20px;border-radius:14px;
                margin-bottom:8px;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#0f172a">
            📊 DVVNL Overall Performance Dashboard</div>
    </div>""", unsafe_allow_html=True)


    # ── FILTERS ───────────────────────────────────────────────────────────────
#    st.markdown('<div style="background:#2c5f8a;color:#fff;font-size:16px;font-weight:800;text-transform:uppercase;border-radius:12px;padding:10px 16px;margin-bottom:2px;text-align:center;">🔧 Filters & Controls</div>', unsafe_allow_html=True)
    col1,col2,col3,col4,col5,col6,col7 = st.columns(7)

    with col1:
        new_zone = st.selectbox("🗺️ Zone", ["All Zones"]+all_zones,
            index=0 if st.session_state.ov_filter_zone=="All Zones"
            else (all_zones.index(st.session_state.ov_filter_zone)+1
                  if st.session_state.ov_filter_zone in all_zones else 0),
            key="ov_zone_cascade")
        if new_zone != st.session_state.ov_filter_zone:
            st.session_state.ov_filter_zone = new_zone
            st.session_state.ov_filter_circle = "All Circles"
            st.session_state.ov_filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.ov_filter_zone = new_zone

    avail_circles = (zone_to_circles.get(st.session_state.ov_filter_zone, [])
                     if st.session_state.ov_filter_zone != "All Zones"
                     else sorted(df_raw['circle'].dropna().unique().tolist()) if 'circle' in df_raw.columns else [])

    with col2:
        new_circle = st.selectbox("🏙️ Circle", ["All Circles"]+avail_circles,
            index=0 if st.session_state.ov_filter_circle=="All Circles"
            else (avail_circles.index(st.session_state.ov_filter_circle)+1
                  if st.session_state.ov_filter_circle in avail_circles else 0),
            key="ov_circle_cascade")
        if new_circle != st.session_state.ov_filter_circle:
            st.session_state.ov_filter_circle = new_circle
            st.session_state.ov_filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.ov_filter_circle = new_circle

    if st.session_state.ov_filter_circle != "All Circles":
        avail_divs = circle_to_divisions.get(st.session_state.ov_filter_circle, [])
    elif st.session_state.ov_filter_zone != "All Zones":
        avail_divs = sorted(df_raw[df_raw['zone']==st.session_state.ov_filter_zone]['division'].dropna().unique().tolist()) if 'division' in df_raw.columns else []
    else:
        avail_divs = sorted(df_raw['division'].dropna().unique().tolist()) if 'division' in df_raw.columns else []

    with col3:
        new_div = st.selectbox("🏢 Division", ["All Divisions"]+avail_divs,
            index=0 if st.session_state.ov_filter_division=="All Divisions"
            else (avail_divs.index(st.session_state.ov_filter_division)+1
                  if st.session_state.ov_filter_division in avail_divs else 0),
            key="ov_division_cascade")
        st.session_state.ov_filter_division = new_div

    with col4:
        level_filter = st.selectbox("📌 View By", ["Zone","Circle","Division","Feeder/Substation"], key="ov_level")

    with col5:
        sort_options = {
            "AT&C Loss %":"atc_loss_pct", "Billing Efficiency %":"billing_efficiency_pct",
            "Collection Efficiency %":"collection_efficiency_pct", "Line Loss %":"line_loss_pct",
            "Real Rate (₹/KWH)":"real_rate", "ABR (₹/KWH)":"abr",
            "Input Energy (MU)":"input_energy_kwh", "Revenue (₹L)":"revenue_realized"
        }
        sort_col_label = st.selectbox("📊 Sort By", list(sort_options.keys()), key="ov_sort")
        sort_col = sort_options[sort_col_label]

    with col6:
        sort_asc = st.toggle("📈 Ascending", False, key="ov_asc")

    with col7:
        if st.button("🔄 Refresh Data", use_container_width=True, key="ov_refresh"):
            st.cache_data.clear(); st.rerun()

    zone_filter     = st.session_state.ov_filter_zone
    circle_filter   = st.session_state.ov_filter_circle
    division_filter = st.session_state.ov_filter_division

    # ── APPLY FILTERS ─────────────────────────────────────────────────────────
    df = df_raw.copy()
    if zone_filter     != "All Zones"     and 'zone'     in df.columns: df = df[df['zone']     == zone_filter]
    if circle_filter   != "All Circles"   and 'circle'   in df.columns: df = df[df['circle']   == circle_filter]
    if division_filter != "All Divisions" and 'division' in df.columns: df = df[df['division'] == division_filter]

    # ── LEVEL GROUPING ────────────────────────────────────────────────────────
    lvl_map = {"Zone":"zone","Circle":"circle","Division":"division","Feeder/Substation":None}
    group_col   = lvl_map.get(level_filter)
    if group_col and group_col not in df.columns: group_col = None
    group_label = level_filter if group_col else "Unit"

    SUM_COLS = ['input_energy_kwh','sold_energy_kwh','net_assessment','revenue_realized',
                'consumers','billed_consumers','paid_consumers','smart_meter_consumers','total_outstanding_amount']
    present_sum = [c for c in SUM_COLS if c in df.columns]

    if group_col:
        count_src = 'feeder' if 'feeder' in df.columns else ('substation' if 'substation' in df.columns else group_col)
        df_agg = df.groupby(group_col).agg(**{c:pd.NamedAgg(column=c,aggfunc='sum') for c in present_sum},
                                            unit_count=pd.NamedAgg(column=count_src,aggfunc='count')).reset_index()
        df_agg = recalc_kpis(df_agg)
        display_df = df_agg
    else:
        display_df = df.copy()

    if sort_col in display_df.columns:
        display_df = display_df.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

    # ── GRAND TOTALS ──────────────────────────────────────────────────────────
    total_input      = float(df['input_energy_kwh'].sum())      if 'input_energy_kwh'      in df.columns else 0
    total_sold       = float(df['sold_energy_kwh'].sum())       if 'sold_energy_kwh'       in df.columns else 0
    total_assessment = float(df['net_assessment'].sum())        if 'net_assessment'        in df.columns else 0
    total_revenue    = float(df['revenue_realized'].sum())      if 'revenue_realized'      in df.columns else 0
    total_consumers  = int(df['consumers'].sum())               if 'consumers'             in df.columns else 0
    total_billed     = int(df['billed_consumers'].sum())        if 'billed_consumers'      in df.columns else 0
    total_paid       = int(df['paid_consumers'].sum())          if 'paid_consumers'        in df.columns else 0
    total_smart      = int(df['smart_meter_consumers'].sum())   if 'smart_meter_consumers' in df.columns else 0
    total_outstanding= float(df['total_outstanding_amount'].sum()) if 'total_outstanding_amount' in df.columns else 0

    be_gt = total_sold   / total_input      if total_input      > 0 else 0
    ce_gt = total_revenue/ total_assessment if total_assessment > 0 else 0

    gt = {
        "atc_loss_pct":              round((1 - be_gt * ce_gt) * 100, 2),
        "billing_efficiency_pct":    round(be_gt * 100, 2),
        "collection_efficiency_pct": round(ce_gt * 100, 2),
        "line_loss_pct":             round((total_input - total_sold) / total_input * 100, 2) if total_input > 0 else 0,
        "input_energy_kwh":          total_input,
        "sold_energy_kwh":           total_sold,
        "net_assessment":            total_assessment,
        "revenue_realized":          total_revenue,
        "consumers":                 total_consumers,
        "billed_consumers":          total_billed,
        "paid_consumers":            total_paid,
        "smart_meter_consumers":     total_smart,
        "total_outstanding_amount":  total_outstanding,
        "real_rate":                 round(total_revenue / (total_input * RATE_FACTOR), 2) if total_input > 0 else 0,
        "abr":                       round(total_assessment / (total_sold * RATE_FACTOR), 2) if total_sold > 0 else 0,
    }
    total_units = len(display_df)

    def get_current_hierarchy():
        parts = []
        if zone_filter     != "All Zones":     parts.append(zone_filter)
        if circle_filter   != "All Circles":   parts.append(circle_filter)
        if division_filter != "All Divisions": parts.append(division_filter)
        return " → ".join(parts) if parts else "DVVNL (All Units)"

    current_hierarchy = get_current_hierarchy()

    # ── PRE-AGGREGATE helpers for zone/circle/division level tables ────────────
    def agg_level(grp_cols):
        d = df.groupby(grp_cols).agg(**{c:pd.NamedAgg(column=c,aggfunc='sum') for c in present_sum}).reset_index()
        return recalc_kpis(d)

    zone_df     = agg_level(['zone'])               if 'zone'     in df.columns else pd.DataFrame()
    circle_df   = agg_level(['zone','circle'])       if all(c in df.columns for c in ['zone','circle']) else pd.DataFrame()
    division_df = agg_level(['zone','circle','division']) if all(c in df.columns for c in ['zone','circle','division']) else pd.DataFrame()

    st.markdown(build_hierarchy_header(zone_filter, circle_filter, division_filter, level_filter, total_units), unsafe_allow_html=True)

    # ── KPI CARDS ─────────────────────────────────────────────────────────────
    st.markdown(f'<div style="background:#4c89b4;color:#fff;font-size:16px;font-weight:800;text-transform:uppercase;border-radius:12px;padding:10px 16px;margin-bottom:14px;text-align:center;">📈 {current_hierarchy} — Key Performance Indicators</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    for col,lbl,val,unit,color,sub in [
        (c1,"AT&C Loss",    f"{gt.get('atc_loss_pct',0):.2f}",             "%",           atc_color(gt.get('atc_loss_pct',0)), "Target <15%"),
        (c2,"Billing Eff",  f"{gt.get('billing_efficiency_pct',0):.2f}",   "%",           "#0D692F",  "Sold/Input"),
        (c3,"Coll Eff",     f"{gt.get('collection_efficiency_pct',0):.2f}","%",           "#0A3F94",  "Rev/Assess"),
        (c4,"Line Loss",    f"{gt.get('line_loss_pct',0):.2f}",            "%",           "#6d350e",  "Technical"),
        (c5,"Input Energy", f"{gt.get('input_energy_kwh',0):.2f}",         "MU",          "#1725A5",  "Million Units"),
        (c6,"Sold Energy",  f"{gt.get('sold_energy_kwh',0):.2f}",          "MU",          "#197553",  "Million Units"),
        (c7,"Assessment",   f"{gt.get('net_assessment',0)/LAKH_TO_CR:.2f}","₹ Cr",        "#700c8e",  "Lakhs÷100"),
    ]:
        with col: kpi_card(lbl, val, unit, color=color, sub=sub)

    e1,e2,e3,e4,e5,e6,e7 = st.columns(7)
    for col,lbl,val,color,sub in [
        (e1,"Revenue",      f"{gt.get('revenue_realized',0)/LAKH_TO_CR:.2f}", "#105a67", "₹ In Cr."),
        (e2,"Real Rate",    f"₹{gt.get('real_rate',0):.2f}",                  "#700c8e", "Rev/Input(₹/kWh)"),
        (e3,"ABR",          f"₹{gt.get('abr',0):.2f}",                        "#0891b2", "Assess/Sold(₹/kWh)"),
        (e4,"Billed",       fmt_lakh(gt.get('billed_consumers',0)),            "#0c6343", "Customers"),
        (e5,"Paid",         fmt_lakh(gt.get('paid_consumers',0)),              "#06525f", "Customers"),
        (e6,"Smart Meters", fmt_lakh(gt.get('smart_meter_consumers',0)),       "#36118C", "Installed"),
        (e7, "Outstanding", f"{gt.get('total_outstanding_amount', 0) / 10000000:.2f}", "#7e0d0d", "₹ In Cr."),
    ]:
        with col: kpi_card(lbl, val, "", color=color, sub=sub)

    # ── CRITICAL ALERTS ───────────────────────────────────────────────────────
    if 'atc_loss_pct' in display_df.columns:
        critical = display_df[display_df['atc_loss_pct'] >= 50]
        if not critical.empty:
            with st.expander(f"🔴 {len(critical)} CRITICAL {group_label}s (AT&C ≥ 50%)", expanded=False):
                for _, row in critical.iterrows():
                    cols = st.columns([2,1,1,1])
                    with cols[0]: st.markdown(f"**{row.get(group_col,'?')}**")
                    with cols[1]: st.markdown(f"<span style='color:#ef4444;font-weight:800'>AT&C: {row.get('atc_loss_pct',0):.1f}%</span>",unsafe_allow_html=True)
                    with cols[2]: st.markdown(f"<span style='color:#f97316'>BE: {row.get('billing_efficiency_pct',0):.1f}%</span>",unsafe_allow_html=True)
                    with cols[3]: st.markdown(f"<span style='color:#fbbf24'>CE: {row.get('collection_efficiency_pct',0):.1f}%</span>",unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TABS
    # ══════════════════════════════════════════════════════════════════════════
    tabs = st.tabs([
        "📊 Overview",
        "🔴 AT&C Analysis",
        "⚡ Energy & Line Loss",
        "💰 Revenue & Collection",
        "💹 ABR & Through Rate",
        "🏆 Rankings",
        "📐 Slab Analysis",
        "📋 Data & Export"
    ])

    # ══ TAB 0: OVERVIEW ═══════════════════════════════════════════════════════
    with tabs[0]:
        section_hdr(f"📊 {current_hierarchy} — {group_label}-wise KPI Comparison")

        if not display_df.empty and group_col and group_col in display_df.columns:
            fig = go.Figure()
            for col_name,label,color in [
                ("atc_loss_pct","AT&C %","#ef4444"),
                ("billing_efficiency_pct","Billing Eff %","#22c55e"),
                ("collection_efficiency_pct","Coll Eff %","#3b82f6")
            ]:
                if col_name in display_df.columns:
                    fig.add_trace(go.Bar(name=label, x=display_df[group_col], y=display_df[col_name],
                                         marker_color=color, text=display_df[col_name].round(1), textposition="outside"))
            fig.update_layout(**dark_layout(barmode="group", height=460))
            st.plotly_chart(fig, use_container_width=True, key="ov_overview_bar", config=PLOTLY_CONFIG)

        # ── Hierarchical Tables (Zone → Circle → Division) ────────────────────
        section_hdr("🌳 Hierarchical Summary Tables — Zone | Circle | Division")
        insight_box("📌 These tables give the complete performance picture at each level for review.", "info")

        with st.expander("🔍 View Sample Raw Data (First 10 rows)", expanded=False):
            preview_cols = [c for c in ['zone','circle','division','input_energy_kwh','sold_energy_kwh','net_assessment','revenue_realized'] if c in df.columns]
            st.dataframe(df[preview_cols].head(10), use_container_width=True)

        if not zone_df.empty:
            styled_kpi_table(zone_df, 'zone', "📍 Zone-wise Summary")
            st.markdown("---")
        if not circle_df.empty:
            styled_kpi_table(circle_df.rename(columns={'zone':'zone','circle':'circle'}), 'circle', "🏙️ Circle-wise Summary")
            st.markdown("---")
        if not division_df.empty:
            styled_kpi_table(division_df, 'division', "🏢 Division-wise Summary")

        # Download buttons
        section_hdr("📥 Download Hierarchy Data")
        d1,d2,d3 = st.columns(3)
        if not zone_df.empty:
            with d1:
                st.download_button("📥 Zone Data (CSV)", zone_df.to_csv(index=False).encode(),
                    f"DVVNL_Zone_{datetime.now().strftime('%Y%m%d')}.csv","text/csv", use_container_width=True)
        if not circle_df.empty:
            with d2:
                st.download_button("📥 Circle Data (CSV)", circle_df.to_csv(index=False).encode(),
                    f"DVVNL_Circle_{datetime.now().strftime('%Y%m%d')}.csv","text/csv", use_container_width=True)
        if not division_df.empty:
            with d3:
                st.download_button("📥 Division Data (CSV)", division_df.to_csv(index=False).encode(),
                    f"DVVNL_Division_{datetime.now().strftime('%Y%m%d')}.csv","text/csv", use_container_width=True)


    # ══ TAB 1: AT&C ANALYSIS ══════════════════════════════════════════════════
    with tabs[1]:
        section_hdr(f"🔴 AT&C Loss Deep-Dive — {current_hierarchy} ({group_label} Level)")

        insight_box(
            f"📌 <b>Note:</b> AT&C = 100 − (Billing Efficiency × Collection Efficiency / 100). "
            f"Overall AT&C = <b>{gt['atc_loss_pct']:.2f}%</b> | "
            f"Billing Eff = {gt['billing_efficiency_pct']:.2f}% | Collection Eff = {gt['collection_efficiency_pct']:.2f}%",
            "warn" if gt['atc_loss_pct'] > 30 else "good"
        )

        # AT&C Distribution + Worst
        col1, col2 = st.columns(2)
        with col1:
            if 'atc_loss_pct' in display_df.columns:
                bins   = [0,15,30,50,75,100]
                labels = ["0-15% (Good)","15-30% (OK)","30-50% (High)","50-75% (Critical)","75-100% (Severe)"]
                display_df['atc_bin'] = pd.cut(display_df['atc_loss_pct'], bins=bins, labels=labels, include_lowest=True)
                bc = display_df['atc_bin'].value_counts().reindex(labels, fill_value=0)
                fig_dist = go.Figure(go.Bar(x=bc.index, y=bc.values,
                    marker_color=['#22c55e','#84cc16','#eab308','#f97316','#ef4444'],
                    text=bc.values, textposition="outside"))
                fig_dist.update_layout(**dark_layout(title=f"{group_label} Distribution by AT&C Slab", showlegend=False, height=420))
                st.plotly_chart(fig_dist, use_container_width=True, key="ov_atc_dist", config=PLOTLY_CONFIG)

        with col2:
            if 'atc_loss_pct' in display_df.columns and group_col and group_col in display_df.columns:
                worst10 = display_df.nlargest(10, 'atc_loss_pct')
                fig_w = go.Figure(go.Bar(y=worst10[group_col], x=worst10['atc_loss_pct'],
                    orientation='h', marker_color='#ef4444',
                    text=worst10['atc_loss_pct'].round(1), textposition="outside"))
                fig_w.update_layout(**dark_layout(title=f"Top 10 Worst {group_label}s — AT&C Loss", height=420,
                                                   xaxis_title="AT&C Loss %"))
                st.plotly_chart(fig_w, use_container_width=True, key="ov_atc_worst", config=PLOTLY_CONFIG)

        # ── Zone Level AT&C Analysis ──────────────────────────────────────────
        if not zone_df.empty:
            section_hdr("🗺️ Zone-wise AT&C Analysis", "#1e3a5f")
            cols = st.columns(2)
            with cols[0]:
                fig_z = px.bar(zone_df.sort_values('atc_loss_pct',ascending=False),
                               x='zone', y='atc_loss_pct',
                               color='atc_loss_pct', color_continuous_scale='RdYlGn_r',
                               text=zone_df.sort_values('atc_loss_pct',ascending=False)['atc_loss_pct'].round(2),
                               title="Zone-wise AT&C Loss %")
                fig_z.add_hline(y=15, line_dash="dash", line_color="#22c55e", annotation_text="15% Target")
                fig_z.update_traces(textposition="outside")
                fig_z.update_layout(**dark_layout(showlegend=False, height=400))
                st.plotly_chart(fig_z, use_container_width=True, key="z_atc_bar", config=PLOTLY_CONFIG)
            with cols[1]:
                # BE vs CE scatter per zone
                fig_scatter = px.scatter(zone_df, x='billing_efficiency_pct', y='collection_efficiency_pct',
                    size='atc_loss_pct', color='atc_loss_pct', color_continuous_scale='RdYlGn_r',
                    text='zone', title="Zone: Billing Eff vs Collection Eff (size=AT&C)")
                fig_scatter.update_traces(textposition="top center")
                fig_scatter.update_layout(**dark_layout(height=400, xaxis_title="Billing Eff %", yaxis_title="Collection Eff %"))
                st.plotly_chart(fig_scatter, use_container_width=True, key="z_atc_scatter", config=PLOTLY_CONFIG)

            # Zone-wise stacked components
            fig_comp = go.Figure()
            zs = zone_df.sort_values('atc_loss_pct', ascending=False)
            fig_comp.add_trace(go.Bar(name="Line Loss %",       x=zs['zone'], y=zs['line_loss_pct'],       marker_color="#ef4444"))
            fig_comp.add_trace(go.Bar(name="Collection Loss %", x=zs['zone'],
                                      y=(100 - zs['collection_efficiency_pct']).clip(0),  marker_color="#f97316"))
            fig_comp.update_layout(**dark_layout(barmode="stack", title="Zone: AT&C Loss Components (Line Loss + Collection Loss)",
                                                  height=380, yaxis_title="Loss %"))
            st.plotly_chart(fig_comp, use_container_width=True, key="z_atc_comp", config=PLOTLY_CONFIG)
            styled_kpi_table(zone_df, 'zone')

        # ── Circle Level AT&C Analysis ────────────────────────────────────────
        if not circle_df.empty:
            section_hdr("🏙️ Circle-wise AT&C Analysis", "#1e3a5f")
            fig_c = px.bar(circle_df.sort_values('atc_loss_pct', ascending=False),
                           x='circle', y='atc_loss_pct',
                           color='atc_loss_pct', color_continuous_scale='RdYlGn_r',
                           text=circle_df.sort_values('atc_loss_pct', ascending=False)['atc_loss_pct'].round(2),
                           title="Circle-wise AT&C Loss %")
            fig_c.add_hline(y=15, line_dash="dash", line_color="#22c55e", annotation_text="15% Target")
            fig_c.update_traces(textposition="outside")
            fig_c.update_layout(**dark_layout(showlegend=False, height=420))
            st.plotly_chart(fig_c, use_container_width=True, key="c_atc_bar", config=PLOTLY_CONFIG)

            # Circle grouped by zone
            if 'zone' in circle_df.columns:
                fig_cg = px.bar(circle_df.sort_values(['zone','atc_loss_pct'], ascending=[True,False]),
                                x='circle', y='atc_loss_pct', color='zone',
                                barmode='group', title="Circle AT&C Loss — Grouped by Zone",
                                text=circle_df.sort_values(['zone','atc_loss_pct'],ascending=[True,False])['atc_loss_pct'].round(1))
                fig_cg.update_traces(textposition="outside")
                fig_cg.update_layout(**dark_layout(height=420))
                st.plotly_chart(fig_cg, use_container_width=True, key="c_atc_grp", config=PLOTLY_CONFIG)
            styled_kpi_table(circle_df, 'circle')

        # ── Division Level AT&C ───────────────────────────────────────────────
        if not division_df.empty:
            section_hdr("🏢 Division-wise AT&C Analysis", "#1e3a5f")
            top_n_atc = st.slider("Show Top N Divisions by AT&C", 5, min(50, len(division_df)), min(20, len(division_df)), key="atc_div_n")
            worst_div = division_df.nlargest(top_n_atc, 'atc_loss_pct')
            fig_d = px.bar(worst_div, y='division', x='atc_loss_pct', orientation='h',
                           color='atc_loss_pct', color_continuous_scale='RdYlGn_r',
                           text=worst_div['atc_loss_pct'].round(2),
                           title=f"Top {top_n_atc} Divisions — Highest AT&C Loss %")
            fig_d.update_traces(textposition="outside")
            fig_d.update_layout(**dark_layout(showlegend=False, height=max(400, top_n_atc*26)))
            st.plotly_chart(fig_d, use_container_width=True, key="d_atc_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(division_df, 'division')


    # ══ TAB 2: ENERGY & LINE LOSS ══════════════════════════════════════════════
    with tabs[2]:
        section_hdr(f"⚡ Energy & Line Loss Analysis — {current_hierarchy} ({group_label} Level)")

        insight_box(
            f"📌 <b>Note:</b> Total Input = <b>{gt['input_energy_kwh']:.2f} MU</b> | "
            f"Total Sold = <b>{gt['sold_energy_kwh']:.2f} MU</b> | "
            f"Line Loss = <b>{gt['line_loss_pct']:.2f}%</b>. "
            f"Energy lost = {gt['input_energy_kwh']-gt['sold_energy_kwh']:.2f} MU = ₹"
            f"{(gt['input_energy_kwh']-gt['sold_energy_kwh'])*RATE_FACTOR*gt.get('abr',0)/LAKH_TO_CR:.2f} Cr approx.",
            "warn" if gt['line_loss_pct'] > 20 else "good"
        )

        col1, col2 = st.columns(2)
        with col1:
            if group_col and group_col in display_df.columns:
                fig_e = go.Figure()
                fig_e.add_trace(go.Bar(name="Input (MU)", x=display_df[group_col], y=display_df['input_energy_kwh'], marker_color="#6366f1"))
                fig_e.add_trace(go.Bar(name="Sold (MU)",  x=display_df[group_col], y=display_df['sold_energy_kwh'],  marker_color="#22c55e"))
                fig_e.update_layout(**dark_layout(barmode="group", yaxis_title="Energy (MU)", height=430,
                                                   title=f"{group_label}: Input vs Sold Energy"))
                st.plotly_chart(fig_e, use_container_width=True, key="ov_energy_compare", config=PLOTLY_CONFIG)

        with col2:
            if group_col and group_col in display_df.columns and 'line_loss_pct' in display_df.columns:
                fig_ll = px.bar(display_df, x=group_col, y='line_loss_pct',
                                color='line_loss_pct',
                                color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                                text=display_df['line_loss_pct'].round(1),
                                title=f"{group_label}: Line Loss %")
                fig_ll.update_traces(textposition="outside")
                fig_ll.update_layout(**dark_layout(showlegend=False, height=430))
                st.plotly_chart(fig_ll, use_container_width=True, key="ov_line_loss", config=PLOTLY_CONFIG)

        # ── Zone Energy & Line Loss ───────────────────────────────────────────
        if not zone_df.empty:
            section_hdr("🗺️ Zone-wise Energy & Line Loss", "#1e3a5f")
            cols = st.columns(2)
            with cols[0]:
                fig_ze = go.Figure()
                fig_ze.add_trace(go.Bar(name="Input (MU)", x=zone_df['zone'], y=zone_df['input_energy_kwh'], marker_color="#6366f1",
                                        text=zone_df['input_energy_kwh'].round(2), textposition="outside"))
                fig_ze.add_trace(go.Bar(name="Sold (MU)",  x=zone_df['zone'], y=zone_df['sold_energy_kwh'],  marker_color="#22c55e",
                                        text=zone_df['sold_energy_kwh'].round(2), textposition="outside"))
                fig_ze.update_layout(**dark_layout(barmode="group", title="Zone: Input vs Sold Energy (MU)", height=400, yaxis_title="MU"))
                st.plotly_chart(fig_ze, use_container_width=True, key="ze_bar", config=PLOTLY_CONFIG)
            with cols[1]:
                fig_zll = px.funnel_area(names=zone_df['zone'], values=zone_df['line_loss_pct'],
                                          title="Zone: Line Loss % (Funnel)")
                fig_zll.update_layout(**dark_layout(height=400))
                st.plotly_chart(fig_zll, use_container_width=True, key="zll_funnel", config=PLOTLY_CONFIG)

            zone_loss_val = zone_df.copy()
            zone_loss_val['energy_lost_mu'] = zone_loss_val['input_energy_kwh'] - zone_loss_val['sold_energy_kwh']
            zone_loss_val['revenue_loss_cr'] = (zone_loss_val['energy_lost_mu'] * RATE_FACTOR * zone_loss_val['abr'] / LAKH_TO_CR).round(2)
            insight_box(f"💡 Zone with highest energy loss: <b>{zone_loss_val.nlargest(1,'energy_lost_mu')['zone'].values[0]}</b> — "
                        f"{zone_loss_val.nlargest(1,'energy_lost_mu')['energy_lost_mu'].values[0]:.2f} MU lost", "warn")
            styled_kpi_table(zone_df[['zone','input_energy_kwh','sold_energy_kwh','line_loss_pct','billing_efficiency_pct']], 'zone')

        # ── Circle Energy ─────────────────────────────────────────────────────
        if not circle_df.empty:
            section_hdr("🏙️ Circle-wise Energy & Line Loss", "#1e3a5f")
            fig_ce = px.bar(circle_df.sort_values('line_loss_pct',ascending=False),
                            x='circle', y='line_loss_pct',
                            color='line_loss_pct', color_continuous_scale='OrRd',
                            text=circle_df.sort_values('line_loss_pct',ascending=False)['line_loss_pct'].round(2),
                            title="Circle-wise Line Loss %")
            fig_ce.update_traces(textposition="outside")
            fig_ce.update_layout(**dark_layout(showlegend=False, height=420))
            st.plotly_chart(fig_ce, use_container_width=True, key="ce_ll", config=PLOTLY_CONFIG)
            styled_kpi_table(circle_df[['zone','circle','input_energy_kwh','sold_energy_kwh','line_loss_pct','billing_efficiency_pct']], 'circle')

        # ── Division Energy ────────────────────────────────────────────────────
        if not division_df.empty:
            section_hdr("🏢 Division-wise Energy & Line Loss", "#1e3a5f")
            top_n_ll = st.slider("Show Top N Divisions by Line Loss", 5, min(50,len(division_df)), min(20,len(division_df)), key="ll_div_n")
            worst_ll = division_df.nlargest(top_n_ll, 'line_loss_pct')
            fig_dll = px.bar(worst_ll, y='division', x='line_loss_pct', orientation='h',
                             color='line_loss_pct', color_continuous_scale='OrRd',
                             text=worst_ll['line_loss_pct'].round(2),
                             title=f"Top {top_n_ll} Divisions — Highest Line Loss %")
            fig_dll.update_traces(textposition="outside")
            fig_dll.update_layout(**dark_layout(showlegend=False, height=max(400,top_n_ll*26)))
            st.plotly_chart(fig_dll, use_container_width=True, key="dll_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(division_df[['zone','circle','division','input_energy_kwh','sold_energy_kwh','line_loss_pct','billing_efficiency_pct']], 'division')


    # ══ TAB 3: REVENUE & COLLECTION ════════════════════════════════════════════
    with tabs[3]:
        section_hdr(f"💰 Revenue & Collection Efficiency — {current_hierarchy} ({group_label} Level)")

        rev_gap = total_assessment - total_revenue
        insight_box(
            f"📌 <b>Note:</b> Total Assessment = ₹{total_assessment/LAKH_TO_CR:.2f} Cr | "
            f"Revenue Realized = ₹{total_revenue/LAKH_TO_CR:.2f} Cr | "
            f"Collection Eff = <b>{gt['collection_efficiency_pct']:.2f}%</b> | "
            f"Revenue Gap = ₹{rev_gap/LAKH_TO_CR:.2f} Cr",
            "warn" if gt['collection_efficiency_pct'] < 85 else "good"
        )

        col1, col2 = st.columns(2)
        with col1:
            if group_col and group_col in display_df.columns and 'collection_efficiency_pct' in display_df.columns:
                fig_ce2 = px.bar(display_df, x=group_col, y='collection_efficiency_pct',
                                 color='collection_efficiency_pct',
                                 color_continuous_scale=[[0,"#ef4444"],[0.5,"#f97316"],[1,"#22c55e"]],
                                 text=display_df['collection_efficiency_pct'].round(1),
                                 title=f"{group_label}: Collection Efficiency %")
                fig_ce2.add_hline(y=90, line_dash="dash", line_color="#22c55e", annotation_text="90% Target")
                fig_ce2.update_traces(textposition="outside")
                fig_ce2.update_layout(**dark_layout(showlegend=False, height=430))
                st.plotly_chart(fig_ce2, use_container_width=True, key="ov_collection_eff", config=PLOTLY_CONFIG)

        with col2:
            if group_col and group_col in display_df.columns:
                fig_rev2 = go.Figure()
                if 'net_assessment' in display_df.columns:
                    fig_rev2.add_trace(go.Bar(name="Assessment (₹Cr)", x=display_df[group_col],
                                              y=display_df['net_assessment']/LAKH_TO_CR, marker_color="#fbbf24",
                                              text=(display_df['net_assessment']/LAKH_TO_CR).round(1), textposition="outside"))
                if 'revenue_realized' in display_df.columns:
                    fig_rev2.add_trace(go.Bar(name="Revenue (₹Cr)", x=display_df[group_col],
                                              y=display_df['revenue_realized']/LAKH_TO_CR, marker_color="#22c55e",
                                              text=(display_df['revenue_realized']/LAKH_TO_CR).round(1), textposition="outside"))
                fig_rev2.update_layout(**dark_layout(barmode="group", yaxis_title="Amount (₹ Crores)", height=430,
                                                      title=f"{group_label}: Assessment vs Revenue"))
                st.plotly_chart(fig_rev2, use_container_width=True, key="ov_rev_compare", config=PLOTLY_CONFIG)

        # Outstanding
        if 'total_outstanding_amount' in display_df.columns and group_col and group_col in display_df.columns:
            section_hdr(f"⚠️ Outstanding Amount — {group_label} Level")
            top_out = display_df.nlargest(10,'total_outstanding_amount').copy()
            fig_out = px.bar(top_out, x=group_col, y=top_out['total_outstanding_amount']/10000000,
                             color=top_out['total_outstanding_amount'],
                             color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                             text=top_out['total_outstanding_amount'].apply(lambda x: f"₹{x/10000000:.2f}Cr"),
                             title="Top 10 by Outstanding Amount")
            fig_out.update_traces(textposition="outside")
            fig_out.update_layout(**dark_layout(showlegend=False, yaxis_title="Outstanding (₹ Crores)", height=420))
            st.plotly_chart(fig_out, use_container_width=True, key="ov_outstanding", config=PLOTLY_CONFIG)

        # ── Zone Collection ────────────────────────────────────────────────────
        if not zone_df.empty:
            section_hdr("🗺️ Zone-wise Revenue & Collection Analysis", "#1e3a5f")
            cols = st.columns(2)
            with cols[0]:
                fig_zce = px.bar(zone_df.sort_values('collection_efficiency_pct',ascending=True),
                                 y='zone', x='collection_efficiency_pct', orientation='h',
                                 color='collection_efficiency_pct',
                                 color_continuous_scale=[[0,"#ef4444"],[0.5,"#f97316"],[1,"#22c55e"]],
                                 text=zone_df.sort_values('collection_efficiency_pct',ascending=True)['collection_efficiency_pct'].round(2),
                                 title="Zone: Collection Efficiency %")
                fig_zce.add_vline(x=90, line_dash="dash", line_color="#22c55e", annotation_text="90%")
                fig_zce.update_traces(textposition="outside")
                fig_zce.update_layout(**dark_layout(showlegend=False, height=380, xaxis_title="Collection %"))
                st.plotly_chart(fig_zce, use_container_width=True, key="zce_bar", config=PLOTLY_CONFIG)
            with cols[1]:
                zr = zone_df.copy()
                zr['gap_cr'] = (zr['net_assessment'] - zr['revenue_realized']) / LAKH_TO_CR
                fig_zgap = px.bar(zr.sort_values('gap_cr',ascending=False), x='zone', y='gap_cr',
                                  color='gap_cr', color_continuous_scale='Reds',
                                  text=zr.sort_values('gap_cr',ascending=False)['gap_cr'].round(2),
                                  title="Zone: Revenue Gap (Assessment − Revenue) ₹ Cr")
                fig_zgap.update_traces(textposition="outside")
                fig_zgap.update_layout(**dark_layout(showlegend=False, height=380, yaxis_title="Gap (₹ Cr)"))
                st.plotly_chart(fig_zgap, use_container_width=True, key="zgap_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(zone_df[['zone','net_assessment','revenue_realized','collection_efficiency_pct','total_outstanding_amount'] if 'total_outstanding_amount' in zone_df.columns else ['zone','net_assessment','revenue_realized','collection_efficiency_pct']], 'zone')

        # ── Circle Collection ──────────────────────────────────────────────────
        if not circle_df.empty:
            section_hdr("🏙️ Circle-wise Revenue & Collection Analysis", "#1e3a5f")
            fig_cce = px.bar(circle_df.sort_values('collection_efficiency_pct',ascending=False),
                             x='circle', y='collection_efficiency_pct',
                             color='collection_efficiency_pct',
                             color_continuous_scale=[[0,"#ef4444"],[0.5,"#f97316"],[1,"#22c55e"]],
                             text=circle_df.sort_values('collection_efficiency_pct',ascending=False)['collection_efficiency_pct'].round(2),
                             title="Circle: Collection Efficiency %")
            fig_cce.add_hline(y=90, line_dash="dash", line_color="#22c55e", annotation_text="90% Target")
            fig_cce.update_traces(textposition="outside")
            fig_cce.update_layout(**dark_layout(showlegend=False, height=420))
            st.plotly_chart(fig_cce, use_container_width=True, key="cce_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(circle_df[['zone','circle','net_assessment','revenue_realized','collection_efficiency_pct']], 'circle')

        # ── Division Collection ────────────────────────────────────────────────
        if not division_df.empty:
            section_hdr("🏢 Division-wise Collection Analysis", "#1e3a5f")
            top_n_ce = st.slider("Show Top N Divisions by Collection Efficiency (Lowest)", 5, min(50,len(division_df)), min(20,len(division_df)), key="ce_div_n")
            worst_ce = division_df.nsmallest(top_n_ce, 'collection_efficiency_pct')
            fig_dce = px.bar(worst_ce, y='division', x='collection_efficiency_pct', orientation='h',
                             color='collection_efficiency_pct',
                             color_continuous_scale=[[0,"#ef4444"],[0.5,"#f97316"],[1,"#22c55e"]],
                             text=worst_ce['collection_efficiency_pct'].round(2),
                             title=f"Bottom {top_n_ce} Divisions — Lowest Collection Efficiency %")
            fig_dce.update_traces(textposition="outside")
            fig_dce.update_layout(**dark_layout(showlegend=False, height=max(400,top_n_ce*26)))
            st.plotly_chart(fig_dce, use_container_width=True, key="dce_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(division_df[['zone','circle','division','net_assessment','revenue_realized','collection_efficiency_pct']], 'division')


    # ══ TAB 4: ABR & THROUGH RATE ══════════════════════════════════════════
    with tabs[4]:
        section_hdr(f"💹 ABR & Through (Real) Rate Analysis — {current_hierarchy}")

        insight_box(
            f"📌 <b>ABR (Average Billing Rate)</b> = Assessment (₹L) ÷ (Sold Energy (MU) × 10)  →  ₹/kWh billed. "
            f"&nbsp;&nbsp;<b>Through/Real Rate</b> = Revenue (₹L) ÷ (Input Energy (MU) × 10)  →  ₹ actually recovered per kWh input. "
            f"<br>Overall ABR = <b>₹{gt['abr']:.2f}/kWh</b> | Real Rate = <b>₹{gt['real_rate']:.2f}/kWh</b> | "
            f"Rate Gap = ₹{gt['abr']-gt['real_rate']:.2f}/kWh",
            "warn" if (gt['abr'] - gt['real_rate']) > 1.0 else "good"
        )

        col1, col2 = st.columns(2)
        with col1:
            if group_col and group_col in display_df.columns and 'abr' in display_df.columns:
                fig_abr = px.bar(display_df.sort_values('abr',ascending=False), x=group_col, y='abr',
                                 color='abr', color_continuous_scale='Blues',
                                 text=display_df.sort_values('abr',ascending=False)['abr'].round(2),
                                 title=f"{group_label}: ABR (₹/kWh)")
                fig_abr.update_traces(textposition="outside")
                fig_abr.update_layout(**dark_layout(showlegend=False, height=430, yaxis_title="ABR ₹/kWh"))
                st.plotly_chart(fig_abr, use_container_width=True, key="ov_abr", config=PLOTLY_CONFIG)

        with col2:
            if group_col and group_col in display_df.columns and 'real_rate' in display_df.columns:
                fig_rr = px.bar(display_df.sort_values('real_rate',ascending=False), x=group_col, y='real_rate',
                                color='real_rate', color_continuous_scale='Greens',
                                text=display_df.sort_values('real_rate',ascending=False)['real_rate'].round(2),
                                title=f"{group_label}: Real (Through) Rate (₹/kWh)")
                fig_rr.update_traces(textposition="outside")
                fig_rr.update_layout(**dark_layout(showlegend=False, height=430, yaxis_title="Real Rate ₹/kWh"))
                st.plotly_chart(fig_rr, use_container_width=True, key="ov_rr", config=PLOTLY_CONFIG)

        # ABR vs Real Rate comparison (grouped)
        if group_col and group_col in display_df.columns and 'abr' in display_df.columns and 'real_rate' in display_df.columns:
            fig_both = go.Figure()
            fig_both.add_trace(go.Bar(name="ABR (₹/kWh)", x=display_df[group_col], y=display_df['abr'],
                                      marker_color="#3b82f6", text=display_df['abr'].round(2), textposition="outside"))
            fig_both.add_trace(go.Bar(name="Real Rate (₹/kWh)", x=display_df[group_col], y=display_df['real_rate'],
                                      marker_color="#22c55e", text=display_df['real_rate'].round(2), textposition="outside"))
            fig_both.update_layout(**dark_layout(barmode="group", title=f"{group_label}: ABR vs Real Rate Comparison",
                                                  height=420, yaxis_title="₹/kWh"))
            st.plotly_chart(fig_both, use_container_width=True, key="ov_abr_rr_cmp", config=PLOTLY_CONFIG)

            # Rate gap
            display_df_temp = display_df.copy()
            display_df_temp['rate_gap'] = (display_df_temp['abr'] - display_df_temp['real_rate']).round(2)
            fig_gap = px.bar(display_df_temp.sort_values('rate_gap',ascending=False), x=group_col, y='rate_gap',
                             color='rate_gap', color_continuous_scale='RdYlGn_r',
                             text=display_df_temp.sort_values('rate_gap',ascending=False)['rate_gap'].round(2),
                             title=f"{group_label}: Rate Gap = ABR − Real Rate (₹/kWh) — Lower is better")
            fig_gap.update_traces(textposition="outside")
            fig_gap.update_layout(**dark_layout(showlegend=False, height=400, yaxis_title="Rate Gap ₹/kWh"))
            st.plotly_chart(fig_gap, use_container_width=True, key="ov_rate_gap", config=PLOTLY_CONFIG)

        # ── Zone ABR & Rate ────────────────────────────────────────────────────
        if not zone_df.empty:
            section_hdr("🗺️ Zone-wise ABR & Through Rate", "#1e3a5f")
            z_rate = zone_df.copy()
            z_rate['rate_gap'] = (z_rate['abr'] - z_rate['real_rate']).round(2)
            cols = st.columns(2)
            with cols[0]:
                fig_zabr = go.Figure()
                fig_zabr.add_trace(go.Bar(name="ABR (₹/kWh)",       x=z_rate['zone'], y=z_rate['abr'],       marker_color="#3b82f6", text=z_rate['abr'].round(2), textposition="outside"))
                fig_zabr.add_trace(go.Bar(name="Real Rate (₹/kWh)", x=z_rate['zone'], y=z_rate['real_rate'], marker_color="#22c55e", text=z_rate['real_rate'].round(2), textposition="outside"))
                fig_zabr.update_layout(**dark_layout(barmode="group", title="Zone: ABR vs Real Rate", height=400, yaxis_title="₹/kWh"))
                st.plotly_chart(fig_zabr, use_container_width=True, key="z_abr_rr", config=PLOTLY_CONFIG)
            with cols[1]:
                fig_zgap2 = px.bar(z_rate.sort_values('rate_gap',ascending=False), x='zone', y='rate_gap',
                                   color='rate_gap', color_continuous_scale='RdYlGn_r',
                                   text=z_rate.sort_values('rate_gap',ascending=False)['rate_gap'].round(2),
                                   title="Zone: Rate Gap (ABR − Real Rate) ₹/kWh")
                fig_zgap2.update_traces(textposition="outside")
                fig_zgap2.update_layout(**dark_layout(showlegend=False, height=400, yaxis_title="Gap ₹/kWh"))
                st.plotly_chart(fig_zgap2, use_container_width=True, key="z_rate_gap", config=PLOTLY_CONFIG)
            insight_box(f"💡 Zone with highest rate gap: <b>{z_rate.nlargest(1,'rate_gap')['zone'].values[0]}</b> — "
                        f"Gap = ₹{z_rate.nlargest(1,'rate_gap')['rate_gap'].values[0]:.2f}/kWh", "warn")
            styled_kpi_table(zone_df[['zone','abr','real_rate']], 'zone')

        # ── Circle ABR & Rate ──────────────────────────────────────────────────
        if not circle_df.empty:
            section_hdr("🏙️ Circle-wise ABR & Through Rate", "#1e3a5f")
            c_rate = circle_df.copy()
            c_rate['rate_gap'] = (c_rate['abr'] - c_rate['real_rate']).round(2)
            fig_cabr = go.Figure()
            fig_cabr.add_trace(go.Bar(name="ABR", x=c_rate['circle'], y=c_rate['abr'], marker_color="#3b82f6",
                                      text=c_rate['abr'].round(2), textposition="outside"))
            fig_cabr.add_trace(go.Bar(name="Real Rate", x=c_rate['circle'], y=c_rate['real_rate'], marker_color="#22c55e",
                                      text=c_rate['real_rate'].round(2), textposition="outside"))
            fig_cabr.update_layout(**dark_layout(barmode="group", title="Circle: ABR vs Real Rate (₹/kWh)", height=420, yaxis_title="₹/kWh"))
            st.plotly_chart(fig_cabr, use_container_width=True, key="c_abr_rr", config=PLOTLY_CONFIG)
            styled_kpi_table(circle_df[['zone','circle','abr','real_rate']], 'circle')

        # ── Division ABR & Rate ────────────────────────────────────────────────
        if not division_df.empty:
            section_hdr("🏢 Division-wise ABR & Through Rate", "#1e3a5f")
            d_rate = division_df.copy()
            d_rate['rate_gap'] = (d_rate['abr'] - d_rate['real_rate']).round(2)
            top_n_rg = st.slider("Show Top N Divisions by Rate Gap", 5, min(50,len(division_df)), min(20,len(division_df)), key="rg_div_n")
            worst_rg = d_rate.nlargest(top_n_rg, 'rate_gap')
            fig_drg = px.bar(worst_rg, y='division', x='rate_gap', orientation='h',
                             color='rate_gap', color_continuous_scale='RdYlGn_r',
                             text=worst_rg['rate_gap'].round(2),
                             title=f"Top {top_n_rg} Divisions — Highest Rate Gap (₹/kWh)")
            fig_drg.update_traces(textposition="outside")
            fig_drg.update_layout(**dark_layout(showlegend=False, height=max(400,top_n_rg*26)))
            st.plotly_chart(fig_drg, use_container_width=True, key="d_rg_bar", config=PLOTLY_CONFIG)
            styled_kpi_table(division_df[['zone','circle','division','abr','real_rate']], 'division')


    # ══ TAB 5: RANKINGS ════════════════════════════════════════════════════════
    with tabs[5]:
        section_hdr(f"🏆 Rankings — {current_hierarchy} ({group_label} Level)")
        n_top = st.slider("Top/Bottom N", 3, 30, 10, key="ov_n_top")

        rank_metrics = [
            ("atc_loss_pct",              "AT&C Loss %",           True,  "Lowest AT&C (Best)",   False),
            ("atc_loss_pct",              "AT&C Loss %",           False, "Highest AT&C (Worst)",  True),
            ("collection_efficiency_pct", "Collection Eff %",      False, "Best Collection",       False),
            ("collection_efficiency_pct", "Collection Eff %",      True,  "Worst Collection",      True),
            ("line_loss_pct",             "Line Loss %",           True,  "Lowest Line Loss",      False),
            ("abr",                       "ABR ₹/kWh",            False, "Highest ABR",           False),
            ("real_rate",                 "Real Rate ₹/kWh",      False, "Best Through Rate",  False),
        ]

        col1, col2 = st.columns(2)
        for i, (metric, metric_lbl, smallest, rank_title, is_worst) in enumerate(rank_metrics):
            if metric not in display_df.columns or not group_col or group_col not in display_df.columns:
                continue
            ranked = display_df.nsmallest(n_top, metric) if smallest else display_df.nlargest(n_top, metric)
            colors = [[0,"#ef4444"],[1,"#22c55e"]] if not is_worst else [[0,"#22c55e"],[1,"#ef4444"]]
            fig_r = px.bar(ranked, y=group_col, x=metric, orientation='h',
                           color=metric, color_continuous_scale=colors,
                           text=ranked[metric].round(2),
                           title=f"{'🏆' if not is_worst else '🔴'} {rank_title} — {n_top} {group_label}s")
            fig_r.update_traces(textposition="outside")
            fig_r.update_layout(**dark_layout(showlegend=False, height=420))
            target = col1 if i % 2 == 0 else col2
            with target:
                st.plotly_chart(fig_r, use_container_width=True, key=f"ov_rank_{i}", config=PLOTLY_CONFIG)


    # ══ TAB 6: SLAB ANALYSIS ══════════════════════════════════════════════════
    with tabs[6]:
        section_hdr(f"📐 Slab-wise Abstract — {current_hierarchy}")
        insight_box("📌 Slab analysis shows distribution of units across AT&C loss bands.", "info")

        if 'atc_loss_pct' in display_df.columns:
            slab_counts = []
            total_sl = len(display_df)
            for s in ATC_SLABS:
                mask = (display_df['atc_loss_pct'] >= s['min']) & (display_df['atc_loss_pct'] < s['max'])
                count = mask.sum()
                pct   = round(count / total_sl * 100, 1) if total_sl > 0 else 0
                avg_a = display_df.loc[mask,'atc_loss_pct'].mean() if count > 0 else 0
                avg_r = display_df.loc[mask,'real_rate'].mean()    if count > 0 and 'real_rate' in display_df.columns else 0
                avg_b = display_df.loc[mask,'abr'].mean()          if count > 0 and 'abr' in display_df.columns else 0
                slab_counts.append({**s, 'count':count,'pct':pct,'avg_atc':avg_a,'avg_real_rate':avg_r,'avg_abr':avg_b})

            cols = st.columns(len(ATC_SLABS))
            for i,(col,s) in enumerate(zip(cols, slab_counts)):
                with col:
                    st.markdown(f"""
                    <div style="background:{s['bg']};border:3px solid {s['color']};border-radius:14px;
                                padding:14px 8px;text-align:center;box-shadow:0 4px 12px {s['color']}33;">
                        <div style="font-size:32px;font-weight:900;color:{s['color']};font-family:'JetBrains Mono',monospace">{s['count']}</div>
                        <div style="font-size:10px;color:#64748b;font-weight:700">{s['label']}</div>
                        <div style="font-size:12px;font-weight:800;color:{s['color']};margin-top:4px">{s['text']}</div>
                        <div style="font-size:10px;color:#94a3b8;margin-top:4px">{s['pct']}% | Avg {s['avg_atc']:.1f}%</div>
                        <div style="font-size:10px;color:#64748b">ABR ₹{s['avg_abr']:.2f} | RR ₹{s['avg_real_rate']:.2f}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # ── CLICKABLE SLAB → DETAIL TABLE ──────────────────────────────────
            section_hdr("🔍 View Slab-wise Detail Data")
            slab_select_options = ["— Select a Slab —"] + [
                f"{s['text']} {s['label']} ({s['count']} {group_label}s)" for s in slab_counts
            ]
            sel_slab_label = st.selectbox(
                "Select a slab to view its detailed data:",
                slab_select_options, key="ov_slab_select"
            )

            if sel_slab_label != "— Select a Slab —":
                sel_idx = slab_select_options.index(sel_slab_label) - 1
                sel_s   = slab_counts[sel_idx]
                mask = (display_df['atc_loss_pct'] >= sel_s['min']) & (display_df['atc_loss_pct'] < sel_s['max'])
                slab_detail_df = display_df.loc[mask].copy()

                st.markdown(
                    f"<div style='background:{sel_s['bg']};border-left:5px solid {sel_s['color']};"
                    f"border-radius:8px;padding:10px 16px;margin:10px 0;'>"
                    f"<b style='color:{sel_s['color']}'>{sel_s['text']} {sel_s['label']}</b> — "
                    f"{len(slab_detail_df)} {group_label}(s) | "
                    f"Avg AT&C: <b>{sel_s['avg_atc']:.2f}%</b> | "
                    f"Avg ABR: <b>₹{sel_s['avg_abr']:.2f}</b> | "
                    f"Avg Real Rate: <b>₹{sel_s['avg_real_rate']:.2f}</b>"
                    f"</div>", unsafe_allow_html=True
                )

                if not slab_detail_df.empty:
                    if group_col:
                        styled_kpi_table(slab_detail_df, group_col, f"📋 {sel_s['label']} — {group_label}-wise Detail")
                    else:
                        st.dataframe(slab_detail_df, use_container_width=True, hide_index=True)

                    st.download_button(
                        f"📥 Download {sel_s['label']} Slab Data (CSV)",
                        slab_detail_df.to_csv(index=False).encode(),
                        f"DVVNL_Slab_{sel_s['label'].replace(' ','_').replace('%','pct')}_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv", use_container_width=True, key="ov_slab_detail_dl"
                    )
                else:
                    st.info(f"No {group_label}s found in this slab.")


            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                summary_df = pd.DataFrame([{"Slab":s['label'],"Status":s['text'],"Count":s['count'],
                                             "% of Total":f"{s['pct']}%","Avg AT&C %":f"{s['avg_atc']:.1f}%",
                                             "Avg ABR":f"₹{s['avg_abr']:.2f}","Avg Real Rate":f"₹{s['avg_real_rate']:.2f}"}
                                            for s in slab_counts])
                st.markdown("**📊 Slab Summary Table**")
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

            with col2:
                fig_pie = px.pie(summary_df, values='Count', names='Slab',
                                 color='Slab', hole=0.4,
                                 color_discrete_sequence=[s['color'] for s in slab_counts],
                                 title="AT&C Slab Distribution")
                fig_pie.update_layout(**dark_layout(height=380))
                st.plotly_chart(fig_pie, use_container_width=True, key="ov_slab_pie", config=PLOTLY_CONFIG)

            # Per-zone slab breakdown
            if not zone_df.empty and 'atc_loss_pct' in zone_df.columns:
                section_hdr("🗺️ Zone-wise Slab Status")
                for _, zrow in zone_df.iterrows():
                    atc_val = zrow.get('atc_loss_pct', 0)
                    slab_label = next((s['text'] for s in ATC_SLABS if s['min'] <= atc_val < s['max']), "—")
                    color = next((s['color'] for s in ATC_SLABS if s['min'] <= atc_val < s['max']), "#888")
                    st.markdown(
                        f"<span style='background:{color};color:#fff;border-radius:6px;padding:3px 10px;font-weight:700;'>"
                        f"{zrow['zone']}</span> &nbsp; AT&C: <b>{atc_val:.2f}%</b> — {slab_label} "
                        f"&nbsp;|&nbsp; BE: {zrow.get('billing_efficiency_pct',0):.2f}% &nbsp;|&nbsp; CE: {zrow.get('collection_efficiency_pct',0):.2f}%",
                        unsafe_allow_html=True
                    )



# ══ TAB 7: DATA & EXPORT ══════════════════════════════════════════════════
    with tabs[7]:
        section_hdr(f"📋 Data Table & Export — {current_hierarchy}")

        all_cols = display_df.columns.tolist()
        default_cols = [c for c in [group_col,'atc_loss_pct','billing_efficiency_pct','collection_efficiency_pct',
                                    'line_loss_pct','input_energy_kwh','sold_energy_kwh',
                                    'net_assessment','revenue_realized','real_rate','abr','unit_count']
                        if c in all_cols]
        show_cols = st.multiselect("Columns to display:", all_cols, default=default_cols, key="ov_cols")
        search    = st.text_input("🔍 Search:", "", key="ov_search")

        df_display = display_df.copy()
        if search and group_col and group_col in df_display.columns:
            df_display = df_display[df_display[group_col].astype(str).str.contains(search, case=False, na=False)]
        if show_cols:
            df_display = df_display[show_cols]

        pct_cols = [c for c in ['atc_loss_pct','billing_efficiency_pct','collection_efficiency_pct','line_loss_pct'] if c in df_display.columns]
        num_cols = [c for c in ['input_energy_kwh','sold_energy_kwh','net_assessment','revenue_realized','total_outstanding_amount'] if c in df_display.columns]
        rate_cols= [c for c in ['real_rate','abr'] if c in df_display.columns]

        fmt_dict = {c:"{:.2f}%" for c in pct_cols}
        fmt_dict.update({c:"{:,.2f}" for c in num_cols})
        fmt_dict.update({c:"₹{:.2f}" for c in rate_cols})

        st.dataframe(df_display.style.format(fmt_dict), use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(df_display)} of {len(display_df)} {group_label}s")

        d1,d2,d3 = st.columns(3)
        with d1:
            st.download_button("📥 Download CSV", df_display.to_csv(index=False).encode(),
                f"DVVNL_Overall_{level_filter}_{datetime.now().strftime('%Y%m%d')}.csv","text/csv",
                use_container_width=True, key="ov_dl_csv")
        with d2:
            st.download_button("📊 Download Excel", export_excel(df_display),
                f"DVVNL_Overall_{level_filter}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key="ov_dl_xlsx")
        with d3:
            st.download_button("📋 Raw Data CSV", df.to_csv(index=False).encode(),
                f"DVVNL_Overall_Raw_{datetime.now().strftime('%Y%m%d')}.csv","text/csv",
                use_container_width=True, key="ov_dl_raw")

        section_hdr(f"📊 Grand Total Summary — {current_hierarchy}")
        st.dataframe(pd.DataFrame([gt]), use_container_width=True, hide_index=True)

        # ══════════════════════════════════════════════════════════════════════
        # HIERARCHICAL REPORT EXPORT
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        section_hdr("📑 Hierarchical Report Export — Zone → Circle → Division")
        insight_box(
            "📌 Generate a structured multi-level report (Excel with separate sheets, "
            "or a single flattened hierarchical CSV) for offline review and circulation.",
            "info"
        )

        report_scope = st.radio(
            "Select Report Scope:",
            ["📊 Current Filtered View Only", "🌐 Full DVVNL Hierarchy (All Zones/Circles/Divisions)"],
            horizontal=True, key="ov_report_scope"
        )

        report_format = st.radio(
            "Select Report Format:",
            ["📗 Excel (Multi-sheet: Zone | Circle | Division | Grand Total)",
             "📄 Hierarchical CSV (Flattened, indented levels)"],
            horizontal=False, key="ov_report_format"
        )

        # Determine source dataframes based on scope
        if report_scope.startswith("🌐"):
            _zone_src     = agg_level(['zone'])                    if 'zone' in df_raw.columns else pd.DataFrame()
            _circle_src   = agg_level(['zone','circle'])           if all(c in df_raw.columns for c in ['zone','circle']) else pd.DataFrame()
            _division_src = agg_level(['zone','circle','division']) if all(c in df_raw.columns for c in ['zone','circle','division']) else pd.DataFrame()
            _scope_label  = "Full_DVVNL"

            # Recompute against full df_raw (not the filtered df)
            def agg_level_raw(grp_cols):
                d = df_raw.groupby(grp_cols).agg(**{c:pd.NamedAgg(column=c,aggfunc='sum') for c in present_sum}).reset_index()
                return recalc_kpis(d)

            _zone_src     = agg_level_raw(['zone'])                    if 'zone' in df_raw.columns else pd.DataFrame()
            _circle_src   = agg_level_raw(['zone','circle'])           if all(c in df_raw.columns for c in ['zone','circle']) else pd.DataFrame()
            _division_src = agg_level_raw(['zone','circle','division']) if all(c in df_raw.columns for c in ['zone','circle','division']) else pd.DataFrame()
            _gt_src       = recalc_kpis(pd.DataFrame([{
                **{c: df_raw[c].sum() for c in present_sum if c in df_raw.columns}
            }])).iloc[0].to_dict()
        else:
            _zone_src, _circle_src, _division_src = zone_df, circle_df, division_df
            _gt_src = gt
            _scope_label = (current_hierarchy.replace(" → ","_").replace(" ","_")
                            if current_hierarchy != "DVVNL (All Units)" else "Filtered_View")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if report_format.startswith("📗"):
            # ── EXCEL MULTI-SHEET REPORT ────────────────────────────────────────
            def build_excel_report():
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    # Cover / Grand Total sheet
                    gt_df = pd.DataFrame([_gt_src])
                    gt_df.to_excel(writer, index=False, sheet_name="Grand_Total")

                    if not _zone_src.empty:
                        _zone_src.to_excel(writer, index=False, sheet_name="Zone_Summary")
                    if not _circle_src.empty:
                        _circle_src.to_excel(writer, index=False, sheet_name="Circle_Summary")
                    if not _division_src.empty:
                        # Excel sheet name max length = 31 chars
                        _division_src.to_excel(writer, index=False, sheet_name="Division_Summary")

                    # Apply basic formatting
                    workbook = writer.book
                    for sheet_name in writer.sheets:
                        ws = writer.sheets[sheet_name]
                        for col_cells in ws.columns:
                            max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
                            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 3, 35)
                return buf.getvalue()

            excel_bytes = build_excel_report()
            st.download_button(
                "📗 Download Hierarchical Excel Report (Zone | Circle | Division | Grand Total)",
                excel_bytes,
                f"DVVNL_Hierarchical_Report_{_scope_label}_{timestamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key="ov_hier_excel_dl"
            )

            with st.expander("👁️ Preview Report Sheets", expanded=False):
                st.markdown("**📍 Grand Total**")
                st.dataframe(pd.DataFrame([_gt_src]), use_container_width=True, hide_index=True)
                if not _zone_src.empty:
                    st.markdown("**🗺️ Zone Summary**")
                    st.dataframe(_zone_src, use_container_width=True, hide_index=True)
                if not _circle_src.empty:
                    st.markdown("**🏙️ Circle Summary**")
                    st.dataframe(_circle_src, use_container_width=True, hide_index=True)
                if not _division_src.empty:
                    st.markdown("**🏢 Division Summary**")
                    st.dataframe(_division_src, use_container_width=True, hide_index=True)

        else:
            # ── HIERARCHICAL FLATTENED CSV (indented levels) ────────────────────
            def build_hierarchical_csv():
                rows = []
                report_cols = ['input_energy_kwh','sold_energy_kwh','billing_efficiency_pct',
                               'line_loss_pct','net_assessment','revenue_realized',
                               'collection_efficiency_pct','atc_loss_pct','real_rate','abr']

                # DVVNL Grand Total row
                base_row = {"Level":"DVVNL","Name":"DVVNL (Overall)","Parent":""}
                for c in report_cols:
                    base_row[c] = _gt_src.get(c, 0)
                rows.append(base_row)

                if not _zone_src.empty:
                    for _, zr in _zone_src.iterrows():
                        zrow = {"Level":"Zone","Name":f"  {zr['zone']}","Parent":"DVVNL"}
                        for c in report_cols:
                            zrow[c] = zr.get(c, 0)
                        rows.append(zrow)

                        if not _circle_src.empty and 'zone' in _circle_src.columns:
                            sub_circles = _circle_src[_circle_src['zone'] == zr['zone']]
                            for _, cr in sub_circles.iterrows():
                                crow = {"Level":"Circle","Name":f"    {cr['circle']}","Parent":zr['zone']}
                                for c in report_cols:
                                    crow[c] = cr.get(c, 0)
                                rows.append(crow)

                                if not _division_src.empty and 'circle' in _division_src.columns:
                                    sub_divs = _division_src[_division_src['circle'] == cr['circle']]
                                    for _, dr in sub_divs.iterrows():
                                        drow = {"Level":"Division","Name":f"      {dr['division']}","Parent":cr['circle']}
                                        for c in report_cols:
                                            drow[c] = dr.get(c, 0)
                                        rows.append(drow)

                report_df = pd.DataFrame(rows)
                # Round numeric columns
                for c in report_cols:
                    if c in report_df.columns:
                        report_df[c] = pd.to_numeric(report_df[c], errors='coerce').round(2)
                return report_df

            hier_csv_df = build_hierarchical_csv()

            st.download_button(
                "📄 Download Hierarchical CSV Report (Indented Zone → Circle → Division)",
                hier_csv_df.to_csv(index=False).encode(),
                f"DVVNL_Hierarchical_Report_{_scope_label}_{timestamp}.csv",
                "text/csv", use_container_width=True, key="ov_hier_csv_dl"
            )

            with st.expander("👁️ Preview Hierarchical Report", expanded=True):
                rename_map = {
                    'input_energy_kwh':'Input(MU)','sold_energy_kwh':'Sold(MU)',
                    'billing_efficiency_pct':'Billing%','line_loss_pct':'LineLoss%',
                    'net_assessment':'Assessment(₹L)','revenue_realized':'Revenue(₹L)',
                    'collection_efficiency_pct':'Collection%','atc_loss_pct':'AT&C%',
                    'real_rate':'RealRate','abr':'ABR'
                }
                preview = hier_csv_df.rename(columns=rename_map)
                st.dataframe(preview, use_container_width=True, hide_index=True, height=420)
if __name__ == "__main__":
    render()