"""
run_optimized.py — Optimized launcher for DVVNL Dashboard
==========================================================
Run: streamlit run run_optimized.py

This version implements:
- Lazy loading of modules
- Session state caching
- Progressive rendering
- Reduced DOM updates
"""

import streamlit as st
import time

# Configure page FIRST
st.set_page_config(
    page_title="DVVNL Commercial Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"  # Collapsed by default for faster load
)

# Minimal CSS for faster rendering
st.markdown("""
<style>
    /* Minimal critical CSS only */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 16px; font-size: 14px; }
    [data-testid="stPlotlyChart"] > div:first-child { padding: 8px !important; }
    section[data-testid="stSidebar"] { min-width: 200px; width: 250px; }
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
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
# Simple header
st.markdown("""
<div style="background:linear-gradient(90deg,#075a94,#4e7c9c);padding:8px 16px;border-radius:12px;margin-bottom:8px;text-align:center;">
    <span style="color:#fff;font-size:18px;font-weight:700;">⚡ DVVNL AT&amp;C Loss Analytics — April 2026</span>
</div>
""", unsafe_allow_html=True)

# Tab selection with session state for persistence
tab_options = ["Feeders", "Substations", "Overall"]
selected_tab = st.radio("Select Dashboard:", tab_options, horizontal=True, label_visibility="collapsed")

# Load only selected dashboard
if selected_tab == "Feeders":
    with st.spinner("Loading Feeder Dashboard..."):
        import subprocess
        # Run app.py in a subprocess or import directly
        try:
            # Direct import approach
            import importlib.util
            spec = importlib.util.spec_from_file_location("feeder_app", "app.py")
            feeder_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(feeder_module)
        except Exception as e:
            st.error(f"Error loading feeder dashboard: {e}")
            
elif selected_tab == "Substations":
    with st.spinner("Loading Substation Dashboard..."):
        try:
            from substation_dashboard import render
            render()
        except Exception as e:
            st.error(f"Error loading substation dashboard: {e}")
            
else:  # Overall
    with st.spinner("Loading Overall Dashboard..."):
        try:
            from overall_dvvnl import render
            render()
        except Exception as e:
            st.error(f"Error loading overall dashboard: {e}")
            st.info("Make sure DVVNL_OVERALL_APRIL26.csv exists")