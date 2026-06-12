"""
substation_dashboard.py — DVVNL Substation Analytics Dashboard
==============================================================
Optimized for fast rendering, vectorized search, and browser stability.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import duckdb, io
from datetime import datetime

from config import DB_PATH, APRIL_START, APRIL_END, COLOR_PALETTE, KPI_THRESHOLDS
from substation_queries import load_substation_data, process_substation
from charts import (
    dark_layout, atc_color,
    chart_zone_radar, chart_funnel,
    chart_loss_histogram, chart_waterfall_decomposition, chart_energy_sankey
)


st.set_page_config(
    page_title="DVVNL Substation Dashboard",
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


# ── HELPERS ───────────────────────────────────────────────────────────────────
def fmt_lakh(n):
    if n is None or (isinstance(n,float) and pd.isna(n)): return "—"
    if abs(n)>=1e7: return f"{n/1e7:.2f} Cr"
    if abs(n)>=1e5: return f"{n/1e5:.2f} L"
    if abs(n)>=1e3: return f"{n/1e3:.1f} K"
    return f"{n:.0f}"

def rating(v):
    if v is None: return "N/A"
    if v < KPI_THRESHOLDS["atc_good"]:  return "✅ GOOD"
    if v < KPI_THRESHOLDS["atc_ok"]:    return "⚠️ OK"
    if v < KPI_THRESHOLDS["atc_high"]:  return "🟠 HIGH"
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
        df.to_excel(w, index=False, sheet_name="Substation_KPIs")
    return buf.getvalue()

def build_hierarchy_header(zone_sel, circle_sel, division_sel, ss_count):
    """Build a descriptive header showing current filter hierarchy"""
    hierarchy_parts = []
    
    if zone_sel != "All Zones":
        hierarchy_parts.append(f'<span style="color: #60a5fa;">🗺️ {zone_sel}</span>')
    if circle_sel != "All Circles":
        hierarchy_parts.append(f'<span style="color: #34d399;">🏙️ {circle_sel}</span>')
    if division_sel != "All Divisions":
        hierarchy_parts.append(f'<span style="color: #fbbf24;">🏢 {division_sel}</span>')
    
    if hierarchy_parts:
        hierarchy_display = " → ".join(hierarchy_parts)
        level_text = "Selected Unit"
    else:
        hierarchy_display = "🏢 DVVNL (All Units)"
        level_text = "Organization Level"
    
    return f"""
    <div style="
        background:linear-gradient(135deg, rgb(91 119 169) 0%, rgb(87 102 146) 50%, rgb(30, 58, 95) 100%);
        border-radius: 16px;
        padding: 12px 24px;
        margin: 10px 0 20px 0;
        box-shadow: 0 6px 16px rgba(0,0,0,0.15);
        border: 1px solid rgba(255,255,255,0.15);
    ">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="
                    background: rgba(255,255,255,0.15);
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 22px;
                ">🏗️</div>
                <div>
                    <div style="color: #93c5fd; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;">
                        CURRENT VIEW
                    </div>
                    <div style="color: #ffffff; font-size: 18px; font-weight: 800;">
                        {hierarchy_display}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="text-align: center;">
                    <div style="color: #93c5fd; font-size: 10px; font-weight: 600;">SUBSTATIONS</div>
                    <div style="color: #fbbf24; font-size: 22px; font-weight: 900;">{ss_count:,}</div>
                </div>
                <div style="text-align: center;">
                    <div style="color: #93c5fd; font-size: 10px; font-weight: 600;">HIERARCHY LEVEL</div>
                    <div style="color: #34d399; font-size: 14px; font-weight: 700;">{level_text}</div>
                </div>
            </div>
        </div>
        <div style="margin-top: 10px; height: 2px; background: linear-gradient(90deg, transparent, #60a5fa, #fbbf24, transparent); border-radius: 2px;"></div>
    </div>
    """

# ── DB CONNECTION & CACHING ───────────────────────────────────────────────────
@st.cache_resource
def _get_con():
    return duckdb.connect(DB_PATH, read_only=True)

@st.cache_data(ttl=600, show_spinner="⚡ Loading substation data from DuckDB...")
def _load_raw():
    return load_substation_data(_get_con())

@st.cache_data(ttl=3600, show_spinner=False)
def _process(zone_f, circle_f, div_f):
    edf, bdf = _load_raw()
    return process_substation(edf, bdf, zone_f, circle_f, div_f)

@st.cache_data(ttl=3600, show_spinner=False)
def get_filter_options():
    """Get unique filter options from full dataset for cascading"""
    try:
        _full = _process("All Zones", "All Circles", "All Divisions")
        df_full = _full['df']
        
        all_zones = sorted(df_full['zone'].dropna().unique().tolist()) if 'zone' in df_full.columns else []
        
        # Create dictionaries for cascading filters
        zone_to_circles = {}
        circle_to_divisions = {}
        
        if 'zone' in df_full.columns and 'circle' in df_full.columns:
            for zone in all_zones:
                circles = df_full[df_full['zone'] == zone]['circle'].dropna().unique().tolist()
                zone_to_circles[zone] = sorted(circles)
        
        if 'circle' in df_full.columns and 'division' in df_full.columns:
            circles_list_all = sorted(df_full['circle'].dropna().unique().tolist())
            for circle in circles_list_all:
                divisions = df_full[df_full['circle'] == circle]['division'].dropna().unique().tolist()
                circle_to_divisions[circle] = sorted(divisions)
        
        return all_zones, zone_to_circles, circle_to_divisions, df_full
    except Exception as e:
        st.error(f"Error loading filter options: {e}")
        return [], {}, {}, pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}

def render():
    """Main render function for Substation Dashboard"""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg, rgb(73 144 192), rgb(141 174 216), rgb(240, 249, 255));
                border-bottom:2px solid #35498f;padding:4px 20px;border-radius:14px;
                margin-bottom:8px;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#0f172a">
            🏗️ Substation-wise AT&amp;C Loss Dashboard</div>
    </div>
    """, unsafe_allow_html=True)    
    # # ── FILTERS SECTION ───────────────────────────────────────────────────────
    # st.markdown('<div style="background:#4c89b4;color:#fff;font-size:14px;' \
    # 'font-weight:800;text-transform:uppercase;border-radius:12px;' \
    # 'padding:8px 16px;margin-bottom:2px;text-align:center;">' \
    # '🔧 Filters & Controls</div>', unsafe_allow_html=True)
    
    # Load filter options for cascading
    all_zones, zone_to_circles, circle_to_divisions, df_full = get_filter_options()
    
    # Initialize session state for filters if not exists
    if 'sub_filter_zone' not in st.session_state:
        st.session_state.sub_filter_zone = "All Zones"
    if 'sub_filter_circle' not in st.session_state:
        st.session_state.sub_filter_circle = "All Circles"
    if 'sub_filter_division' not in st.session_state:
        st.session_state.sub_filter_division = "All Divisions"
    
    # Row 1: Zone, Circle, Division filters with cascading
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        # Zone filter - when changed, reset circle and division
        new_zone = st.selectbox(
            "🗺️ Zone", 
            ["All Zones"] + all_zones,
            index=0 if st.session_state.sub_filter_zone == "All Zones" else (all_zones.index(st.session_state.sub_filter_zone) + 1 if st.session_state.sub_filter_zone in all_zones else 0),
            key="sub_zone_cascade"
        )
        
        # Reset circle and division if zone changed
        if new_zone != st.session_state.sub_filter_zone:
            st.session_state.sub_filter_zone = new_zone
            st.session_state.sub_filter_circle = "All Circles"
            st.session_state.sub_filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.sub_filter_zone = new_zone
    
    # Get available circles based on selected zone
    if st.session_state.sub_filter_zone != "All Zones":
        available_circles = zone_to_circles.get(st.session_state.sub_filter_zone, [])
    else:
        available_circles = sorted(df_full['circle'].dropna().unique().tolist()) if 'circle' in df_full.columns else []
    
    with col2:
        new_circle = st.selectbox(
            "🏙️ Circle", 
            ["All Circles"] + available_circles,
            index=0 if st.session_state.sub_filter_circle == "All Circles" else (available_circles.index(st.session_state.sub_filter_circle) + 1 if st.session_state.sub_filter_circle in available_circles else 0),
            key="sub_circle_cascade"
        )
        
        # Reset division if circle changed
        if new_circle != st.session_state.sub_filter_circle:
            st.session_state.sub_filter_circle = new_circle
            st.session_state.sub_filter_division = "All Divisions"
            st.rerun()
        else:
            st.session_state.sub_filter_circle = new_circle
    
    # Get available divisions based on selected circle
    if st.session_state.sub_filter_circle != "All Circles":
        available_divisions = circle_to_divisions.get(st.session_state.sub_filter_circle, [])
    elif st.session_state.sub_filter_zone != "All Zones":
        # Get all divisions in selected zone
        df_zone = df_full[df_full['zone'] == st.session_state.sub_filter_zone] if st.session_state.sub_filter_zone != "All Zones" else df_full
        available_divisions = sorted(df_zone['division'].dropna().unique().tolist()) if 'division' in df_zone.columns else []
    else:
        available_divisions = sorted(df_full['division'].dropna().unique().tolist()) if 'division' in df_full.columns else []
    
    with col3:
        new_division = st.selectbox(
            "🏢 Division", 
            ["All Divisions"] + available_divisions,
            index=0 if st.session_state.sub_filter_division == "All Divisions" else (available_divisions.index(st.session_state.sub_filter_division) + 1 if st.session_state.sub_filter_division in available_divisions else 0),
            key="sub_div_cascade"
        )
        st.session_state.sub_filter_division = new_division
    
    with col4:
    # Sort options with proper display labels
        sort_options_display = [
        "AT&C Loss %",
        "Billing Efficiency %", 
        "Collection Efficiency %",
        "Line Loss %",
        "Input Energy (KWH)",
        "Revenue Realized (₹)",
        "Feeder Count"
    ]
    
        sort_options_values = [
        "atc_loss_pct",
        "billing_efficiency_pct",
        "collection_efficiency_pct", 
        "line_loss_pct",
        "input_energy_kwh",
        "revenue_realized",
        "feeder_count"
    ]
    
        selected_display = st.selectbox("📊 Sort By", sort_options_display, key="sub_sort")
        sub_sort = sort_options_values[sort_options_display.index(selected_display)]
    
    with col5:
        sub_asc = st.toggle("Ascending", False, key="sub_asc")
    
    with col6:
        if st.button("🔄 Refresh Data", use_container_width=True, key="sub_refresh"):
            st.cache_data.clear()
            st.rerun()
    
    # Use session state values for filtering
    sub_zone = st.session_state.sub_filter_zone
    sub_circle = st.session_state.sub_filter_circle
    sub_div = st.session_state.sub_filter_division
    
    # ── LOAD FILTERED DATA ────────────────────────────────────────────────────
    try:
        result = _process(sub_zone, sub_circle, sub_div)
    except Exception as e:
        st.error(f"❌ Processing Error: {e}")
        return

    df = result['df'].copy()
    zone_df = result['zone_df']
    circle_df = result['circle_df']
    division_df = result['division_df']
    gt = result['gt']
    funnel_data = result['funnel']
    hist_df = result['hist_df']
    unmatched_df = result['unmatched_df']

    if sub_sort in df.columns:
        df = df.sort_values(sub_sort, ascending=sub_asc).reset_index(drop=True)

    # Safe plot size calculations
    if 'input_energy_kwh' in df.columns:
        df['plot_size_input'] = df['input_energy_kwh'].fillna(1).abs().clip(lower=1)
    if 'net_assessment_sub' in df.columns:
        df['plot_size_assessment'] = df['net_assessment_sub'].fillna(1).abs().clip(lower=1)

    total_ss = len(df)
    
    # Build current hierarchy display
    def get_current_hierarchy():
        parts = []
        if sub_zone != "All Zones":
            parts.append(sub_zone)
        if sub_circle != "All Circles":
            parts.append(sub_circle)
        if sub_div != "All Divisions":
            parts.append(sub_div)
        return " → ".join(parts) if parts else "DVVNL (All Units)"
    
    current_hierarchy = get_current_hierarchy()

    # ── SUBSTATION HEADER WITH HIERARCHY ───────────────────────────────────────

    
    # ── DYNAMIC HIERARCHY HEADER ──────────────────────────────────────────────
    st.markdown(build_hierarchy_header(sub_zone, sub_circle, sub_div, total_ss), unsafe_allow_html=True)
    
    # ── GRAND KPIs ────────────────────────────────────────────────────────────
    st.markdown(f'<div style="background:#4c89b4;color:#fff;font-size:16px;font-weight:800;text-transform:uppercase;border-radius:12px;padding:10px 16px;margin-bottom:14px;text-align:center;">📊 {current_hierarchy} — Summary KPIs</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    for col,lbl,val,unit,color,sub in [
        (c1,"AT&C Loss",   f"{gt.get('atc_loss_pct',0):.1f}",            "%",  atc_color(gt.get('atc_loss_pct',0)),"Target <15%"),
        (c2,"Billing Eff", f"{gt.get('billing_efficiency_pct',0):.1f}",   "%",  "#0D692F","Sold/Input"),
        (c3,"Coll Eff",    f"{gt.get('collection_efficiency_pct',0):.1f}","%",  "#0A3F94","Rev/Assess"),
        (c4,"Line Loss",   f"{gt.get('line_loss_pct',0):.1f}",            "%",  "#6d350e","Technical"),
        (c5,"Input Energy",fmt_lakh(gt.get('input_energy_kwh',0)),        "KWH","#1725A5","Total"),
        (c6,"Sold Energy", fmt_lakh(gt.get('sold_energy_kwh',0)),         "KWH","#197553","Billed"),
        (c7,"Assessment",  fmt_lakh(gt.get('net_assessment_sub',0)),      "₹",  "#700c8e","Apr"),
    ]:
        with col: kpi_card(lbl, val, unit, color=color, sub=sub)

    e1,e2,e3,e4,e5,e6,e7 = st.columns(7)
    for col,lbl,val,color,sub in [
        (e1,"Revenue",     fmt_lakh(gt.get('revenue_realized',0)),      "#105a67","Collected"),
        (e2,"Substations",   str(total_ss),                             "#091169","In view"),
        (e3,"Consumers",     fmt_lakh(gt.get('consumers',0)),           "#1215a3","Operative"),
        (e4,"Billed",        fmt_lakh(gt.get('billed_consumers',0)),    "#0c6343","April"),
        (e5,"Paid",          fmt_lakh(gt.get('paid_consumers',0)),      "#06525f","April"),
        (e6,"Smart Meters",  fmt_lakh(gt.get('smart_meter_consumers',0)),"#36118C","Smart"),
        (e7,"Outstanding",   fmt_lakh(gt.get('outstanding_amount',0)),  "#7e0d0d","Arrears ₹"),
    ]:
        with col: kpi_card(lbl, val, "", color=color, sub=sub)

    # ── CRITICAL ALERTS ───────────────────────────────────────────────────────
    if "atc_loss_pct" in df.columns:
        critical = df[df["atc_loss_pct"] >= KPI_THRESHOLDS["atc_high"]]
        if not critical.empty:
             st.markdown(f"🔴 {len(critical)} CRITICAL Substations (AT&C ≥ {KPI_THRESHOLDS['atc_high']}%)")

        # if not critical.empty:
        #     with st.expander(f"🔴 {len(critical)} CRITICAL Substations (AT&C ≥ {KPI_THRESHOLDS['atc_high']}%)", expanded=False):
        #         for _, row in critical.iterrows():
        #             ca,cb,cc,cd = st.columns([2,1,1,1])
        #             with ca: st.markdown(f"**{row.get('substation','?')}** <span style='color:#64748b;font-size:11px'>{row.get('zone','')}</span>", unsafe_allow_html=True)
        #             with cb: st.markdown(f"<span style='color:#ef4444;font-weight:800'>AT&C: {row.get('atc_loss_pct',0):.1f}%</span>", unsafe_allow_html=True)
        #             with cc: st.markdown(f"<span style='color:#f97316'>BE: {row.get('billing_efficiency_pct',0):.1f}%</span>", unsafe_allow_html=True)
        #             with cd: st.markdown(f"<span style='color:#fbbf24'>CE: {row.get('collection_efficiency_pct',0):.1f}%</span>", unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────────────────────
    stabs = st.tabs([
        "📊 Overview", "🔴 AT&C Deep Dive", "⚡ Energy", "💰 Revenue",
        "🏆 Rankings", "🗺️ Zone View", "📐 Slab Analysis", "📋 Data & Export"
    ])

    # ══ STAB 1: OVERVIEW ══════════════════════════════════════════════════════
    with stabs[0]:
        if not zone_df.empty:
            st.markdown(f"**{current_hierarchy} - Zone-wise KPI**")
            fig2 = go.Figure()
            for cn,nm,cl in [("atc_loss_pct","AT&C %","#ef4444"),
                              ("billing_efficiency_pct","Billing Eff %","#22c55e"),
                              ("collection_efficiency_pct","Coll Eff %","#3b82f6")]:
                if cn in zone_df.columns:
                    fig2.add_trace(go.Bar(name=nm, x=zone_df["zone"], y=zone_df[cn], marker_color=cl))
            fig2.update_layout(**dark_layout(barmode="group"))
            st.plotly_chart(fig2, use_container_width=True, key="ss_ov_zone", config=PLOTLY_CONFIG)

        # st.markdown('<div class="section-title">🏭 Substation Overview - Input Energy Range Analysis</div>',
        #             unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
            <span style="color: #0f172a; font-size: 14px;">
            📌 <b>Substation Analytics:</b> Analyze substations based on input energy consumption ranges. 
            Identify high-consumption substations for priority monitoring and low-consumption substations for optimization.
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # ── INPUT ENERGY RANGE DEFINITIONS ──────────────────────────────────────────
        energy_ranges = [
            {"name": "Very High (> 10 MU)", "min": 10000000, "max": float('inf'), "color": "#ef4444", "icon": "🔴"},
            {"name": "High (5-10 MU)", "min": 5000000, "max": 10000000, "color": "#f97316", "icon": "🟠"},
            {"name": "Medium (2-5 MU)", "min": 2000000, "max": 5000000, "color": "#eab308", "icon": "⚠️"},
            {"name": "Low (1-2 MU)", "min": 1000000, "max": 2000000, "color": "#84cc16", "icon": "🟢"},
            {"name": "Very Low (< 1 MU)", "min": 0, "max": 1000000, "color": "#22c55e", "icon": "✅"}
        ]
        
        # Function to classify substation by input energy
        def get_energy_range(input_energy):
            if pd.isna(input_energy):
                return "Very Low (< 1 MU)"
            for rg in energy_ranges:
                if rg["min"] <= input_energy < rg["max"]:
                    return rg["name"]
            return "Very Low (< 1 MU)"
        
        # Create energy range column
        if 'input_energy_kwh' in df.columns:
            df['energy_range'] = df['input_energy_kwh'].apply(get_energy_range)
            
            # ── SUMMARY STATISTICS CARDS ─────────────────────────────────────────────
            st.markdown("### 📊 Overall Substation Statistics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                total_substations = len(df)
                st.metric("🏭 Total Substations", f"{total_substations:,}")
            
            with col2:
                total_input = df['input_energy_kwh'].sum() / 1e6
                st.metric("⚡ Total Input Energy", f"{total_input:.2f} MU")
            
            with col3:
                avg_input = df['input_energy_kwh'].mean() / 1e6
                st.metric("📊 Avg Input per Substation", f"{avg_input:.2f} MU")
            
            with col4:
                total_feeders = df['feeder_count'].sum() if 'feeder_count' in df.columns else 0
                st.metric("🔌 Total Feeders", f"{total_feeders:,.0f}")
            
            with col5:
                avg_atc = df['atc_loss_pct'].mean() if 'atc_loss_pct' in df.columns else 0
                st.metric("📉 Avg AT&C Loss", f"{avg_atc:.2f}%")
            
            st.markdown("---")
            
            # ── ENERGY RANGE DISTRIBUTION ───────────────────────────────────────────
            st.markdown("### 📊 Substation Distribution by Input Energy Range")
            
            # Create range distribution dataframe
            range_counts = df['energy_range'].value_counts().reset_index()
            range_counts.columns = ['Energy Range', 'Number of Substations']
            
            # Add percentage
            range_counts['Percentage'] = (range_counts['Number of Substations'] / total_substations * 100).round(1)
            
            # Add color mapping
            color_map = {rg["name"]: rg["color"] for rg in energy_ranges}
            range_counts['Color'] = range_counts['Energy Range'].map(color_map)
            
            # Display as columns
            range_cols = st.columns(len(energy_ranges))
            for idx, rg in enumerate(energy_ranges):
                if idx < len(range_cols):
                    with range_cols[idx]:
                        count = range_counts[range_counts['Energy Range'] == rg['name']]['Number of Substations'].values[0] if not range_counts[range_counts['Energy Range'] == rg['name']].empty else 0
                        pct = range_counts[range_counts['Energy Range'] == rg['name']]['Percentage'].values[0] if not range_counts[range_counts['Energy Range'] == rg['name']].empty else 0
                        st.markdown(f"""
                        <div style="background:{rg['color']}15; border:2px solid {rg['color']}; border-radius:12px; padding:12px; text-align:center;">
                            <div style="font-size:28px; font-weight:900; color:{rg['color']};">{count}</div>
                            <div style="font-size:12px; color:#475569; font-weight:600;">{rg['name']}</div>
                            <div style="font-size:11px; color:#64748b;">{pct}% of total</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Bar chart for energy range distribution
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                fig_range = px.bar(
                    range_counts, 
                    x='Energy Range', 
                    y='Number of Substations',
                    color='Energy Range',
                    color_discrete_map=color_map,
                    text='Number of Substations',
                    title='Substation Count by Input Energy Range'
                )
                fig_range.update_traces(textposition='outside', textfont=dict(size=12, weight='bold'))
                fig_range.update_layout(**dark_layout(height=400, showlegend=False))
                st.plotly_chart(fig_range, use_container_width=True, key="ss_range_bar", config=PLOTLY_CONFIG)
            
            with col2:
                fig_pie = px.pie(
                    range_counts,
                    values='Number of Substations',
                    names='Energy Range',
                    color='Energy Range',
                    color_discrete_map=color_map,
                    hole=0.4,
                    title='Percentage Distribution by Energy Range'
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(**dark_layout(height=400))
                st.plotly_chart(fig_pie, use_container_width=True, key="ss_range_pie", config=PLOTLY_CONFIG)
            
            st.markdown("---")
            
            # ── ZONE-WISE SUBSTATION OVERVIEW ───────────────────────────────────────
            st.markdown("### 🗺️ Zone-wise Substation Overview")
            
            if 'zone' in df.columns:
                zone_summary = df.groupby('zone').agg({
                    'substation': 'count',
                    'input_energy_kwh': 'sum',
                    'feeder_count': 'sum' if 'feeder_count' in df.columns else 'count',
                    'atc_loss_pct': 'mean',
                    'collection_efficiency_pct': 'mean'
                }).reset_index()
                
                zone_summary.columns = ['Zone', 'No. of Substations', 'Total Input (KWH)', 'Total Feeders', 'Avg AT&C %', 'Avg Collection %']
                zone_summary['Total Input (MU)'] = (zone_summary['Total Input (KWH)'] / 1e6).round(2)
                zone_summary = zone_summary.drop('Total Input (KWH)', axis=1)
                
                # Sort by number of substations
                zone_summary = zone_summary.sort_values('No. of Substations', ascending=False)
                
                st.dataframe(
                    zone_summary.style
                    .format({
                        'No. of Substations': '{:,.0f}',
                        'Total Input (MU)': '{:.2f} MU',
                        'Total Feeders': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%',
                        'Avg Collection %': '{:.2f}%'
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("📌 Zones sorted by number of substations (highest first)")
            
            st.markdown("---")
            
            # ── CIRCLE-WISE SUBSTATION OVERVIEW (TOP 15) ────────────────────────────
            st.markdown("### 🏙️ Circle-wise Substation Overview (Top 15 by Substation Count)")
            
            if 'circle' in df.columns and 'zone' in df.columns:
                circle_summary = df.groupby(['zone', 'circle']).agg({
                    'substation': 'count',
                    'input_energy_kwh': 'sum',
                    'feeder_count': 'sum' if 'feeder_count' in df.columns else 'count',
                    'atc_loss_pct': 'mean'
                }).reset_index()
                
                circle_summary.columns = ['Zone', 'Circle', 'No. of Substations', 'Total Input (KWH)', 'Total Feeders', 'Avg AT&C %']
                circle_summary['Total Input (MU)'] = (circle_summary['Total Input (KWH)'] / 1e6).round(2)
                circle_summary = circle_summary.drop('Total Input (KWH)', axis=1)
                
                # Sort and show top 15
                circle_summary = circle_summary.sort_values('No. of Substations', ascending=False).head(15)
                
                st.dataframe(
                    circle_summary.style
                    .format({
                        'No. of Substations': '{:,.0f}',
                        'Total Input (MU)': '{:.2f} MU',
                        'Total Feeders': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%'
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("📌 Showing top 15 circles by substation count")
            
            st.markdown("---")
            
            # ── DIVISION-WISE SUBSTATION OVERVIEW (TOP 20) ──────────────────────────
            if 'division' in df.columns:
                st.markdown("### 🏢 Division-wise Substation Overview (Top 20 by Substation Count)")
                
                div_summary = df.groupby(['zone', 'circle', 'division']).agg({
                    'substation': 'count',
                    'input_energy_kwh': 'sum',
                    'feeder_count': 'sum' if 'feeder_count' in df.columns else 'count',
                    'atc_loss_pct': 'mean'
                }).reset_index()
                
                div_summary.columns = ['Zone', 'Circle', 'Division', 'No. of Substations', 'Total Input (KWH)', 'Total Feeders', 'Avg AT&C %']
                div_summary['Total Input (MU)'] = (div_summary['Total Input (KWH)'] / 1e6).round(2)
                div_summary = div_summary.drop('Total Input (KWH)', axis=1)
                
                # Sort and show top 20
                div_summary = div_summary.sort_values('No. of Substations', ascending=False).head(20)
                
                st.dataframe(
                    div_summary.style
                    .format({
                        'No. of Substations': '{:,.0f}',
                        'Total Input (MU)': '{:.2f} MU',
                        'Total Feeders': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%'
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("📌 Showing top 20 divisions by substation count")
            
            st.markdown("---")
            
            # ── DETAILED SUBSTATION LIST BY ENERGY RANGE ────────────────────────────
            st.markdown("### 🔍 Detailed Substation List by Energy Range")
            
            # Range selector for detailed view
            selected_range = st.selectbox(
                "Select Energy Range to View Substations:",
                ["All Substations"] + [rg["name"] for rg in energy_ranges],
                key="ss_range_select"
            )
            
            # Filter substations based on selection
            if selected_range == "All Substations":
                filtered_df = df.copy()
            else:
                filtered_df = df[df['energy_range'] == selected_range].copy()
            
            if not filtered_df.empty:
                st.markdown(f"**Showing {len(filtered_df)} substations**")
                
                # Select columns for display
                display_cols = ['substation', 'zone', 'circle', 'division']
                if 'feeder_count' in filtered_df.columns:
                    display_cols.append('feeder_count')
                display_cols.extend(['input_energy_kwh', 'atc_loss_pct', 'collection_efficiency_pct', 'line_loss_pct'])
                
                available_cols = [c for c in display_cols if c in filtered_df.columns]
                detail_df = filtered_df[available_cols].copy()
                
                # Rename columns for display
                detail_df = detail_df.rename(columns={
                    'substation': 'Substation',
                    'zone': 'Zone',
                    'circle': 'Circle',
                    'division': 'Division',
                    'feeder_count': 'Feeders',
                    'input_energy_kwh': 'Input Energy (MU)',
                    'atc_loss_pct': 'AT&C %',
                    'collection_efficiency_pct': 'Collection %',
                    'line_loss_pct': 'Line Loss %'
                })
                
                # Format Input Energy to MU
                if 'Input Energy (MU)' in detail_df.columns:
                    detail_df['Input Energy (MU)'] = (detail_df['Input Energy (MU)'] / 1e6).round(2)
                
                # Format percentages
                pct_cols = ['AT&C %', 'Collection %', 'Line Loss %']
                for col in pct_cols:
                    if col in detail_df.columns:
                        detail_df[col] = detail_df[col].round(2)
                
                # Sort by Input Energy descending
                if 'Input Energy (MU)' in detail_df.columns:
                    detail_df = detail_df.sort_values('Input Energy (MU)', ascending=False)
                
                # Display with color coding
                def highlight_atc(val):
                    if isinstance(val, (int, float)):
                        if val < 15:
                            return 'color: #22c55e; font-weight: bold'
                        elif val < 30:
                            return 'color: #84cc16; font-weight: bold'
                        elif val < 50:
                            return 'color: #eab308; font-weight: bold'
                        elif val < 75:
                            return 'color: #f97316; font-weight: bold'
                        else:
                            return 'color: #ef4444; font-weight: bold'
                    return ''
                
                if 'AT&C %' in detail_df.columns:
                    styled_detail = detail_df.style.map(highlight_atc, subset=['AT&C %'])
                else:
                    styled_detail = detail_df.style
                
                st.dataframe(
                    styled_detail.set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_detail = detail_df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 Download {selected_range} Substation List (CSV)",
                    data=csv_detail,
                    file_name=f"DVVNL_Substations_{selected_range.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info(f"No substations found in the '{selected_range}' range")
            
            st.markdown("---")
            
            # ── KEY INSIGHTS ───────────────────────────────────────────────────────
            st.markdown("### 📈 Key Insights")
            
            insight_col1, insight_col2, insight_col3 = st.columns(3)
            
            with insight_col1:
                # Highest consumption substation
                if 'input_energy_kwh' in df.columns and not df.empty:
                    max_sub = df.loc[df['input_energy_kwh'].idxmax()]
                    max_energy = max_sub['input_energy_kwh'] / 1e6
                    st.info(f"🏭 **Highest Energy Substation:** {max_sub.get('substation', 'Unknown')}\n\nInput: {max_energy:.2f} MU")
            
            with insight_col2:
                # Zone with most substations
                if 'zone' in df.columns:
                    top_zone = df['zone'].value_counts().index[0] if not df['zone'].value_counts().empty else "Unknown"
                    top_zone_count = df['zone'].value_counts().iloc[0] if not df['zone'].value_counts().empty else 0
                    st.success(f"🗺️ **Zone with Most Substations:** {top_zone}\n\n{top_zone_count} Substations")
            
            with insight_col3:
                # Circle with most substations
                if 'circle' in df.columns:
                    top_circle = df['circle'].value_counts().index[0] if not df['circle'].value_counts().empty else "Unknown"
                    top_circle_count = df['circle'].value_counts().iloc[0] if not df['circle'].value_counts().empty else 0
                    st.warning(f"🏙️ **Circle with Most Substations:** {top_circle}\n\n{top_circle_count} Substations")
            
            st.markdown("---")
            st.markdown("### 💡 Understanding Input Energy Ranges")
            st.info("""
            **Input Energy Ranges Classification:**
            - 🔴 **Very High (> 10 MU)** - Substations serving large industrial/commercial areas, priority for monitoring
            - 🟠 **High (5-10 MU)** - Major substations, regular performance review recommended
            - ⚠️ **Medium (2-5 MU)** - Standard substations, routine monitoring
            - 🟢 **Low (1-2 MU)** - Smaller substations, efficiency optimization opportunities
            - ✅ **Very Low (< 1 MU)** - Minimal load substations, consider consolidation
            
            **MU = Million Units (1 MU = 1,000,000 KWH)**
            """)
        
        else:
            st.warning("⚠️ Input Energy data (input_energy_kwh column) not available in the dataset.")

    # ══ STAB 2: AT&C DEEP DIVE ════════════════════════════════════════════════
    with stabs[1]:
        st.markdown(f"**ATC Substation Slab - {current_hierarchy}**")
        # if not hist_df.empty:
        #     st.plotly_chart(chart_loss_histogram(hist_df.rename(columns={"substation_count":"feeder_count"})),
        #                     use_container_width=True, key="ss_dd_hist", config=PLOTLY_CONFIG)

    # ══ STAB 10: SUBSTATION AT&C SLAB ANALYSIS ═══════════════════════════════════

        st.markdown("""
        <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
            <span style="color: #0f172a; font-size: 14px;">
            📌 <b>Substation AT&C Slab Analysis</b> 
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # ── AT&C SLAB DEFINITIONS ──────────────────────────────────────────────────
        atc_slabs = [
            {"name": "Excellent (<15%)", "min": -float('inf'), "max": 15, "color": "#22c55e", "icon": "✅"},
            {"name": "Good (15-30%)", "min": 15, "max": 30, "color": "#84cc16", "icon": "🟢"},
            {"name": "High (30-50%)", "min": 30, "max": 50, "color": "#eab308", "icon": "⚠️"},
            {"name": "Critical (50-75%)", "min": 50, "max": 75, "color": "#f97316", "icon": "🔴"},
            {"name": "Severe (≥75%)", "min": 75, "max": float('inf'), "color": "#ef4444", "icon": "💀"}
        ]
        
        # Function to classify AT&C into slab
        def get_atc_slab(atc_value):
            if pd.isna(atc_value):
                return "Excellent (<15%)"
            for slab in atc_slabs:
                if slab["min"] <= atc_value < slab["max"]:
                    return slab["name"]
            return "Excellent (<15%)"
        
        # Create AT&C slab column
        if 'atc_loss_pct' in df.columns:
            df['atc_slab'] = df['atc_loss_pct'].apply(get_atc_slab)
            total_substations = len(df)
            
            # # ── OVERALL STATISTICS CARDS ─────────────────────────────────────────────
            # st.markdown("### 📊 Overall AT&C Statistics")
            
            # col1, col2, col3, col4, col5 = st.columns(5)
            
            # with col1:
            #     st.metric("🏭 Total Substations", f"{total_substations:,}")
            
            # with col2:
            #     avg_atc = df['atc_loss_pct'].mean()
            #     st.metric("📊 Avg AT&C Loss", f"{avg_atc:.2f}%")
            
            # with col3:
            #     min_atc = df['atc_loss_pct'].min()
            #     st.metric("📉 Best AT&C", f"{min_atc:.2f}%")
            
            # with col4:
            #     max_atc = df['atc_loss_pct'].max()
            #     st.metric("📈 Worst AT&C", f"{max_atc:.2f}%")
            
            # with col5:
            #     std_atc = df['atc_loss_pct'].std()
            #     st.metric("📊 Std Deviation", f"{std_atc:.2f}%")
            
            # st.markdown("---")
            
            # ── SLAB DISTRIBUTION CARDS ─────────────────────────────────────────────
            st.markdown("### 📊 Substation Distribution by AT&C Slab")
            
            # Calculate slab counts
            slab_counts = df['atc_slab'].value_counts()
            for slab in atc_slabs:
                if slab["name"] not in slab_counts.index:
                    slab_counts[slab["name"]] = 0
            
            # Display as color-coded cards
            slab_cols = st.columns(len(atc_slabs))
            for idx, slab in enumerate(atc_slabs):
                if idx < len(slab_cols):
                    with slab_cols[idx]:
                        count = slab_counts.get(slab["name"], 0)
                        percentage = (count / total_substations * 100) if total_substations > 0 else 0
                        st.markdown(f"""
                        <div style="background:{slab['color']}15; border:3px solid {slab['color']}; border-radius:16px; padding:16px 8px; text-align:center;">
                            <div style="font-size:36px; font-weight:900; color:{slab['color']};">{count}</div>
                            <div style="font-size:11px; color:#64748b; font-weight:700;">{slab['name']}</div>
                            <div style="font-size:13px; font-weight:800; color:{slab['color']};">{slab['icon']}</div>
                            <div style="font-size:10px; color:#94a3b8;">{percentage:.1f}% of total</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Charts for slab distribution
            st.markdown("---")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                # Bar chart
                slab_df = pd.DataFrame({
                    'Slab': [s["name"] for s in atc_slabs],
                    'Count': [slab_counts.get(s["name"], 0) for s in atc_slabs],
                    'Color': [s["color"] for s in atc_slabs]
                })
                
                fig_bar = px.bar(
                    slab_df, x='Slab', y='Count',
                    color='Slab', color_discrete_sequence=[s["color"] for s in atc_slabs],
                    text='Count', title='Substation Count by AT&C Slab'
                )
                fig_bar.update_traces(textposition='outside', textfont=dict(size=12, weight='bold'))
                fig_bar.update_layout(**dark_layout(height=400, showlegend=False))
                st.plotly_chart(fig_bar, use_container_width=True, key="ss_atc_slab_bar", config=PLOTLY_CONFIG)
            
            with chart_col2:
                # Pie chart
                fig_pie = px.pie(
                    slab_df, values='Count', names='Slab',
                    color='Slab', color_discrete_sequence=[s["color"] for s in atc_slabs],
                    hole=0.4, title='Percentage Distribution by AT&C Slab'
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(**dark_layout(height=400))
                st.plotly_chart(fig_pie, use_container_width=True, key="ss_atc_slab_pie", config=PLOTLY_CONFIG)
            
            st.markdown("---")
            
            # ── ZONE-WISE AT&C SLAB ANALYSIS ────────────────────────────────────────
            st.markdown("### 🗺️ Zone-wise AT&C Slab Distribution")
            
            if 'zone' in df.columns:
                # Create zone-wise slab summary
                zone_slab = pd.crosstab(df['zone'], df['atc_slab'], margins=True, margins_name='Total')
                zone_slab = zone_slab.drop('Total', axis=0) if 'Total' in zone_slab.index else zone_slab
                
                # Add total substations per zone
                zone_totals = df.groupby('zone').size().reset_index(name='Total Substations')
                zone_avg_atc = df.groupby('zone')['atc_loss_pct'].mean().round(2).reset_index(name='Avg AT&C %')
                
                # Merge
                zone_summary = zone_totals.merge(zone_avg_atc, on='zone')
                
                # Add slab counts
                for slab in atc_slabs:
                    slab_name = slab["name"]
                    if slab_name in zone_slab.columns:
                        zone_summary = zone_summary.merge(
                            zone_slab[[slab_name]].reset_index().rename(columns={slab_name: f'{slab_name}_count'}),
                            left_on='zone', right_on='zone', how='left'
                        )
                        zone_summary[f'{slab_name}_count'] = zone_summary[f'{slab_name}_count'].fillna(0).astype(int)
                        zone_summary[f'{slab_name}_pct'] = (zone_summary[f'{slab_name}_count'] / zone_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'Total Substations', 'Avg AT&C %']
                for slab in atc_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                zone_summary = zone_summary[[c for c in display_cols if c in zone_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'Total Substations': 'Total Substations', 'Avg AT&C %': 'Avg AT&C %'}
                for slab in atc_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                zone_summary = zone_summary.rename(columns=rename_dict)
                
                # Sort by Total Substations
                zone_summary = zone_summary.sort_values('Total Substations', ascending=False)
                
                # Display
                st.dataframe(
                    zone_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in atc_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in atc_slabs}
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_zone = zone_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Zone-wise AT&C Slab Summary (CSV)",
                    data=csv_zone,
                    file_name=f"DVVNL_Substation_Zone_ATAC_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── CIRCLE-WISE AT&C SLAB ANALYSIS (TOP 20) ─────────────────────────────
            st.markdown("### 🏙️ Circle-wise AT&C Slab Distribution (Top 20 by Substation Count)")
            
            if 'circle' in df.columns and 'zone' in df.columns:
                # Create circle-wise summary
                circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Substations')
                circle_avg_atc = df.groupby(['zone', 'circle'])['atc_loss_pct'].mean().round(2).reset_index(name='Avg AT&C %')
                
                circle_summary = circle_totals.merge(circle_avg_atc, on=['zone', 'circle'])
                
                # Add slab counts
                for slab in atc_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['atc_slab'] == slab_name].groupby(['zone', 'circle']).size().reset_index(name=f'{slab_name}_count')
                    circle_summary = circle_summary.merge(slab_count, on=['zone', 'circle'], how='left')
                    circle_summary[f'{slab_name}_count'] = circle_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    circle_summary[f'{slab_name}_pct'] = (circle_summary[f'{slab_name}_count'] / circle_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'Total Substations', 'Avg AT&C %']
                for slab in atc_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                circle_summary = circle_summary[[c for c in display_cols if c in circle_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'Total Substations': 'Total Substations', 'Avg AT&C %': 'Avg AT&C %'}
                for slab in atc_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                circle_summary = circle_summary.rename(columns=rename_dict)
                
                # Sort and show top 20
                circle_summary = circle_summary.sort_values('Total Substations', ascending=False).head(20)
                
                st.dataframe(
                    circle_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in atc_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in atc_slabs}
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 20 circles by substation count. Total circles: {circle_summary['Circle'].nunique() if not circle_summary.empty else 0}")
                
                # Download button
                csv_circle = circle_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Circle-wise AT&C Slab Summary (CSV)",
                    data=csv_circle,
                    file_name=f"DVVNL_Substation_Circle_ATAC_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DIVISION-WISE AT&C SLAB ANALYSIS (TOP 30) ───────────────────────────
            if 'division' in df.columns:
                st.markdown("### 🏢 Division-wise AT&C Slab Distribution (Top 30 by Substation Count)")
                
                # Create division-wise summary
                div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Substations')
                div_avg_atc = df.groupby(['zone', 'circle', 'division'])['atc_loss_pct'].mean().round(2).reset_index(name='Avg AT&C %')
                
                div_summary = div_totals.merge(div_avg_atc, on=['zone', 'circle', 'division'])
                
                # Add slab counts
                for slab in atc_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['atc_slab'] == slab_name].groupby(['zone', 'circle', 'division']).size().reset_index(name=f'{slab_name}_count')
                    div_summary = div_summary.merge(slab_count, on=['zone', 'circle', 'division'], how='left')
                    div_summary[f'{slab_name}_count'] = div_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    div_summary[f'{slab_name}_pct'] = (div_summary[f'{slab_name}_count'] / div_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'division', 'Total Substations', 'Avg AT&C %']
                for slab in atc_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                div_summary = div_summary[[c for c in display_cols if c in div_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'division': 'Division', 
                               'Total Substations': 'Total Substations', 'Avg AT&C %': 'Avg AT&C %'}
                for slab in atc_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                div_summary = div_summary.rename(columns=rename_dict)
                
                # Sort and show top 30
                div_summary = div_summary.sort_values('Total Substations', ascending=False).head(30)
                
                st.dataframe(
                    div_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg AT&C %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in atc_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in atc_slabs}
                    })
                    .background_gradient(subset=['Avg AT&C %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 30 divisions by substation count. Total divisions: {div_summary['Division'].nunique() if not div_summary.empty else 0}")
                
                # Download button
                csv_division = div_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Division-wise AT&C Slab Summary (CSV)",
                    data=csv_division,
                    file_name=f"DVVNL_Substation_Division_ATAC_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DETAILED SUBSTATION LIST BY AT&C SLAB ───────────────────────────────
            st.markdown("### 🔍 Detailed Substation List by AT&C Slab")
            
            # Slab selector
            selected_slab = st.selectbox(
                "Select AT&C Slab to View Substations:",
                ["All Substations"] + [s["name"] for s in atc_slabs],
                key="ss_atc_slab_select"
            )
            
            # Filter substations
            if selected_slab == "All Substations":
                slab_filtered_df = df.copy()
            else:
                slab_filtered_df = df[df['atc_slab'] == selected_slab].copy()
            
            if not slab_filtered_df.empty:
                st.markdown(f"**Showing {len(slab_filtered_df)} substations**")
                
                # Select columns for display
                detail_cols = ['substation', 'zone', 'circle', 'division']
                if 'feeder_count' in slab_filtered_df.columns:
                    detail_cols.append('feeder_count')
                detail_cols.extend(['input_energy_kwh', 'atc_loss_pct', 'collection_efficiency_pct', 'line_loss_pct'])
                
                available_detail = [c for c in detail_cols if c in slab_filtered_df.columns]
                detail_sub_df = slab_filtered_df[available_detail].copy()
                
                # Rename columns
                detail_sub_df = detail_sub_df.rename(columns={
                    'substation': 'Substation',
                    'zone': 'Zone',
                    'circle': 'Circle',
                    'division': 'Division',
                    'feeder_count': 'Feeders',
                    'input_energy_kwh': 'Input Energy (MU)',
                    'atc_loss_pct': 'AT&C %',
                    'collection_efficiency_pct': 'Collection %',
                    'line_loss_pct': 'Line Loss %'
                })
                
                # Format Input Energy to MU
                if 'Input Energy (MU)' in detail_sub_df.columns:
                    detail_sub_df['Input Energy (MU)'] = (detail_sub_df['Input Energy (MU)'] / 1e6).round(2)
                
                # Sort by AT&C % descending
                if 'AT&C %' in detail_sub_df.columns:
                    detail_sub_df = detail_sub_df.sort_values('AT&C %', ascending=False)
                
                # Color coding function for AT&C
                def highlight_sub_atc(val):
                    if isinstance(val, (int, float)):
                        if val < 15:
                            return 'color: #22c55e; font-weight: bold'
                        elif val < 30:
                            return 'color: #84cc16; font-weight: bold'
                        elif val < 50:
                            return 'color: #eab308; font-weight: bold'
                        elif val < 75:
                            return 'color: #f97316; font-weight: bold'
                        else:
                            return 'color: #ef4444; font-weight: bold'
                    return ''
                
                # Apply styling
                styled_detail_sub = detail_sub_df.style.map(highlight_sub_atc, subset=['AT&C %'] if 'AT&C %' in detail_sub_df.columns else [])
                
                st.dataframe(
                    styled_detail_sub.set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_detail_sub = detail_sub_df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 Download {selected_slab} Substation List (CSV)",
                    data=csv_detail_sub,
                    file_name=f"DVVNL_Substations_ATAC_{selected_slab.replace(' ', '_').replace('%', 'pct')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info(f"No substations found in the '{selected_slab}' slab")
            
            st.markdown("---")
            
            # ── KEY INSIGHTS ───────────────────────────────────────────────────────
            st.markdown("### 📈 Key Insights")
            
            insight_col1, insight_col2, insight_col3 = st.columns(3)
            
            with insight_col1:
                # Best performing zone
                if 'zone' in df.columns:
                    zone_avg = df.groupby('zone')['atc_loss_pct'].mean()
                    if not zone_avg.empty:
                        best_zone = zone_avg.idxmin()
                        best_zone_atc = zone_avg.min()
                        st.success(f"🏆 **Best Performing Zone:** {best_zone}\n\nAvg AT&C: {best_zone_atc:.2f}%")
            
            with insight_col2:
                # Worst performing zone
                if 'zone' in df.columns:
                    worst_zone = zone_avg.idxmax() if not zone_avg.empty else None
                    worst_zone_atc = zone_avg.max() if not zone_avg.empty else 0
                    if worst_zone:
                        st.warning(f"⚠️ **Needs Improvement Zone:** {worst_zone}\n\nAvg AT&C: {worst_zone_atc:.2f}%")
            
            with insight_col3:
                # Most common slab
                most_common = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
                most_common_count = slab_counts.max() if not slab_counts.empty else 0
                st.info(f"📊 **Most Common Slab:** {most_common}\n\n{most_common_count:,} Substations ({most_common_count/total_substations*100:.1f}%)")
            
            # st.markdown("---")
            # st.markdown("### 💡 Understanding AT&C Loss for Substations")
            # st.info("""
            # **AT&C Loss (Aggregate Technical & Commercial Loss) for Substations represents:**
            # - Technical losses: Energy lost in transformers and feeders
            # - Commercial losses: Theft, metering inaccuracies, billing inefficiencies
            
            # **Slab Classifications:**
            # - ✅ **Excellent (<15%)** - Optimal performance, benchmark for others
            # - 🟢 **Good (15-30%)** - Acceptable range, monitor regularly
            # - ⚠️ **High (30-50%)** - Needs attention, investigate root causes
            # - 🔴 **Critical (50-75%)** - Serious issues, immediate action required
            # - 💀 **Severe (≥75%)** - Critical infrastructure problems, urgent intervention needed
            
            # **Action Items:**
            # - Priority: Focus on Critical and Severe slabs first
            # - Investigate: High slab substations for pattern analysis
            # - Replicate: Best practices from Excellent slab substations
            # """)
        
        else:
            st.warning("⚠️ AT&C Loss data (atc_loss_pct column) not available in the dataset.")



    # ══ STAB 3: ENERGY ════════════════════════════════════════════════════════
    with stabs[2]:
        if not zone_df.empty:
            col1,col2 = st.columns(2)
            with col1:
                st.markdown(f"**{current_hierarchy} - Zone Energy: Input vs Sold**")
                fig = go.Figure()
                if "total_input" in zone_df.columns:
                    fig.add_trace(go.Bar(name="Input KWH", x=zone_df["zone"], y=zone_df["total_input"],  marker_color="#6366f1"))
                    fig.add_trace(go.Bar(name="Sold KWH",  x=zone_df["zone"], y=zone_df["total_sold"],   marker_color="#22c55e"))
                fig.update_layout(**dark_layout(barmode="group"))
                st.plotly_chart(fig, use_container_width=True, key="ss_en_zone", config=PLOTLY_CONFIG)
            with col2:
                st.markdown(f"**{current_hierarchy} - Zone Line Loss %**")
                if "line_loss_pct" in zone_df.columns:
                    fig2 = px.bar(zone_df, x="zone", y="line_loss_pct", color="line_loss_pct",
                                  color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]])
                    fig2.update_layout(**dark_layout(showlegend=False))
                    st.plotly_chart(fig2, use_container_width=True, key="ss_en_ll", config=PLOTLY_CONFIG)



    # ══ STAB 11: SUBSTATION LINE LOSS ANALYSIS ═══════════════════════════════════
    # with stabs[10]:
    #     st.markdown('<div class="section-title">📉 Substation Line Loss Analysis - Zone | Circle | Division</div>',
    #                 unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
            <span style="color: #0f172a; font-size: 14px;">
            📌 <b>Substation Line Loss Analysis:</b> Analyze technical losses across substations at Zone, Circle, and Division levels.
            Identify high-loss substations for improvement and efficiency optimization.
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # ── LINE LOSS SLAB DEFINITIONS ─────────────────────────────────────────────
        line_loss_slabs = [
            {"name": "Excellent (<10%)", "min": -float('inf'), "max": 10, "color": "#22c55e", "icon": "✅"},
            {"name": "Good (10-15%)", "min": 10, "max": 15, "color": "#84cc16", "icon": "🟢"},
            {"name": "Moderate (15-25%)", "min": 15, "max": 25, "color": "#eab308", "icon": "⚠️"},
            {"name": "High (25-40%)", "min": 25, "max": 40, "color": "#f97316", "icon": "🔴"},
            {"name": "Severe (≥40%)", "min": 40, "max": float('inf'), "color": "#ef4444", "icon": "💀"}
        ]
        
        # Function to classify Line Loss into slab
        def get_line_loss_slab(ll_value):
            if pd.isna(ll_value):
                return "Excellent (<10%)"
            # Ensure numeric value
            try:
                value = float(ll_value)
            except (ValueError, TypeError):
                return "Excellent (<10%)"
            for slab in line_loss_slabs:
                if slab["min"] <= value < slab["max"]:
                    return slab["name"]
            return "Severe (≥40%)"  # Fallback for values >=40
        
        # Create line loss slab column
        if 'line_loss_pct' in df.columns:
            df['line_loss_slab'] = df['line_loss_pct'].apply(get_line_loss_slab)
            total_substations = len(df)
            
            # ── OVERALL STATISTICS CARDS ─────────────────────────────────────────────
            # st.markdown("### 📊 Overall Line Loss Statistics")
            
            # col1, col2, col3, col4, col5 = st.columns(5)
            
            # with col1:
            #     st.metric("🏭 Total Substations", f"{total_substations:,}")
            
            # with col2:
            #     avg_ll = df['line_loss_pct'].mean()
            #     st.metric("📊 Avg Line Loss", f"{avg_ll:.2f}%")
            
            # with col3:
            #     min_ll = df['line_loss_pct'].min()
            #     st.metric("📉 Best Line Loss", f"{min_ll:.2f}%")
            
            # with col4:
            #     max_ll = df['line_loss_pct'].max()
            #     st.metric("📈 Worst Line Loss", f"{max_ll:.2f}%")
            
            # with col5:
            #     std_ll = df['line_loss_pct'].std()
            #     st.metric("📊 Std Deviation", f"{std_ll:.2f}%")
            
            # st.markdown("---")
            
            # ── SLAB DISTRIBUTION CARDS ─────────────────────────────────────────────
            st.markdown("### 📊 Substation Distribution by Line Loss Slab")
            
            # Calculate slab counts
            slab_counts = df['line_loss_slab'].value_counts()
            for slab in line_loss_slabs:
                if slab["name"] not in slab_counts.index:
                    slab_counts[slab["name"]] = 0
            
            # Display as color-coded cards
            slab_cols = st.columns(len(line_loss_slabs))
            for idx, slab in enumerate(line_loss_slabs):
                if idx < len(slab_cols):
                    with slab_cols[idx]:
                        count = slab_counts.get(slab["name"], 0)
                        percentage = (count / total_substations * 100) if total_substations > 0 else 0
                        st.markdown(f"""
                        <div style="background:{slab['color']}15; border:3px solid {slab['color']}; border-radius:16px; padding:16px 8px; text-align:center;">
                            <div style="font-size:36px; font-weight:900; color:{slab['color']};">{count}</div>
                            <div style="font-size:11px; color:#64748b; font-weight:700;">{slab['name']}</div>
                            <div style="font-size:13px; font-weight:800; color:{slab['color']};">{slab['icon']}</div>
                            <div style="font-size:10px; color:#94a3b8;">{percentage:.1f}% of total</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Charts for slab distribution
            st.markdown("---")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                # Bar chart
                slab_df = pd.DataFrame({
                    'Slab': [s["name"] for s in line_loss_slabs],
                    'Count': [slab_counts.get(s["name"], 0) for s in line_loss_slabs],
                    'Color': [s["color"] for s in line_loss_slabs]
                })
                
                fig_bar = px.bar(
                    slab_df, x='Slab', y='Count',
                    color='Slab', color_discrete_sequence=[s["color"] for s in line_loss_slabs],
                    text='Count', title='Substation Count by Line Loss Slab'
                )
                fig_bar.update_traces(textposition='outside', textfont=dict(size=12, weight='bold'))
                fig_bar.update_layout(**dark_layout(height=400, showlegend=False))
                st.plotly_chart(fig_bar, use_container_width=True, key="ss_ll_slab_bar", config=PLOTLY_CONFIG)
            
            with chart_col2:
                # Pie chart
                fig_pie = px.pie(
                    slab_df, values='Count', names='Slab',
                    color='Slab', color_discrete_sequence=[s["color"] for s in line_loss_slabs],
                    hole=0.4, title='Percentage Distribution by Line Loss Slab'
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(**dark_layout(height=400))
                st.plotly_chart(fig_pie, use_container_width=True, key="ss_ll_slab_pie", config=PLOTLY_CONFIG)
            
            st.markdown("---")
            
            # ── ZONE-WISE LINE LOSS SLAB ANALYSIS ───────────────────────────────────
            st.markdown("### 🗺️ Zone-wise Line Loss Distribution")
            
            if 'zone' in df.columns:
                # Create zone-wise slab summary
                zone_slab = pd.crosstab(df['zone'], df['line_loss_slab'], margins=True, margins_name='Total')
                zone_slab = zone_slab.drop('Total', axis=0) if 'Total' in zone_slab.index else zone_slab
                
                # Add total substations per zone
                zone_totals = df.groupby('zone').size().reset_index(name='Total Substations')
                zone_avg_ll = df.groupby('zone')['line_loss_pct'].mean().round(2).reset_index(name='Avg Line Loss %')
                
                # Merge
                zone_summary = zone_totals.merge(zone_avg_ll, on='zone')
                
                # Add slab counts
                for slab in line_loss_slabs:
                    slab_name = slab["name"]
                    if slab_name in zone_slab.columns:
                        zone_summary = zone_summary.merge(
                            zone_slab[[slab_name]].reset_index().rename(columns={slab_name: f'{slab_name}_count'}),
                            left_on='zone', right_on='zone', how='left'
                        )
                        zone_summary[f'{slab_name}_count'] = zone_summary[f'{slab_name}_count'].fillna(0).astype(int)
                        zone_summary[f'{slab_name}_pct'] = (zone_summary[f'{slab_name}_count'] / zone_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'Total Substations', 'Avg Line Loss %']
                for slab in line_loss_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                zone_summary = zone_summary[[c for c in display_cols if c in zone_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'Total Substations': 'Total Substations', 'Avg Line Loss %': 'Avg Line Loss %'}
                for slab in line_loss_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                zone_summary = zone_summary.rename(columns=rename_dict)
                
                # Sort by Total Substations
                zone_summary = zone_summary.sort_values('Total Substations', ascending=False)
                
                # Display
                st.dataframe(
                    zone_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Line Loss %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                    })
                    .background_gradient(subset=['Avg Line Loss %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_zone = zone_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Zone-wise Line Loss Slab Summary (CSV)",
                    data=csv_zone,
                    file_name=f"DVVNL_Substation_Zone_LineLoss_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── CIRCLE-WISE LINE LOSS SLAB ANALYSIS (TOP 20) ─────────────────────────
            st.markdown("### 🏙️ Circle-wise Line Loss Distribution (Top 20 by Substation Count)")
            
            if 'circle' in df.columns and 'zone' in df.columns:
                # Create circle-wise summary
                circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Substations')
                circle_avg_ll = df.groupby(['zone', 'circle'])['line_loss_pct'].mean().round(2).reset_index(name='Avg Line Loss %')
                
                circle_summary = circle_totals.merge(circle_avg_ll, on=['zone', 'circle'])
                
                # Add slab counts
                for slab in line_loss_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['line_loss_slab'] == slab_name].groupby(['zone', 'circle']).size().reset_index(name=f'{slab_name}_count')
                    circle_summary = circle_summary.merge(slab_count, on=['zone', 'circle'], how='left')
                    circle_summary[f'{slab_name}_count'] = circle_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    circle_summary[f'{slab_name}_pct'] = (circle_summary[f'{slab_name}_count'] / circle_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'Total Substations', 'Avg Line Loss %']
                for slab in line_loss_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                circle_summary = circle_summary[[c for c in display_cols if c in circle_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'Total Substations': 'Total Substations', 'Avg Line Loss %': 'Avg Line Loss %'}
                for slab in line_loss_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                circle_summary = circle_summary.rename(columns=rename_dict)
                
                # Sort and show top 20
                circle_summary = circle_summary.sort_values('Total Substations', ascending=False).head(20)
                
                st.dataframe(
                    circle_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Line Loss %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                    })
                    .background_gradient(subset=['Avg Line Loss %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 20 circles by substation count. Total circles: {circle_summary['Circle'].nunique() if not circle_summary.empty else 0}")
                
                # Download button
                csv_circle = circle_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Circle-wise Line Loss Slab Summary (CSV)",
                    data=csv_circle,
                    file_name=f"DVVNL_Substation_Circle_LineLoss_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DIVISION-WISE LINE LOSS SLAB ANALYSIS (TOP 30) ───────────────────────
            if 'division' in df.columns:
                st.markdown("### 🏢 Division-wise Line Loss Distribution (Top 30 by Substation Count)")
                
                # Create division-wise summary
                div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Substations')
                div_avg_ll = df.groupby(['zone', 'circle', 'division'])['line_loss_pct'].mean().round(2).reset_index(name='Avg Line Loss %')
                
                div_summary = div_totals.merge(div_avg_ll, on=['zone', 'circle', 'division'])
                
                # Add slab counts
                for slab in line_loss_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['line_loss_slab'] == slab_name].groupby(['zone', 'circle', 'division']).size().reset_index(name=f'{slab_name}_count')
                    div_summary = div_summary.merge(slab_count, on=['zone', 'circle', 'division'], how='left')
                    div_summary[f'{slab_name}_count'] = div_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    div_summary[f'{slab_name}_pct'] = (div_summary[f'{slab_name}_count'] / div_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'division', 'Total Substations', 'Avg Line Loss %']
                for slab in line_loss_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                div_summary = div_summary[[c for c in display_cols if c in div_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'division': 'Division', 
                               'Total Substations': 'Total Substations', 'Avg Line Loss %': 'Avg Line Loss %'}
                for slab in line_loss_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                div_summary = div_summary.rename(columns=rename_dict)
                
                # Sort and show top 30
                div_summary = div_summary.sort_values('Total Substations', ascending=False).head(30)
                
                st.dataframe(
                    div_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Line Loss %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in line_loss_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in line_loss_slabs}
                    })
                    .background_gradient(subset=['Avg Line Loss %'], cmap='RdYlGn_r', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 30 divisions by substation count. Total divisions: {div_summary['Division'].nunique() if not div_summary.empty else 0}")
                
                # Download button
                csv_division = div_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Division-wise Line Loss Slab Summary (CSV)",
                    data=csv_division,
                    file_name=f"DVVNL_Substation_Division_LineLoss_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DETAILED SUBSTATION LIST BY LINE LOSS SLAB ───────────────────────────
            st.markdown("### 🔍 Detailed Substation List by Line Loss Slab")
            
            # Slab selector
            selected_slab = st.selectbox(
                "Select Line Loss Slab to View Substations:",
                ["All Substations"] + [s["name"] for s in line_loss_slabs],
                key="ss_ll_slab_select"
            )
            
            # Filter substations
            if selected_slab == "All Substations":
                slab_filtered_df = df.copy()
            else:
                slab_filtered_df = df[df['line_loss_slab'] == selected_slab].copy()
            
            if not slab_filtered_df.empty:
                st.markdown(f"**Showing {len(slab_filtered_df)} substations**")
                
                # Select columns for display
                detail_cols = ['substation', 'zone', 'circle', 'division']
                if 'feeder_count' in slab_filtered_df.columns:
                    detail_cols.append('feeder_count')
                detail_cols.extend(['input_energy_kwh', 'line_loss_pct', 'atc_loss_pct', 'collection_efficiency_pct'])
                
                available_detail = [c for c in detail_cols if c in slab_filtered_df.columns]
                detail_sub_df = slab_filtered_df[available_detail].copy()
                
                # Rename columns
                detail_sub_df = detail_sub_df.rename(columns={
                    'substation': 'Substation',
                    'zone': 'Zone',
                    'circle': 'Circle',
                    'division': 'Division',
                    'feeder_count': 'Feeders',
                    'input_energy_kwh': 'Input Energy (MU)',
                    'line_loss_pct': 'Line Loss %',
                    'atc_loss_pct': 'AT&C %',
                    'collection_efficiency_pct': 'Collection %'
                })
                
                # Format Input Energy to MU
                if 'Input Energy (MU)' in detail_sub_df.columns:
                    detail_sub_df['Input Energy (MU)'] = (detail_sub_df['Input Energy (MU)'] / 1e6).round(2)
                
                # Sort by Line Loss % descending
                if 'Line Loss %' in detail_sub_df.columns:
                    detail_sub_df = detail_sub_df.sort_values('Line Loss %', ascending=False)
                
                # Color coding function for Line Loss
                def highlight_line_loss(val):
                    if isinstance(val, (int, float)):
                        if val < 10:
                            return 'color: #22c55e; font-weight: bold'
                        elif val < 15:
                            return 'color: #84cc16; font-weight: bold'
                        elif val < 25:
                            return 'color: #eab308; font-weight: bold'
                        elif val < 40:
                            return 'color: #f97316; font-weight: bold'
                        else:
                            return 'color: #ef4444; font-weight: bold'
                    return ''
                
                # Apply styling
                styled_detail_sub = detail_sub_df.style.map(highlight_line_loss, subset=['Line Loss %'] if 'Line Loss %' in detail_sub_df.columns else [])
                
                st.dataframe(
                    styled_detail_sub.set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_detail_sub = detail_sub_df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 Download {selected_slab} Substation List (CSV)",
                    data=csv_detail_sub,
                    file_name=f"DVVNL_Substations_LineLoss_{selected_slab.replace(' ', '_').replace('%', 'pct')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info(f"No substations found in the '{selected_slab}' slab")
            
            st.markdown("---")
            
            # # ── KEY INSIGHTS ───────────────────────────────────────────────────────
            # st.markdown("### 📈 Key Insights")
            
            # insight_col1, insight_col2, insight_col3 = st.columns(3)
            
            # with insight_col1:
            #     # Best performing zone (lowest line loss)
            #     if 'zone' in df.columns:
            #         zone_avg_ll = df.groupby('zone')['line_loss_pct'].mean()
            #         if not zone_avg_ll.empty:
            #             best_zone = zone_avg_ll.idxmin()
            #             best_zone_ll = zone_avg_ll.min()
            #             st.success(f"🏆 **Best Zone (Lowest Line Loss):** {best_zone}\n\nAvg Line Loss: {best_zone_ll:.2f}%")
            
            # with insight_col2:
            #     # Worst performing zone (highest line loss)
            #     if 'zone' in df.columns:
            #         worst_zone = zone_avg_ll.idxmax() if not zone_avg_ll.empty else None
            #         worst_zone_ll = zone_avg_ll.max() if not zone_avg_ll.empty else 0
            #         if worst_zone:
            #             st.warning(f"⚠️ **Needs Improvement Zone:** {worst_zone}\n\nAvg Line Loss: {worst_zone_ll:.2f}%")
            
            # with insight_col3:
            #     # Most common slab
            #     most_common = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
            #     most_common_count = slab_counts.max() if not slab_counts.empty else 0
            #     st.info(f"📊 **Most Common Slab:** {most_common}\n\n{most_common_count:,} Substations ({most_common_count/total_substations*100:.1f}%)")
            
            # st.markdown("---")
            
            # # ── HIGH LINE LOSS SUBSTATIONS ALERT ───────────────────────────────────
            # if 'line_loss_pct' in df.columns:
            #     high_loss = df[df['line_loss_pct'] >= 25]
            #     if not high_loss.empty:
            #         with st.expander(f"⚠️ {len(high_loss)} Substations with High Line Loss (≥25%)", expanded=False):
            #             for _, row in high_loss.iterrows():
            #                 ca, cb, cc, cd = st.columns([3, 1, 1, 1])
            #                 with ca:
            #                     st.markdown(f"**{row.get('substation', '?')}** - {row.get('zone', '')} / {row.get('circle', '')}")
            #                 with cb:
            #                     st.markdown(f"<span style='color:#ef4444;font-weight:800'>Line Loss: {row.get('line_loss_pct', 0):.1f}%</span>", unsafe_allow_html=True)
            #                 with cc:
            #                     st.markdown(f"<span style='color:#f97316'>Input: {row.get('input_energy_kwh', 0)/1e6:.1f} MU</span>", unsafe_allow_html=True)
            #                 with cd:
            #                     st.markdown(f"<span style='color:#eab308'>AT&C: {row.get('atc_loss_pct', 0):.1f}%</span>", unsafe_allow_html=True)
            
            # st.markdown("---")
            # st.markdown("### 💡 Understanding Line Loss for Substations")
            # st.info("""
            # **Line Loss (Technical Loss)** for substations represents energy lost during transformation and distribution:
            
            # **Components of Line Loss:**
            # - Transformer losses (core losses + copper losses)
            # - Feeder losses (I²R losses in conductors)
            # - Reactive power losses
            
            # **Slab Classifications:**
            # - ✅ **Excellent (<10%)** - Optimal technical performance
            # - 🟢 **Good (10-15%)** - Acceptable range
            # - ⚠️ **Moderate (15-25%)** - Needs investigation
            # - 🔴 **High (25-40%)** - Immediate action required
            # - 💀 **Severe (≥40%)** - Critical infrastructure issues
            
            # **Action Items:**
            # - Priority: Upgrade transformers in Severe and High slabs
            # - Investigate: Overloading, poor power factor, aging infrastructure
            # - Optimize: Load balancing, capacitor banks, conductor upgrade
            # - Replicate: Best practices from Excellent slab substations
            
            # **Note:** Negative line loss values are included in Excellent category.
            # """)
        
        else:
            st.warning("⚠️ Line Loss data (line_loss_pct column) not available in the dataset.")







    # ══ STAB 4: REVENUE ═══════════════════════════════════════════════════════
    with stabs[3]:
        st.plotly_chart(chart_funnel(funnel_data), use_container_width=True, key="ss_rev_funnel", config=PLOTLY_CONFIG)
        
        # if all(c in df.columns for c in ["tariff_subsidy","ptw_subsidy","powerloom_subsidy"]):
        #     st.markdown(f"**Subsidy Components (₹) — Top 25 - {current_hierarchy}**")
        #     df_sub = df[["substation","tariff_subsidy","ptw_subsidy","powerloom_subsidy"]].copy()
        #     df_sub = df_sub[df_sub[["tariff_subsidy","ptw_subsidy","powerloom_subsidy"]].sum(axis=1) > 0].head(25)
        #     if not df_sub.empty:
        #         fig_sub = go.Figure()
        #         fig_sub.add_trace(go.Bar(name="Tariff Subsidy",x=df_sub["substation"],y=df_sub["tariff_subsidy"],marker_color="#fbbf24"))
        #         fig_sub.add_trace(go.Bar(name="PTW Subsidy",   x=df_sub["substation"],y=df_sub["ptw_subsidy"],   marker_color="#0ea5e9"))
        #         fig_sub.add_trace(go.Bar(name="Powerloom",     x=df_sub["substation"],y=df_sub["powerloom_subsidy"],marker_color="#8b5cf6"))
        #         fig_sub.update_layout(**dark_layout(barmode="stack", xaxis_tickangle=-45))
        #         st.plotly_chart(fig_sub, use_container_width=True, key="ss_rev_sub", config=PLOTLY_CONFIG)

    # ══ STAB 12: SUBSTATION COLLECTION EFFICIENCY ANALYSIS ════════════════════════
    # with stabs[11]:
    #     st.markdown('<div class="section-title">💰 Substation Collection Efficiency Analysis - Zone | Circle | Division</div>',
    #                 unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
            <span style="color: #0f172a; font-size: 14px;">
            📌 <b>Substation Collection Efficiency Analysis:</b> Analyze revenue collection performance across substations at Zone, Circle, and Division levels.
            Identify collection efficiency patterns and prioritize actions for revenue enhancement.
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # ── COLLECTION EFFICIENCY SLAB DEFINITIONS ─────────────────────────────────
        ce_slabs = [
            {"name": "Excellent (≥95%)", "min": 95, "max": float('inf'), "color": "#22c55e", "icon": "✅"},
            {"name": "Good (85-95%)", "min": 85, "max": 95, "color": "#84cc16", "icon": "🟢"},
            {"name": "Moderate (70-85%)", "min": 70, "max": 85, "color": "#eab308", "icon": "⚠️"},
            {"name": "Poor (50-70%)", "min": 50, "max": 70, "color": "#f97316", "icon": "🔴"},
            {"name": "Critical (<50%)", "min": -float('inf'), "max": 50, "color": "#ef4444", "icon": "💀"}
        ]
        
        # Function to classify Collection Efficiency into slab
        def get_ce_slab(ce_value):
            if pd.isna(ce_value):
                return "Poor (50-70%)"
            try:
                value = float(ce_value)
            except (ValueError, TypeError):
                return "Poor (50-70%)"
            for slab in ce_slabs:
                if slab["min"] <= value < slab["max"]:
                    return slab["name"]
            return "Excellent (≥95%)"
        
        # Create collection efficiency slab column
        if 'collection_efficiency_pct' in df.columns:
            df['ce_slab'] = df['collection_efficiency_pct'].apply(get_ce_slab)
            total_substations = len(df)
            
            # # ── OVERALL STATISTICS CARDS ─────────────────────────────────────────────
            # st.markdown("### 📊 Overall Collection Efficiency Statistics")
            
            # col1, col2, col3, col4 = st.columns(4)
            
            # with col1:
            #     st.metric("🏭 Total Substations", f"{total_substations:,}")
            
            # with col2:
            #     avg_ce = df['collection_efficiency_pct'].mean()
            #     st.metric("📊 Avg Collection Efficiency", f"{avg_ce:.2f}%")
            
            # with col3:
            #     min_ce = df['collection_efficiency_pct'].min()
            #     st.metric("📉 Lowest Collection", f"{min_ce:.2f}%")
            
            # with col4:
            #     max_ce = df['collection_efficiency_pct'].max()
            #     st.metric("📈 Highest Collection", f"{max_ce:.2f}%")
            
            # st.markdown("---")
            
            # ── SLAB DISTRIBUTION CARDS ─────────────────────────────────────────────
            st.markdown("### 📊 Substation Distribution by Collection Efficiency Slab")
            
            # Calculate slab counts
            slab_counts = df['ce_slab'].value_counts()
            for slab in ce_slabs:
                if slab["name"] not in slab_counts.index:
                    slab_counts[slab["name"]] = 0
            
            # Display as color-coded cards
            slab_cols = st.columns(len(ce_slabs))
            for idx, slab in enumerate(ce_slabs):
                if idx < len(slab_cols):
                    with slab_cols[idx]:
                        count = slab_counts.get(slab["name"], 0)
                        percentage = (count / total_substations * 100) if total_substations > 0 else 0
                        st.markdown(f"""
                        <div style="background:{slab['color']}15; border:3px solid {slab['color']}; border-radius:16px; padding:16px 8px; text-align:center;">
                            <div style="font-size:36px; font-weight:900; color:{slab['color']};">{count}</div>
                            <div style="font-size:11px; color:#64748b; font-weight:700;">{slab['name']}</div>
                            <div style="font-size:13px; font-weight:800; color:{slab['color']};">{slab['icon']}</div>
                            <div style="font-size:10px; color:#94a3b8;">{percentage:.1f}% of total</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Charts for slab distribution
            st.markdown("---")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                # Bar chart
                slab_df = pd.DataFrame({
                    'Slab': [s["name"] for s in ce_slabs],
                    'Count': [slab_counts.get(s["name"], 0) for s in ce_slabs],
                    'Color': [s["color"] for s in ce_slabs]
                })
                
                fig_bar = px.bar(
                    slab_df, x='Slab', y='Count',
                    color='Slab', color_discrete_sequence=[s["color"] for s in ce_slabs],
                    text='Count', title='Substation Count by Collection Efficiency Slab'
                )
                fig_bar.update_traces(textposition='outside', textfont=dict(size=12, weight='bold'))
                fig_bar.update_layout(**dark_layout(height=400, showlegend=False))
                st.plotly_chart(fig_bar, use_container_width=True, key="ss_ce_slab_bar", config=PLOTLY_CONFIG)
            
            with chart_col2:
                # Pie chart
                fig_pie = px.pie(
                    slab_df, values='Count', names='Slab',
                    color='Slab', color_discrete_sequence=[s["color"] for s in ce_slabs],
                    hole=0.4, title='Percentage Distribution by Collection Efficiency Slab'
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(**dark_layout(height=400))
                st.plotly_chart(fig_pie, use_container_width=True, key="ss_ce_slab_pie", config=PLOTLY_CONFIG)
            
            st.markdown("---")
            
            # ── ZONE-WISE COLLECTION EFFICIENCY SLAB ANALYSIS ────────────────────────
            st.markdown("### 🗺️ Zone-wise Collection Efficiency Distribution")
            
            if 'zone' in df.columns:
                # Create zone-wise slab summary
                zone_slab = pd.crosstab(df['zone'], df['ce_slab'], margins=True, margins_name='Total')
                zone_slab = zone_slab.drop('Total', axis=0) if 'Total' in zone_slab.index else zone_slab
                
                # Add total substations per zone
                zone_totals = df.groupby('zone').size().reset_index(name='Total Substations')
                zone_avg_ce = df.groupby('zone')['collection_efficiency_pct'].mean().round(2).reset_index(name='Avg Collection %')
                
                # Merge
                zone_summary = zone_totals.merge(zone_avg_ce, on='zone')
                
                # Add slab counts
                for slab in ce_slabs:
                    slab_name = slab["name"]
                    if slab_name in zone_slab.columns:
                        zone_summary = zone_summary.merge(
                            zone_slab[[slab_name]].reset_index().rename(columns={slab_name: f'{slab_name}_count'}),
                            left_on='zone', right_on='zone', how='left'
                        )
                        zone_summary[f'{slab_name}_count'] = zone_summary[f'{slab_name}_count'].fillna(0).astype(int)
                        zone_summary[f'{slab_name}_pct'] = (zone_summary[f'{slab_name}_count'] / zone_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'Total Substations', 'Avg Collection %']
                for slab in ce_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                zone_summary = zone_summary[[c for c in display_cols if c in zone_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'Total Substations': 'Total Substations', 'Avg Collection %': 'Avg Collection %'}
                for slab in ce_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                zone_summary = zone_summary.rename(columns=rename_dict)
                
                # Sort by Total Substations
                zone_summary = zone_summary.sort_values('Total Substations', ascending=False)
                
                # Display
                st.dataframe(
                    zone_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Collection %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in ce_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in ce_slabs}
                    })
                    .background_gradient(subset=['Avg Collection %'], cmap='RdYlGn', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_zone = zone_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Zone-wise Collection Efficiency Slab Summary (CSV)",
                    data=csv_zone,
                    file_name=f"DVVNL_Substation_Zone_CE_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── CIRCLE-WISE COLLECTION EFFICIENCY SLAB ANALYSIS (TOP 20) ──────────────
            st.markdown("### 🏙️ Circle-wise Collection Efficiency Distribution (Top 20 by Substation Count)")
            
            if 'circle' in df.columns and 'zone' in df.columns:
                # Create circle-wise summary
                circle_totals = df.groupby(['zone', 'circle']).size().reset_index(name='Total Substations')
                circle_avg_ce = df.groupby(['zone', 'circle'])['collection_efficiency_pct'].mean().round(2).reset_index(name='Avg Collection %')
                
                circle_summary = circle_totals.merge(circle_avg_ce, on=['zone', 'circle'])
                
                # Add slab counts
                for slab in ce_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['ce_slab'] == slab_name].groupby(['zone', 'circle']).size().reset_index(name=f'{slab_name}_count')
                    circle_summary = circle_summary.merge(slab_count, on=['zone', 'circle'], how='left')
                    circle_summary[f'{slab_name}_count'] = circle_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    circle_summary[f'{slab_name}_pct'] = (circle_summary[f'{slab_name}_count'] / circle_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'Total Substations', 'Avg Collection %']
                for slab in ce_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                circle_summary = circle_summary[[c for c in display_cols if c in circle_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'Total Substations': 'Total Substations', 'Avg Collection %': 'Avg Collection %'}
                for slab in ce_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                circle_summary = circle_summary.rename(columns=rename_dict)
                
                # Sort and show top 20
                circle_summary = circle_summary.sort_values('Total Substations', ascending=False).head(20)
                
                st.dataframe(
                    circle_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Collection %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in ce_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in ce_slabs}
                    })
                    .background_gradient(subset=['Avg Collection %'], cmap='RdYlGn', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 20 circles by substation count. Total circles: {circle_summary['Circle'].nunique() if not circle_summary.empty else 0}")
                
                # Download button
                csv_circle = circle_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Circle-wise Collection Efficiency Slab Summary (CSV)",
                    data=csv_circle,
                    file_name=f"DVVNL_Substation_Circle_CE_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DIVISION-WISE COLLECTION EFFICIENCY SLAB ANALYSIS (TOP 30) ────────────
            if 'division' in df.columns:
                st.markdown("### 🏢 Division-wise Collection Efficiency Distribution (Top 30 by Substation Count)")
                
                # Create division-wise summary
                div_totals = df.groupby(['zone', 'circle', 'division']).size().reset_index(name='Total Substations')
                div_avg_ce = df.groupby(['zone', 'circle', 'division'])['collection_efficiency_pct'].mean().round(2).reset_index(name='Avg Collection %')
                
                div_summary = div_totals.merge(div_avg_ce, on=['zone', 'circle', 'division'])
                
                # Add slab counts
                for slab in ce_slabs:
                    slab_name = slab["name"]
                    slab_count = df[df['ce_slab'] == slab_name].groupby(['zone', 'circle', 'division']).size().reset_index(name=f'{slab_name}_count')
                    div_summary = div_summary.merge(slab_count, on=['zone', 'circle', 'division'], how='left')
                    div_summary[f'{slab_name}_count'] = div_summary[f'{slab_name}_count'].fillna(0).astype(int)
                    div_summary[f'{slab_name}_pct'] = (div_summary[f'{slab_name}_count'] / div_summary['Total Substations'] * 100).round(1)
                
                # Prepare display columns
                display_cols = ['zone', 'circle', 'division', 'Total Substations', 'Avg Collection %']
                for slab in ce_slabs:
                    display_cols.append(f'{slab["name"]}_count')
                    display_cols.append(f'{slab["name"]}_pct')
                
                div_summary = div_summary[[c for c in display_cols if c in div_summary.columns]]
                
                # Rename columns
                rename_dict = {'zone': 'Zone', 'circle': 'Circle', 'division': 'Division', 
                               'Total Substations': 'Total Substations', 'Avg Collection %': 'Avg Collection %'}
                for slab in ce_slabs:
                    rename_dict[f'{slab["name"]}_count'] = slab["name"]
                    rename_dict[f'{slab["name"]}_pct'] = f'{slab["name"]} %'
                
                div_summary = div_summary.rename(columns=rename_dict)
                
                # Sort and show top 30
                div_summary = div_summary.sort_values('Total Substations', ascending=False).head(30)
                
                st.dataframe(
                    div_summary.style
                    .format({
                        'Total Substations': '{:,.0f}',
                        'Avg Collection %': '{:.2f}%',
                        **{slab["name"]: '{:,.0f}' for slab in ce_slabs},
                        **{f'{slab["name"]} %': '{:.1f}%' for slab in ce_slabs}
                    })
                    .background_gradient(subset=['Avg Collection %'], cmap='RdYlGn', vmin=0, vmax=100)
                    .set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption(f"Showing top 30 divisions by substation count. Total divisions: {div_summary['Division'].nunique() if not div_summary.empty else 0}")
                
                # Download button
                csv_division = div_summary.to_csv(index=False).encode()
                st.download_button(
                    label="📥 Download Division-wise Collection Efficiency Slab Summary (CSV)",
                    data=csv_division,
                    file_name=f"DVVNL_Substation_Division_CE_Slab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # ── DETAILED SUBSTATION LIST BY COLLECTION EFFICIENCY SLAB ───────────────
            st.markdown("### 🔍 Detailed Substation List by Collection Efficiency Slab")
            
            # Slab selector
            selected_slab = st.selectbox(
                "Select Collection Efficiency Slab to View Substations:",
                ["All Substations"] + [s["name"] for s in ce_slabs],
                key="ss_ce_slab_select"
            )
            
            # Filter substations
            if selected_slab == "All Substations":
                slab_filtered_df = df.copy()
            else:
                slab_filtered_df = df[df['ce_slab'] == selected_slab].copy()
            
            if not slab_filtered_df.empty:
                st.markdown(f"**Showing {len(slab_filtered_df)} substations**")
                
                # Select columns for display
                detail_cols = ['substation', 'zone', 'circle', 'division']
                if 'feeder_count' in slab_filtered_df.columns:
                    detail_cols.append('feeder_count')
                detail_cols.extend(['input_energy_kwh', 'collection_efficiency_pct', 'atc_loss_pct', 'line_loss_pct'])
                
                available_detail = [c for c in detail_cols if c in slab_filtered_df.columns]
                detail_sub_df = slab_filtered_df[available_detail].copy()
                
                # Rename columns
                detail_sub_df = detail_sub_df.rename(columns={
                    'substation': 'Substation',
                    'zone': 'Zone',
                    'circle': 'Circle',
                    'division': 'Division',
                    'feeder_count': 'Feeders',
                    'input_energy_kwh': 'Input Energy (MU)',
                    'collection_efficiency_pct': 'Collection %',
                    'atc_loss_pct': 'AT&C %',
                    'line_loss_pct': 'Line Loss %'
                })
                
                # Format Input Energy to MU
                if 'Input Energy (MU)' in detail_sub_df.columns:
                    detail_sub_df['Input Energy (MU)'] = (detail_sub_df['Input Energy (MU)'] / 1e6).round(2)
                
                # Sort by Collection % descending (best first)
                if 'Collection %' in detail_sub_df.columns:
                    detail_sub_df = detail_sub_df.sort_values('Collection %', ascending=False)
                
                # Color coding function for Collection Efficiency
                def highlight_ce(val):
                    if isinstance(val, (int, float)):
                        if val >= 95:
                            return 'color: #22c55e; font-weight: bold'
                        elif val >= 85:
                            return 'color: #84cc16; font-weight: bold'
                        elif val >= 70:
                            return 'color: #eab308; font-weight: bold'
                        elif val >= 50:
                            return 'color: #f97316; font-weight: bold'
                        else:
                            return 'color: #ef4444; font-weight: bold'
                    return ''
                
                # Apply styling
                styled_detail_sub = detail_sub_df.style.map(highlight_ce, subset=['Collection %'] if 'Collection %' in detail_sub_df.columns else [])
                
                st.dataframe(
                    styled_detail_sub.set_properties(**{'font-weight': 'bold'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_detail_sub = detail_sub_df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 Download {selected_slab} Substation List (CSV)",
                    data=csv_detail_sub,
                    file_name=f"DVVNL_Substations_CE_{selected_slab.replace(' ', '_').replace('%', 'pct')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info(f"No substations found in the '{selected_slab}' slab")
            
            st.markdown("---")
            
            # ── KEY INSIGHTS ───────────────────────────────────────────────────────
            st.markdown("### 📈 Key Insights")
            
            insight_col1, insight_col2, insight_col3 = st.columns(3)
            
            with insight_col1:
                # Best performing zone (highest collection efficiency)
                if 'zone' in df.columns:
                    zone_avg_ce = df.groupby('zone')['collection_efficiency_pct'].mean()
                    if not zone_avg_ce.empty:
                        best_zone = zone_avg_ce.idxmax()
                        best_zone_ce = zone_avg_ce.max()
                        st.success(f"🏆 **Best Zone (Highest Collection):** {best_zone}\n\nAvg Collection: {best_zone_ce:.2f}%")
            
            with insight_col2:
                # Worst performing zone (lowest collection efficiency)
                if 'zone' in df.columns:
                    worst_zone = zone_avg_ce.idxmin() if not zone_avg_ce.empty else None
                    worst_zone_ce = zone_avg_ce.min() if not zone_avg_ce.empty else 0
                    if worst_zone:
                        st.warning(f"⚠️ **Needs Improvement Zone:** {worst_zone}\n\nAvg Collection: {worst_zone_ce:.2f}%")
            
            with insight_col3:
                # Most common slab
                most_common = slab_counts.idxmax() if not slab_counts.empty else "Unknown"
                most_common_count = slab_counts.max() if not slab_counts.empty else 0
                st.info(f"📊 **Most Common Slab:** {most_common}\n\n{most_common_count:,} Substations ({most_common_count/total_substations*100:.1f}%)")
            
            st.markdown("---")
            
            # # ── LOW COLLECTION EFFICIENCY SUBSTATIONS ALERT ─────────────────────────
            # if 'collection_efficiency_pct' in df.columns:
            #     low_ce = df[df['collection_efficiency_pct'] < 70]
            #     if not low_ce.empty:
            #         with st.expander(f"⚠️ {len(low_ce)} Substations with Low Collection Efficiency (<70%)", expanded=False):
            #             for _, row in low_ce.iterrows():
            #                 ca, cb, cc, cd = st.columns([3, 1, 1, 1])
            #                 with ca:
            #                     st.markdown(f"**{row.get('substation', '?')}** - {row.get('zone', '')} / {row.get('circle', '')}")
            #                 with cb:
            #                     st.markdown(f"<span style='color:#ef4444;font-weight:800'>Collection: {row.get('collection_efficiency_pct', 0):.1f}%</span>", unsafe_allow_html=True)
            #                 with cc:
            #                     st.markdown(f"<span style='color:#f97316'>Revenue: {fmt_lakh(row.get('revenue_realized', 0))}</span>", unsafe_allow_html=True)
            #                 with cd:
            #                     st.markdown(f"<span style='color:#eab308'>Outstanding: {fmt_lakh(row.get('outstanding_amount', 0))}</span>", unsafe_allow_html=True)
            
            # st.markdown("---")
            # st.markdown("### 💡 Understanding Collection Efficiency for Substations")
            # st.info("""
            # **Collection Efficiency** measures the effectiveness of revenue collection from consumers under each substation.
            
            # **Formula:** Collection Efficiency = (Revenue Collected / Total Assessment) × 100
            
            # **Slab Classifications:**
            # - ✅ **Excellent (≥95%)** - Outstanding collection performance
            # - 🟢 **Good (85-95%)** - Acceptable collection rate
            # - ⚠️ **Moderate (70-85%)** - Needs improvement
            # - 🔴 **Poor (50-70%)** - Significant collection issues
            # - 💀 **Critical (<50%)** - Severe collection problems
            
            # **Action Items:**
            # - Priority: Focus on Critical and Poor slabs for immediate recovery
            # - Investigate: Billing discrepancies, payment defaults, disputes
            # - Implement: Regular follow-up, digital payment options, disconnection drives
            # - Replicate: Best practices from Excellent slab substations
            
            # **Note:** 
            # - Values >100% (over-collection) are included in Excellent category
            # - Negative values (refunds/credits) are included in Critical category
            # """)
        
        else:
            st.warning("⚠️ Collection Efficiency data (collection_efficiency_pct column) not available in the dataset.")





    # ══ STAB 5: RANKINGS ══════════════════════════════════════════════════════
    # with stabs[4]:
    #     n_top = st.slider("Top/Bottom N", 3, 30, 10, key="ss_n_top")
    #     col1,col2 = st.columns(2)
    #     with col1:
    #         top = df.nsmallest(n_top,"atc_loss_pct") if "atc_loss_pct" in df.columns else df.head(n_top)
    #         st.markdown(f"**🏆 Best {n_top} — Lowest AT&C - {current_hierarchy}**")
    #         fig = px.bar(top, y="substation", x="atc_loss_pct", orientation="h",
    #                      color="atc_loss_pct", color_continuous_scale=[[0,"#22c55e"],[1,"#eab308"]],
    #                      hover_data=["zone","feeder_count","billing_efficiency_pct"])
    #         fig.update_layout(**dark_layout(showlegend=False))
    #         st.plotly_chart(fig, use_container_width=True, key="ss_rk_best", config=PLOTLY_CONFIG)
    #     with col2:
    #         bot = df.nlargest(n_top,"atc_loss_pct") if "atc_loss_pct" in df.columns else df.tail(n_top)
    #         st.markdown(f"**🔴 Worst {n_top} — Highest AT&C - {current_hierarchy}**")
    #         fig2 = px.bar(bot, y="substation", x="atc_loss_pct", orientation="h",
    #                       color="atc_loss_pct", color_continuous_scale=[[0,"#f97316"],[1,"#ef4444"]],
    #                       hover_data=["zone","feeder_count","billing_efficiency_pct"])
    #         fig2.update_layout(**dark_layout(showlegend=False))
    #         st.plotly_chart(fig2, use_container_width=True, key="ss_rk_worst", config=PLOTLY_CONFIG)

    #     st.markdown(f"**Full KPI Ranking Table - {current_hierarchy}**")
    #     rank_cols = ["substation","zone","circle","division","feeder_count",
    #                  "consumers","billed_consumers","paid_consumers","smart_meter_consumers",
    #                  "line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct",
    #                  "input_energy_kwh","sold_energy_kwh","net_assessment_sub","revenue_realized","outstanding_amount"]
    #     avail = [c for c in rank_cols if c in df.columns]
    #     df_r = df[avail].copy()
    #     df_r.insert(0,"#",range(1,len(df_r)+1))
    #     if "atc_loss_pct" in df_r.columns:
    #         df_r["Rating"] = df_r["atc_loss_pct"].apply(rating)
    #     pf = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"] if c in df_r.columns}
    #     nf = {c:"{:,.0f}" for c in ["input_energy_kwh","sold_energy_kwh","net_assessment_sub","revenue_realized"] if c in df_r.columns}
        
    #     styler = df_r.style.format({**pf,**nf})
    #     if len(df_r) <= 500 and "atc_loss_pct" in df_r.columns:
    #         styler = styler.background_gradient(subset=["atc_loss_pct"], cmap="RdYlGn_r")
    #     st.dataframe(styler, use_container_width=True, hide_index=True)

    # ══ STAB 13: SUBSTATION RANKINGS TAB ══════════════════════════════════════════
    with stabs[4]:
        st.markdown('<div class="section-title">🏆 Substation Rankings - Best & Worst Performance Analysis</div>',
                    unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #e0e7ff; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; border-left: 4px solid #457a9f;">
            <span style="color: #0f172a; font-size: 14px;">
            📌 <b>Substation Rankings:</b> Identify best and worst performing substations by AT&C Loss, Line Loss, and Collection Efficiency.
            Customize extraction limits per zone, circle, and division for targeted performance improvement.
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # ── RANKING CONFIGURATION ──────────────────────────────────────────────────
        st.markdown("### ⚙️ Ranking Configuration")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            ranking_metric = st.selectbox(
                "📊 Select Ranking Metric",
                ["AT&C Loss %", "Line Loss %", "Collection Efficiency %"],
                key="ss_rank_metric"
            )
        
        with col2:
            ranking_type = st.selectbox(
                "📈 Ranking Type",
                ["Worst Performers (Highest Loss / Lowest Collection)", "Best Performers (Lowest Loss / Highest Collection)"],
                key="ss_rank_type"
            )
        
        with col3:
            rank_limit = st.slider(
                "🔢 Number of Substations to Show",
                min_value=5,
                max_value=50,
                value=10,
                step=5,
                key="ss_rank_limit"
            )
        
        with col4:
            hierarchy_level = st.selectbox(
                "🏗️ Hierarchy Level",
                ["Overall", "Zone-wise", "Circle-wise", "Division-wise"],
                key="ss_rank_hierarchy"
            )
        
        st.markdown("---")
        
        # Map display names to column names
        metric_mapping = {
            "AT&C Loss %": "atc_loss_pct",
            "Line Loss %": "line_loss_pct",
            "Collection Efficiency %": "collection_efficiency_pct"
        }
        
        selected_col = metric_mapping.get(ranking_metric, "atc_loss_pct")
        
        # Determine sort order
        if ranking_type == "Worst Performers (Highest Loss / Lowest Collection)":
            ascending = False if selected_col != "collection_efficiency_pct" else True
        else:
            ascending = True if selected_col != "collection_efficiency_pct" else False
        
        # ── HELPER FUNCTION FOR DISPLAY ───────────────────────────────────────────
        # ── HELPER FUNCTION FOR DISPLAY ───────────────────────────────────────────
        def display_ranking_data(df_to_display, title, file_prefix):
            if df_to_display.empty:
                st.warning("No data available")
                return
            
            st.markdown(f"### {title}")
            
            # Remove duplicate columns
            df_to_display = df_to_display.loc[:, ~df_to_display.columns.duplicated()]
            
            # Build data row by row to avoid column duplication
            output_data = []
            
            for idx, row in df_to_display.iterrows():
                row_data = {}
                
                # Add hierarchy columns
                if 'Zone' in df_to_display.columns:
                    row_data['Zone'] = row.get('Zone', '')
                if 'Circle' in df_to_display.columns:
                    row_data['Circle'] = row.get('Circle', '')
                if 'Division' in df_to_display.columns:
                    row_data['Division'] = row.get('Division', '')
                
                # Add original hierarchy if they exist and not already added
                if 'zone' in df_to_display.columns and 'Zone' not in row_data:
                    row_data['Zone'] = row.get('zone', '')
                if 'circle' in df_to_display.columns and 'Circle' not in row_data:
                    row_data['Circle'] = row.get('circle', '')
                if 'division' in df_to_display.columns and 'Division' not in row_data:
                    row_data['Division'] = row.get('division', '')
                
                # Add substation
                if 'substation' in df_to_display.columns:
                    row_data['Substation'] = row.get('substation', '')
                
                # Add feeder count
                if 'feeder_count' in df_to_display.columns:
                    fc = row.get('feeder_count', 0)
                    row_data['Feeders'] = f"{int(fc):,}" if pd.notna(fc) else "0"
                
                # Add input energy
                if 'input_energy_kwh' in df_to_display.columns:
                    ie = row.get('input_energy_kwh', 0)
                    row_data['Input (MU)'] = f"{ie/1e6:.2f}" if pd.notna(ie) else "0"
                
                # Add the ranking metric
                metric_val = row.get(selected_col, 0)
                row_data[ranking_metric] = f"{metric_val:.2f}%" if pd.notna(metric_val) else "0%"
                
                # Add other KPIs
                if 'atc_loss_pct' in df_to_display.columns:
                    atc_val = row.get('atc_loss_pct', 0)
                    row_data['AT&C %'] = f"{atc_val:.2f}%" if pd.notna(atc_val) else "0%"
                
                if 'line_loss_pct' in df_to_display.columns:
                    ll_val = row.get('line_loss_pct', 0)
                    row_data['Line Loss %'] = f"{ll_val:.2f}%" if pd.notna(ll_val) else "0%"
                
                if 'collection_efficiency_pct' in df_to_display.columns:
                    ce_val = row.get('collection_efficiency_pct', 0)
                    row_data['Collection %'] = f"{ce_val:.2f}%" if pd.notna(ce_val) else "0%"
                
                output_data.append(row_data)
            
            # Create final dataframe
            display_df = pd.DataFrame(output_data)
            
            # Remove any duplicate columns
            display_df = display_df.loc[:, ~display_df.columns.duplicated()]
            
            # Display without any styling
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Download button
            csv_data = display_df.to_csv(index=False).encode()
            st.download_button(
                label=f"📥 Download {file_prefix} (CSV)",
                data=csv_data,
                file_name=f"DVVNL_Substation_{file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )   
            # ── OVERALL RANKINGS ───────────────────────────────────────────────────────
        if hierarchy_level == "Overall":
            if selected_col in df.columns:
                ranked_df = df.sort_values(selected_col, ascending=ascending).head(rank_limit).copy()
                # Remove duplicates
                ranked_df = ranked_df.loc[:, ~ranked_df.columns.duplicated()]
                display_ranking_data(ranked_df, f"Top {rank_limit} {ranking_type}", f"Overall_{ranking_type.replace(' ', '_')}")
        
        # ── ZONE-WISE RANKINGS ─────────────────────────────────────────────────────
        elif hierarchy_level == "Zone-wise" and 'zone' in df.columns:
            zones = sorted(df['zone'].dropna().unique())
            selected_zones = st.multiselect(
                "Select Zones to Analyze (or leave empty for all zones):",
                options=zones,
                default=zones[:3] if len(zones) > 3 else zones,
                key="ss_rank_zones"
            )
            
            if not selected_zones:
                selected_zones = zones
            
            zone_rankings = []
            for zone in selected_zones:
                zone_df = df[df['zone'] == zone].copy()
                if selected_col in zone_df.columns and not zone_df.empty:
                    ranked_zone = zone_df.sort_values(selected_col, ascending=ascending).head(rank_limit).copy()
                    ranked_zone['Zone'] = zone
                    # Remove duplicates before appending
                    ranked_zone = ranked_zone.loc[:, ~ranked_zone.columns.duplicated()]
                    zone_rankings.append(ranked_zone)
            
            if zone_rankings:
                combined_df = pd.concat(zone_rankings, ignore_index=True)
                # Remove any duplicate columns after concatenation
                combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]
                display_ranking_data(combined_df, f"Top {rank_limit} {ranking_type} per Zone", f"ZoneWise_{ranking_type.replace(' ', '_')}")
            else:
                st.warning("No data available for selected zones")
        
        # ── CIRCLE-WISE RANKINGS ───────────────────────────────────────────────────
        elif hierarchy_level == "Circle-wise" and 'circle' in df.columns:
            circles = sorted(df['circle'].dropna().unique())
            selected_circles = st.multiselect(
                "Select Circles to Analyze (or leave empty for all circles):",
                options=circles,
                default=circles[:3] if len(circles) > 3 else circles,
                key="ss_rank_circles"
            )
            
            if not selected_circles:
                selected_circles = circles
            
            circle_rankings = []
            for circle in selected_circles:
                circle_df = df[df['circle'] == circle].copy()
                if selected_col in circle_df.columns and not circle_df.empty:
                    ranked_circle = circle_df.sort_values(selected_col, ascending=ascending).head(rank_limit).copy()
                    ranked_circle['Circle'] = circle
                    ranked_circle = ranked_circle.loc[:, ~ranked_circle.columns.duplicated()]
                    circle_rankings.append(ranked_circle)
            
            if circle_rankings:
                combined_df = pd.concat(circle_rankings, ignore_index=True)
                combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]
                display_ranking_data(combined_df, f"Top {rank_limit} {ranking_type} per Circle", f"CircleWise_{ranking_type.replace(' ', '_')}")
            else:
                st.warning("No data available for selected circles")
        
        # ── DIVISION-WISE RANKINGS ─────────────────────────────────────────────────
        elif hierarchy_level == "Division-wise" and 'division' in df.columns:
            divisions = sorted(df['division'].dropna().unique())
            selected_divisions = st.multiselect(
                "Select Divisions to Analyze (or leave empty for all divisions):",
                options=divisions,
                default=divisions[:3] if len(divisions) > 3 else divisions,
                key="ss_rank_divisions"
            )
            
            if not selected_divisions:
                selected_divisions = divisions
            
            division_rankings = []
            for division in selected_divisions:
                division_df = df[df['division'] == division].copy()
                if selected_col in division_df.columns and not division_df.empty:
                    ranked_division = division_df.sort_values(selected_col, ascending=ascending).head(rank_limit).copy()
                    ranked_division['Division'] = division
                    ranked_division = ranked_division.loc[:, ~ranked_division.columns.duplicated()]
                    division_rankings.append(ranked_division)
            
            if division_rankings:
                combined_df = pd.concat(division_rankings, ignore_index=True)
                combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]
                display_ranking_data(combined_df, f"Top {rank_limit} {ranking_type} per Division", f"DivisionWise_{ranking_type.replace(' ', '_')}")
            else:
                st.warning("No data available for selected divisions")
        
        st.markdown("---")
        
        # # ── SUMMARY STATISTICS CARDS ──────────────────────────────────────────────
        # st.markdown("### 📊 Ranking Summary Statistics")
        
        # if selected_col in df.columns:
        #     stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            
        #     with stat_col1:
        #         total_substations = len(df)
        #         st.metric("🏭 Total Substations", f"{total_substations:,}")
            
        #     with stat_col2:
        #         avg_value = df[selected_col].mean()
        #         st.metric(f"📊 Avg {ranking_metric}", f"{avg_value:.2f}%")
            
        #     with stat_col3:
        #         if ranking_type == "Worst Performers (Highest Loss / Lowest Collection)":
        #             worst_value = df[selected_col].max()
        #             st.metric(f"📈 Worst {ranking_metric}", f"{worst_value:.2f}%")
        #         else:
        #             best_value = df[selected_col].min()
        #             st.metric(f"🏆 Best {ranking_metric}", f"{best_value:.2f}%")
            
        #     with stat_col4:
        #         std_value = df[selected_col].std()
        #         st.metric("📊 Std Deviation", f"{std_value:.2f}%")
        
        # st.markdown("---")
        # ── CUSTOM EXTRACTION SECTION ─────────────────────────────────────────────
        st.markdown("### 🔧 Custom Extraction Tool")
        st.markdown("Extract specific number of best/worst substations from selected zones, circles, or divisions")
        
        extract_col1, extract_col2, extract_col3, extract_col4 = st.columns(4)
        
        with extract_col1:
            extract_level = st.selectbox(
                "Select Hierarchy Level",
                ["Zone", "Circle", "Division"],
                key="ss_extract_level"
            )
        
        with extract_col2:
            extract_limit = st.number_input(
                "Number of Substations per Unit",
                min_value=1,
                max_value=20,
                value=5,
                step=1,
                key="ss_extract_limit"
            )
        
        with extract_col3:
            extract_metric = st.selectbox(
                "Metric for Extraction",
                ["AT&C Loss %", "Line Loss %", "Collection Efficiency %"],
                key="ss_extract_metric"
            )
        
        with extract_col4:
            extract_type = st.selectbox(
                "Extract Type",
                ["Worst Performers", "Best Performers"],
                key="ss_extract_type"
            )
        
        extract_col_name = metric_mapping.get(extract_metric, "atc_loss_pct")
        extract_ascending = False if extract_type == "Worst Performers" else True
        if extract_metric == "Collection Efficiency %":
            extract_ascending = not extract_ascending
        
        if st.button("🔍 Generate Custom Extraction Report", use_container_width=True, key="ss_extract_btn"):
            st.markdown("---")
            st.markdown(f"### 📋 Custom Extraction Results - Top {extract_limit} {extract_type} per {extract_level}")
            
            results = []
            
            if extract_level == "Zone" and 'zone' in df.columns:
                units = sorted(df['zone'].dropna().unique())
                for unit in units:
                    unit_df = df[df['zone'] == unit].copy()
                    if extract_col_name in unit_df.columns and not unit_df.empty:
                        ranked = unit_df.sort_values(extract_col_name, ascending=extract_ascending).head(extract_limit).copy()
                        # Add the hierarchy column with a unique name
                        ranked[f'Selected_{extract_level}'] = unit
                        results.append(ranked)
            
            elif extract_level == "Circle" and 'circle' in df.columns:
                units = sorted(df['circle'].dropna().unique())
                for unit in units:
                    unit_df = df[df['circle'] == unit].copy()
                    if extract_col_name in unit_df.columns and not unit_df.empty:
                        ranked = unit_df.sort_values(extract_col_name, ascending=extract_ascending).head(extract_limit).copy()
                        ranked[f'Selected_{extract_level}'] = unit
                        results.append(ranked)
            
            elif extract_level == "Division" and 'division' in df.columns:
                units = sorted(df['division'].dropna().unique())
                for unit in units:
                    unit_df = df[df['division'] == unit].copy()
                    if extract_col_name in unit_df.columns and not unit_df.empty:
                        ranked = unit_df.sort_values(extract_col_name, ascending=extract_ascending).head(extract_limit).copy()
                        ranked[f'Selected_{extract_level}'] = unit
                        results.append(ranked)
            
            if results:
                # Concatenate all results
                result_df = pd.concat(results, ignore_index=True)
                
                # Remove any duplicate columns
                result_df = result_df.loc[:, ~result_df.columns.duplicated()]
                
                # Define the columns we want to display (in order)
                output_data = []
                
                # Process each row to avoid column duplication issues
                for idx, row in result_df.iterrows():
                    row_data = {}
                    
                    # Add the selected hierarchy
                    row_data[f'{extract_level}'] = row.get(f'Selected_{extract_level}', '')
                    
                    # Add substation
                    row_data['Substation'] = row.get('substation', '')
                    
                    # Add original hierarchy info
                    if 'zone' in result_df.columns and extract_level != 'Zone':
                        row_data['Zone'] = row.get('zone', '')
                    if 'circle' in result_df.columns and extract_level != 'Circle':
                        row_data['Circle'] = row.get('circle', '')
                    if 'division' in result_df.columns and extract_level != 'Division':
                        row_data['Division'] = row.get('division', '')
                    
                    # Add feeder count
                    if 'feeder_count' in result_df.columns:
                        fc = row.get('feeder_count', 0)
                        row_data['Feeders'] = f"{int(fc):,}" if pd.notna(fc) else "0"
                    
                    # Add input energy
                    if 'input_energy_kwh' in result_df.columns:
                        ie = row.get('input_energy_kwh', 0)
                        row_data['Input (MU)'] = f"{ie/1e6:.2f}" if pd.notna(ie) else "0"
                    
                    # Add the selected metric
                    metric_val = row.get(extract_col_name, 0)
                    row_data[extract_metric] = f"{metric_val:.2f}%" if pd.notna(metric_val) else "0%"
                    
                    # Add other KPIs
                    if 'atc_loss_pct' in result_df.columns:
                        atc_val = row.get('atc_loss_pct', 0)
                        row_data['AT&C %'] = f"{atc_val:.2f}%" if pd.notna(atc_val) else "0%"
                    
                    if 'line_loss_pct' in result_df.columns:
                        ll_val = row.get('line_loss_pct', 0)
                        row_data['Line Loss %'] = f"{ll_val:.2f}%" if pd.notna(ll_val) else "0%"
                    
                    if 'collection_efficiency_pct' in result_df.columns:
                        ce_val = row.get('collection_efficiency_pct', 0)
                        row_data['Collection %'] = f"{ce_val:.2f}%" if pd.notna(ce_val) else "0%"
                    
                    output_data.append(row_data)
                
                # Create final dataframe from the list of dictionaries
                final_df = pd.DataFrame(output_data)
                
                # Ensure no duplicate column names
                final_df = final_df.loc[:, ~final_df.columns.duplicated()]
                
                # Display the dataframe
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button for the extraction results
                csv_extract = final_df.to_csv(index=False).encode()
                st.download_button(
                    label=f"📥 Download Custom Extraction Report (CSV)",
                    data=csv_extract,
                    file_name=f"DVVNL_Substation_Custom_Extract_{extract_level}_{extract_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No data available for the selected criteria")        
        st.markdown("---")
        st.markdown("### 💡 How to Use This Tab")
        st.info("""
        **Ranking Configuration:**
        - **Select Metric:** Choose between AT&C Loss, Line Loss, or Collection Efficiency
        - **Ranking Type:** Worst performers (highest loss/lowest collection) or Best performers (lowest loss/highest collection)
        - **Number to Show:** Set how many substations to display (5-50)
        - **Hierarchy Level:** View rankings Overall, Zone-wise, Circle-wise, or Division-wise
        
        **Custom Extraction Tool:**
        - Extract specific number of best/worst substations per selected hierarchy level
        - Useful for creating targeted action plans for each zone/circle/division
        - Results can be downloaded as CSV for further analysis
        
        **Use Cases:**
        - Identify top priority substations for infrastructure investment
        - Compare performance across different zones and circles
        - Create focused improvement plans for underperforming areas
        - Recognize and replicate best practices from top performers
        """)



    # ══ STAB 6: ZONE VIEW ════════════════════════════════════════════════════
    with stabs[5]:
        st.markdown(f'<div class="section-title">Coming Soon</div>',
                    unsafe_allow_html=True)
        # col1,col2 = st.columns(2)
        # with col1:
        #     if not zone_df.empty:
        #         st.markdown(f"**Radar: Multi-KPI {current_hierarchy} Comparison**")
        #         st.plotly_chart(chart_zone_radar(zone_df), use_container_width=True, key="ss_zn_radar", config=PLOTLY_CONFIG)
        # with col2:
        #     if not zone_df.empty and "atc_loss_pct" in zone_df.columns:
        #         st.markdown(f"**{current_hierarchy} AT&C Loss**")
        #         z_s = zone_df.sort_values("atc_loss_pct",ascending=True)
        #         fig = go.Figure(go.Bar(y=z_s["zone"], x=z_s["atc_loss_pct"], orientation="h",
        #                                marker_color=[atc_color(v) for v in z_s["atc_loss_pct"]],
        #                                text=z_s["atc_loss_pct"].apply(lambda x:f"{x:.1f}%"), textposition="outside"))
        #         fig.update_layout(**dark_layout())
        #         st.plotly_chart(fig, use_container_width=True, key="ss_zn_atc", config=PLOTLY_CONFIG)

        # if not circle_df.empty:
        #     st.markdown(f"**Circle-wise KPI - {current_hierarchy}**")
        #     circ_cols = [c for c in ["circle","substation_count","atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in circle_df.columns]
        #     pct_c = {c:"{:.1f}%" for c in ["atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in circle_df.columns}
        #     st.dataframe(circle_df[circ_cols].sort_values("atc_loss_pct",ascending=False).style
        #                  .format(pct_c).background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in circle_df.columns else [], cmap="RdYlGn_r"),
        #                  use_container_width=True, hide_index=True)

        # if not division_df.empty:
        #     st.markdown(f"**Division-wise KPI Heatmap - {current_hierarchy}**")
        #     div_cols = [c for c in ["division","substation_count","atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in division_df.columns]
        #     pct_d = {c:"{:.1f}%" for c in ["atc_loss_pct","billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"] if c in division_df.columns}
        #     st.dataframe(division_df[div_cols].sort_values("atc_loss_pct",ascending=False).style
        #                  .format(pct_d).background_gradient(subset=["atc_loss_pct"] if "atc_loss_pct" in division_df.columns else [], cmap="RdYlGn_r"),
        #                  use_container_width=True, hide_index=True)

    # ══ STAB 7: SLAB ANALYSIS ═════════════════════════════════════════════════
    with stabs[6]:
        st.markdown(f'<div class="section-title">📐 Slab-wise Abstract — {current_hierarchy}</div>',
                    unsafe_allow_html=True)
        
        ATC_SLABS = [
            {"label":"Below 15%","min":-999,"max":15,  "color":"#22c55e","bg":"#f0fdf4","text":"✅ GOOD"},
            {"label":"15–30%",   "min":15,  "max":30,  "color":"#84cc16","bg":"#f7fee7","text":"🟢 OK"},
            {"label":"30–50%",   "min":30,  "max":50,  "color":"#eab308","bg":"#fefce8","text":"⚠️ HIGH"},
            {"label":"50–75%",   "min":50,  "max":75,  "color":"#f97316","bg":"#fff7ed","text":"🟠 CRITICAL"},
            {"label":"Above 75%","min":75,  "max":9999,"color":"#ef4444","bg":"#fef2f2","text":"🔴 SEVERE"},
        ]
        BE_SLABS = [
            {"label":"Above 90%","min":90,  "max":9999,"color":"#22c55e","bg":"#f0fdf4","text":"✅ EXCELLENT"},
            {"label":"75–90%",   "min":75,  "max":90,  "color":"#84cc16","bg":"#f7fee7","text":"🟢 GOOD"},
            {"label":"60–75%",   "min":60,  "max":75,  "color":"#eab308","bg":"#fefce8","text":"⚠️ AVERAGE"},
            {"label":"40–60%",   "min":40,  "max":60,  "color":"#f97316","bg":"#fff7ed","text":"🟠 POOR"},
            {"label":"Below 40%","min":-999,"max":40,  "color":"#ef4444","bg":"#fef2f2","text":"🔴 CRITICAL"},
        ]
        CE_SLABS = [
            {"label":"Above 95%","min":95,  "max":9999,"color":"#22c55e","bg":"#f0fdf4","text":"✅ EXCELLENT"},
            {"label":"85–95%",   "min":85,  "max":95,  "color":"#84cc16","bg":"#f7fee7","text":"🟢 GOOD"},
            {"label":"70–85%",   "min":70,  "max":85,  "color":"#eab308","bg":"#fefce8","text":"⚠️ AVERAGE"},
            {"label":"50–70%",   "min":50,  "max":70,  "color":"#f97316","bg":"#fff7ed","text":"🟠 POOR"},
            {"label":"Below 50%","min":-999,"max":50,  "color":"#ef4444","bg":"#fef2f2","text":"🔴 CRITICAL"},
        ]

        slab_type = st.radio("Select KPI for Slab Analysis:",
                             ["🔴 AT&C Loss %","⚡ Billing Eff %","💰 Collection Eff %"],
                             horizontal=True, key="ss_slab_radio")
        if slab_type=="🔴 AT&C Loss %":       slabs_def,kpi_col,kpi_lbl = ATC_SLABS,"atc_loss_pct","AT&C Loss %"
        elif slab_type=="⚡ Billing Eff %":      slabs_def,kpi_col,kpi_lbl = BE_SLABS, "billing_efficiency_pct","Billing Eff %"
        else:                                    slabs_def,kpi_col,kpi_lbl = CE_SLABS, "collection_efficiency_pct","Collection Eff %"

        def _slab_rows(df_in, col, slabs):
            rows = []
            for s in slabs:
                mask = (df_in[col]>=s["min"]) & (df_in[col]<s["max"])
                g    = df_in[mask]
                inp  = g["input_energy_kwh"].sum() if "input_energy_kwh" in g.columns else 0
                sold = g["sold_energy_kwh"].sum() if "sold_energy_kwh" in g.columns else 0
                ass  = g["net_assessment_sub"].sum() if "net_assessment_sub" in g.columns else 0
                rev  = g["revenue_realized"].sum() if "revenue_realized" in g.columns else 0
                be   = sold/inp if inp>0 else 0
                ce   = rev/ass  if ass>0 else 0
                rows.append({**s,"count":len(g),"avg_kpi":round(g[col].mean(),1) if len(g) else 0,
                             "input":round(inp,2),"sold":round(sold,2),
                             "assessment":round(ass,2),"revenue":round(rev,2),
                             "atc":round((1-be*ce)*100,2),"be":round(be*100,2),"ce":round(ce*100,2),
                             "ll":round((inp-sold)/inp*100,2) if inp>0 else 0,"_df":g})
            return rows

        slab_rows = _slab_rows(df, kpi_col, slabs_def)

        slab_markup_cols = st.columns(len(slabs_def))
        for i,(col_w,s) in enumerate(zip(slab_markup_cols, slab_rows)):
            pct = round(s["count"]/total_ss*100,1) if total_ss>0 else 0
            with col_w:
                st.markdown(f"""
                <div style="background:{s['bg']};border:3px solid {s['color']};border-radius:14px;
                            padding:14px 8px;text-align:center;box-shadow:0 4px 12px {s['color']}33;">
                    <div style="font-size:32px;font-weight:900;color:{s['color']};font-family:'JetBrains Mono',monospace">{s['count']}</div>
                    <div style="font-size:10px;color:#64748b;font-weight:700">{s['label']}</div>
                    <div style="font-size:12px;font-weight:800;color:{s['color']};margin-top:4px">{s['text']}</div>
                    <div style="font-size:10px;color:#94a3b8;margin-top:4px">{pct}% | Avg {s['avg_kpi']}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        sel_opts = [f"{s['text']}  {s['label']}  ({s['count']} substations)" for s in slab_rows]
        sel_slab = st.selectbox("🔍 Click a slab to view substation details:", ["— Select a slab —"]+sel_opts, key="ss_slab_sel")
        if sel_slab != "— Select a slab —":
            idx  = sel_opts.index(sel_slab)
            s    = slab_rows[idx]
            sdf  = s["_df"].copy()
            st.markdown(f"""
            <div style="background:{s['bg']};border:2px solid {s['color']};border-radius:12px;padding:12px 16px;margin:8px 0">
                <span style="font-size:18px;font-weight:900;color:{s['color']}">{s['text']} {s['label']}</span>
                <span style="font-size:12px;color:#64748b;margin-left:10px">{s['count']} substations | Avg {kpi_lbl}: {s['avg_kpi']}%</span>
                <div style="margin-top:8px;display:flex;gap:16px;flex-wrap:wrap">
                    <span style="font-size:12px">AT&C: <b>{s['atc']:.1f}%</b></span>
                    <span style="font-size:12px">BE: <b>{s['be']:.1f}%</b></span>
                    <span style="font-size:12px">CE: <b>{s['ce']:.1f}%</b></span>
                    <span style="font-size:12px">LL: <b>{s['ll']:.1f}%</b></span>
                </div>
            </div>""", unsafe_allow_html=True)

            if not sdf.empty:
                sdf_plot = sdf.sort_values("atc_loss_pct", ascending=False).head(100)
                fig_s = px.bar(sdf_plot,
                               x="substation", y="atc_loss_pct", color="atc_loss_pct",
                               color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                               hover_data=["zone","feeder_count","billing_efficiency_pct","collection_efficiency_pct"])
                fig_s.update_layout(**dark_layout(xaxis_tickangle=-45, showlegend=False, height=600))
                st.plotly_chart(fig_s, use_container_width=True, key="ss_slab_bar", config=PLOTLY_CONFIG)

                det_cols = [c for c in ["substation","zone","circle","division","feeder_count",
                                        "consumers","billed_consumers","paid_consumers",
                                        "line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct",
                                        "input_energy_kwh","sold_energy_kwh","net_assessment_sub","revenue_realized"] if c in sdf.columns]
                sdf_d = sdf[det_cols].copy()
                sdf_d.insert(0,"#",range(1,len(sdf_d)+1))
                pf2 = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"] if c in sdf_d.columns}
                nf2 = {c:"{:,.0f}" for c in ["input_energy_kwh","sold_energy_kwh","net_assessment_sub","revenue_realized"] if c in sdf_d.columns}
                
                styler_s = sdf_d.style.format({**pf2,**nf2})
                if len(sdf_d) <= 500 and "atc_loss_pct" in sdf_d.columns:
                    styler_s = styler_s.background_gradient(subset=["atc_loss_pct"], cmap="RdYlGn_r")
                st.dataframe(styler_s, use_container_width=True, hide_index=True)
                
                st.download_button(f"📥 Download '{s['label']}' slab data",
                                   sdf[det_cols].to_csv(index=False).encode(),
                                   f"SS_Slab_{kpi_col}_{s['label'].replace('%','').replace(' ','_')}.csv",
                                   "text/csv", use_container_width=True, key="ss_slab_dl")

    # ══ STAB 8: DATA & EXPORT ═════════════════════════════════════════════════
    with stabs[7]:
        all_cols = df.columns.tolist()
        def_cols = [c for c in ["substation","zone","circle","division","feeder_count",
                                 "consumers","billed_consumers","paid_consumers","smart_meter_consumers",
                                 "input_energy_kwh","sold_energy_kwh","line_loss_pct",
                                 "billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct",
                                 "net_assessment_sub","revenue_realized","outstanding_amount",
                                 "tariff_subsidy","join_status"] if c in all_cols]
        show_cols = st.multiselect("Columns to display:", all_cols, default=def_cols, key="ss_cols")
        search    = st.text_input("🔍 Search substation / zone:", "", key="ss_search")
        df_d = df.copy()
        
        if search:
            str_cols = df_d.select_dtypes(include=['object', 'string']).columns
            if len(str_cols) > 0:
                mask = df_d[str_cols].apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
                df_d = df_d[mask]
            else:
                df_d = df_d.iloc[0:0]
                
        df_d = df_d[show_cols] if show_cols else df_d
        pf = {c:"{:.1f}%" for c in ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"] if c in df_d.columns}
        nf = {c:"{:,.0f}" for c in ["input_energy_kwh","sold_energy_kwh","net_assessment_sub","revenue_realized"] if c in df_d.columns}
        
        styler_d = df_d.style.format({**pf,**nf})
        if len(df_d) <= 500 and "atc_loss_pct" in df_d.columns:
            styler_d = styler_d.background_gradient(subset=["atc_loss_pct"], cmap="RdYlGn_r")
            
        st.dataframe(styler_d, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(df_d)} of {len(df)} substations")

        dc1,dc2,dc3 = st.columns(3)
        with dc1:
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode(),
                               f"DVVNL_Substation_ATC_Apr2026.csv","text/csv",use_container_width=True,key="ss_dl_csv")
        with dc2:
            st.download_button("📊 Download Excel", export_excel(df),
                               f"DVVNL_Substation_ATC_Apr2026.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True, key="ss_dl_xlsx")
        with dc3:
            if not unmatched_df.empty:
                st.download_button("⚠️ Unmatched Substations CSV",unmatched_df.to_csv(index=False).encode(),
                                   "SS_Unmatched.csv","text/csv",use_container_width=True,key="ss_dl_um")
            else:
                st.success("✅ All substations matched!")

        st.markdown("---")
        st.markdown(f"**Grand Total - {current_hierarchy}**")
        st.dataframe(pd.DataFrame([gt]), use_container_width=True, hide_index=True)


# For standalone testing
if __name__ == "__main__":
    render()