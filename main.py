"""
main.py — DVVNL Analytics Hub (Super-Tab Launcher)
===================================================
Run: python -m streamlit run main.py
"""

import streamlit as st
import sys, os
import importlib

st.set_page_config(
    page_title="DVVNL Commercial Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── SHARED CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&family=JetBrains+Mono:wght@400;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background-color:#e0e7ff;color:#0f172a;}
.main,.stApp{background-color:#e0e7ff;}
.stTabs [data-baseweb="tab-list"]{background:#457a9f;border-bottom:1px solid rgb(41 78 112);gap:4px;border-radius:16px;padding:4px;}
.stTabs [data-baseweb="tab"]{color:#334155;background:#dbeafe;border-radius:10px 10px 0 0;
    font-size:20px;font-weight:900;padding:14px 28px;}
.stTabs [aria-selected="true"]{color:#fff!important;background:#7c3aed!important;}
[data-testid="metric-container"]{background:#dbeafe;border:1px solid #7c3aed;border-radius:14px;padding:12px 16px;}
[data-testid="metric-container"] label{color:#475569!important;font-size:11px!important;}
[data-testid="metric-container"] [data-testid="stMetricValue"]{color:#0f172a!important;font-family:'JetBrains Mono',monospace;}
[data-testid="stPlotlyChart"]>div:first-child{background:#dbeafe!important;border:1px solid #7c3aed!important;
    border-radius:16px!important;padding:16px!important;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#eef2ff,#e0e7ff,#c7d2fe)!important;
    border-right:2px solid #a5b4fc!important;}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div{color:#334155!important;font-weight:700!important;font-size:14px!important;}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select{background:rgba(255,255,255,.85)!important;
    border:1.5px solid #c7d2fe!important;color:#1e293b!important;
    font-size:14px!important;font-weight:600!important;border-radius:12px!important;}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ── HUB HEADER ────────────────────────────────────────────────────────────────
st.markdown("""
    <div style="
        background:linear-gradient(90deg,#075a94,#4e7c9c,#4e7c9c);
        padding:14px 28px;
        border-radius:16px;
        margin-bottom:5px;
        text-align:center;
    ">
        <div style="color:#fff;font-size:20px;letter-spacing:1px;font-weight:700;">
            DVVNL • DAKSHINANCHAL VIDYUT VITRAN NIGAM LIMITED
        <div style="font-size:26px;font-weight:900;color:#fff;">
          ⚡ AT&amp;C Loss Analytics — April 2026
                <div style="color:#fff;font-size:20px;">
            Feeders &amp; Substations
        </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── SESSION STATE FOR TRACKING LOADED MODULES ─────────────────────────────────
if 'loaded_tabs' not in st.session_state:
    st.session_state.loaded_tabs = set()

# ── SUPER TABS ─────────────────────────────────────────────────────────────────
super_tabs = st.tabs([
    "⚡  FEEDER DASHBOARD",
    "🏗️  SUBSTATION DASHBOARD",
    "📊  DVVNL OVERALL DASHBOARD",
])

# ══ SUPER TAB 1: FEEDER ═══════════════════════════════════════════════════════
with super_tabs[0]:
    if 'feeder' not in st.session_state.loaded_tabs:
        st.session_state.loaded_tabs.add('feeder')
    
    _app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    if os.path.exists(_app_path):
        import re
        with open(_app_path, "r", encoding="utf-8") as _f:
            raw = _f.read()
        cleaned = re.sub(
            r'st\.set_page_config\s*\(.*?\)',
            '# set_page_config handled by main.py',
            raw, flags=re.DOTALL
        )
        exec(compile(cleaned, _app_path, "exec"), {"__name__": "__feeder_app__"})
    else:
        st.error("❌ `app.py` not found")

# ══ SUPER TAB 2: SUBSTATION ═══════════════════════════════════════════════════
with super_tabs[1]:
    if 'substation' not in st.session_state.loaded_tabs:
        st.session_state.loaded_tabs.add('substation')
    
    try:
        # Force reload the module to ensure fresh state
        if 'substation_dashboard' in sys.modules:
            importlib.reload(sys.modules['substation_dashboard'])
        
        from substation_dashboard import render as _render_substations
        _render_substations()
    except Exception as _e:
        import traceback
        st.error(f"❌ Substation dashboard error: {_e}")
        st.code(traceback.format_exc())
        st.info("Make sure `substation_dashboard.py` and `substation_queries.py` are in the same folder.")

# ══ SUPER TAB 3: DVVNL OVERALL ════════════════════════════════════════════════
with super_tabs[2]:
    if 'overall' not in st.session_state.loaded_tabs:
        st.session_state.loaded_tabs.add('overall')
    
    try:
        # Force reload the module to ensure fresh state
        if 'overall_dvvnl' in sys.modules:
            importlib.reload(sys.modules['overall_dvvnl'])
        
        from overall_dvvnl import render as _render_overall
        _render_overall()
    except Exception as _e:
        import traceback
        st.error(f"❌ Overall dashboard error: {_e}")
        st.code(traceback.format_exc())
        st.info("Make sure `overall_dvvnl.py` exists and `DVVNL_OVERALL_APRIL26.csv` is in the same folder.")
        
        # Show sample CSV generator
        st.markdown("---")
        st.markdown("### 📝 Sample CSV Generator")
        if st.button("Generate Sample CSV File"):
            from overall_dvvnl import generate_sample_csv
            sample_df = generate_sample_csv()
            sample_df.to_csv("DVVNL_OVERALL_APRIL26.csv", index=False)
            st.success("✅ Sample CSV file 'DVVNL_OVERALL_APRIL26.csv' created!")
            st.dataframe(sample_df)