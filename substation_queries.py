"""
substation_queries.py — DuckDB data layer for Substation Analytics
===================================================================
Loads DVVNL_ENERGY_APRIL26 (for hierarchy + input energy per substation)
and DVVNL_MASTER_APRIL26_SUBSTATIONS (billing KPIs per substation).
Single DB hit, all aggregation in pandas.
"""

import pandas as pd
import numpy as np
from config import ENERGY_TABLE, SUBSTATION_TABLE, ENERGY_COLS as EC, SUBSTATION_COLS as SC

# ── HELPERS ───────────────────────────────────────────────────────────────────
def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip().str.replace(r'[^A-Z0-9]', '', regex=True)

def _calc_kpis(df: pd.DataFrame) -> pd.DataFrame:
    inp  = df['input_energy_kwh'].replace(0, np.nan)
    sold = df['sold_energy_kwh'].replace(0, np.nan)
    rev  = df['revenue_realized'].replace(0, np.nan)
    ass  = df['net_assessment_sub'].replace(0, np.nan)
    be   = (sold / inp).fillna(0).clip(0, 1)
    ce   = (rev  / ass).fillna(0).clip(0, 1)
    df['line_loss_pct']             = ((inp - sold) / inp * 100).round(2).fillna(0)
    df['billing_efficiency_pct']    = (be * 100).round(2)
    df['collection_efficiency_pct'] = (ce * 100).round(2)
    df['atc_loss_pct']              = ((1 - be * ce) * 100).round(2).clip(0, 100)
    df['abr_rs_per_kwh']            = (df['net_assessment_sub'] / sold.replace(0, np.nan)).round(2).fillna(0)
    df['avg_collection_rate']       = (rev / sold.replace(0, np.nan)).round(2).fillna(0)
    df['realization_rate']          = (rev / inp).round(2).fillna(0)
    return df

def _agg_kpis(g: pd.DataFrame) -> pd.Series:
    inp  = g['input_energy_kwh'].sum()
    sold = g['sold_energy_kwh'].sum()
    rev  = g['revenue_realized'].sum()
    ass  = g['net_assessment_sub'].sum()
    be   = sold / inp if inp > 0 else 0
    ce   = rev  / ass if ass > 0 else 0
    return pd.Series({
        'substation_count':          len(g),
        'total_input':               round(inp,  2),
        'total_sold':                round(sold, 2),
        'total_assessment':          round(ass,  0),
        'total_revenue':             round(rev,  0),
        'line_loss_pct':             round((inp-sold)/inp*100, 2) if inp>0 else 0,
        'billing_efficiency_pct':    round(be*100, 2),
        'collection_efficiency_pct': round(ce*100, 2),
        'atc_loss_pct':              round((1-be*ce)*100, 2),
    })


# ══════════════════════════════════════════════════════════════════════════════
# LOAD RAW — 2 DuckDB hits, cached 10 min
# ══════════════════════════════════════════════════════════════════════════════
def load_substation_data(con) -> tuple:
    """
    Hit 1: Energy table aggregated to 1 row per substation (hierarchy + input energy).
    Hit 2: Substation master table (all billing KPIs already at substation level).
    Returns (energy_sub_df, substation_billing_df).
    """

    # ── Energy: aggregate to substation level ────────────────────────────────
    energy_sql = f"""
    SELECT
        TRIM("{EC['substation']}")  AS substation,
        MAX(TRIM("{EC['discom']}")) AS discom,
        MAX(TRIM("{EC['zone']}"))   AS zone,
        MAX(TRIM("{EC['circle']}")) AS circle,
        MAX(TRIM("{EC['division']}")) AS division,
        COUNT(DISTINCT TRIM("{EC['outgoing_feeder']}")) AS feeder_count,
        SUM(COALESCE(TRY_CAST("{EC['total_energy']}" AS DOUBLE), 0) * 1000) AS input_energy_kwh
    FROM {ENERGY_TABLE}
    WHERE "{EC['substation']}" IS NOT NULL
      AND LENGTH(TRIM("{EC['substation']}")) > 0
    GROUP BY TRIM("{EC['substation']}")
    """
    energy_sub_df = con.execute(energy_sql).df().reset_index(drop=True)

    # ── Substation billing table ─────────────────────────────────────────────
    billing_sql = f"""
    SELECT
        TRIM("{SC['substation']}")                                              AS substation,
        TRIM(COALESCE(CAST("{SC['div_code']}"  AS VARCHAR),''))                AS div_code,
        TRIM(COALESCE(CAST("{SC['sdo_code']}"  AS VARCHAR),''))                AS sdo_code,
        TRIM(COALESCE(CAST("{SC['category']}"  AS VARCHAR),''))                AS category,

        SUM(COALESCE(TRY_CAST("{SC['consumers']}"            AS DOUBLE),0))    AS consumers,
        SUM(COALESCE(TRY_CAST("{SC['billed_consumers']}"     AS DOUBLE),0))    AS billed_consumers,
        SUM(COALESCE(TRY_CAST("{SC['paid_consumers']}"       AS DOUBLE),0))    AS paid_consumers,
        SUM(COALESCE(TRY_CAST("{SC['inf_bill_consumers']}"   AS DOUBLE),0))    AS inf_bill_consumers,
        SUM(COALESCE(TRY_CAST("{SC['smart_meter_consumers']}" AS DOUBLE),0))   AS smart_meter_consumers,
        SUM(COALESCE(TRY_CAST("{SC['unmetered_consumers']}"  AS DOUBLE),0))    AS unmetered_consumers,
        SUM(COALESCE(TRY_CAST("{SC['nsc_consumers']}"        AS DOUBLE),0))    AS nsc_consumers,
        SUM(COALESCE(TRY_CAST("{SC['td_consumers']}"         AS DOUBLE),0))    AS td_consumers,
        SUM(COALESCE(TRY_CAST("{SC['govt_code_consumers']}"  AS DOUBLE),0))    AS govt_consumers,
        SUM(COALESCE(TRY_CAST("{SC['govt_lmv4_consumers']}"  AS DOUBLE),0))    AS govt_lmv4_consumers,
        SUM(COALESCE(TRY_CAST("{SC['qb_consumers']}"         AS DOUBLE),0))    AS qb_consumers,

        SUM(COALESCE(TRY_CAST("{SC['operative_load_kw']}"    AS DOUBLE),0))    AS operative_load_kw,
        SUM(COALESCE(TRY_CAST("{SC['sold_energy_kwh']}"      AS DOUBLE),0))    AS sold_energy_kwh,
        SUM(COALESCE(TRY_CAST("{SC['current_assessment']}"   AS DOUBLE),0))    AS current_assessment,
        SUM(COALESCE(TRY_CAST("{SC['revenue_realized']}"     AS DOUBLE),0))    AS revenue_realized,
        SUM(COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0))   AS assessment_ex_subsidy,
        SUM(COALESCE(TRY_CAST("{SC['current_assessment_master']}" AS DOUBLE),0)) AS current_assessment_master,

        SUM(COALESCE(TRY_CAST("{SC['tariff_subsidy']}"       AS DOUBLE),0))    AS tariff_subsidy,
        SUM(COALESCE(TRY_CAST("{SC['ptw_subsidy']}"          AS DOUBLE),0))    AS ptw_subsidy,
        SUM(COALESCE(TRY_CAST("{SC['powerloom_subsidy']}"    AS DOUBLE),0))    AS powerloom_subsidy,

        SUM(COALESCE(TRY_CAST("{SC['outstanding_amount']}"   AS DOUBLE),0))    AS outstanding_amount,
        SUM(COALESCE(TRY_CAST("{SC['inoperative_amount']}"   AS DOUBLE),0))    AS inoperative_amount,
        SUM(COALESCE(TRY_CAST("{SC['lpsc_amount']}"          AS DOUBLE),0))    AS lpsc_amount,
        SUM(COALESCE(TRY_CAST("{SC['lt_metering_charges']}"  AS DOUBLE),0))    AS lt_metering_charges,
        SUM(COALESCE(TRY_CAST("{SC['cap_charges']}"          AS DOUBLE),0))    AS cap_charges,

        SUM(COALESCE(TRY_CAST("{SC['govt_lmv4_units_kwh']}"  AS DOUBLE),0))    AS govt_units_kwh,
        SUM(COALESCE(TRY_CAST("{SC['govt_lmv4_assessment']}" AS DOUBLE),0))    AS govt_assessment,
        SUM(COALESCE(TRY_CAST("{SC['govt_lmv4_revenue']}"    AS DOUBLE),0))    AS govt_revenue,
        SUM(COALESCE(TRY_CAST("{SC['ptw_load_kw']}"          AS DOUBLE),0))    AS ptw_load_kw,
        SUM(COALESCE(TRY_CAST("{SC['ptw_units_kwh']}"        AS DOUBLE),0))    AS ptw_units_kwh,

        SUM(
        CASE
        WHEN UPPER(TRIM("{SC['category']}"))='LMV-5'
        THEN COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv5_assessment,

        SUM(
        CASE
        WHEN UPPER(TRIM("{SC['category']}"))='LMV-3'
        THEN COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv3_assessment,    

        SUM(
        CASE
        WHEN UPPER(TRIM("{SC['category']}"))='LMV-7'
        THEN COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv7_assessment,

        SUM(    
        CASE
        WHEN UPPER(TRIM("{SC['category']}"))='LMV-8'
        THEN COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv8_assessment,  

        SUM(
        CASE
        WHEN UPPER(TRIM("{SC['category']}"))='HV-4'
        THEN COALESCE(TRY_CAST("{SC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS hv4_assessment,     

        SUM(COALESCE(TRY_CAST("{SC['ptw_assessment']}"       AS DOUBLE),0))    AS ptw_assessment

    FROM {SUBSTATION_TABLE}
    WHERE "{SC['substation']}" IS NOT NULL
      AND LENGTH(TRIM("{SC['substation']}")) > 0
    GROUP BY
        TRIM("{SC['substation']}"),
        TRIM(COALESCE(CAST("{SC['div_code']}"  AS VARCHAR),'')),
        TRIM(COALESCE(CAST("{SC['sdo_code']}"  AS VARCHAR),'')),
        TRIM(COALESCE(CAST("{SC['category']}"  AS VARCHAR),''))
    """
    billing_sub_df = con.execute(billing_sql).df().reset_index(drop=True)
    billing_sub_df['net_assessment_sub'] = (
    billing_sub_df['assessment_ex_subsidy']
    - billing_sub_df['lmv5_assessment']
    - billing_sub_df['lmv3_assessment']
    - billing_sub_df['lmv7_assessment']
    - billing_sub_df['lmv8_assessment']
    - billing_sub_df['hv4_assessment']
    - billing_sub_df['govt_assessment']
    + billing_sub_df['ptw_assessment']

#    - billing_sub_df['tariff_subsidy']
#    - billing_sub_df['ptw_subsidy']
#    - billing_sub_df['powerloom_subsidy']
   
    )

    return energy_sub_df, billing_sub_df


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ALL — pure pandas, zero extra DB hits
# ══════════════════════════════════════════════════════════════════════════════
def process_substation(energy_sub_df: pd.DataFrame, billing_sub_df: pd.DataFrame,
                       zone_filter: str, circle_filter: str, division_filter: str) -> dict:
    """Join energy → billing at substation level and compute KPIs."""

    edf = energy_sub_df.copy()
    bdf = billing_sub_df.copy()

    # Normalize keys
    edf['fk'] = _norm(edf['substation'])
    bdf['fk'] = _norm(bdf['substation'])

    # Aggregate billing side to 1 row per substation (in case multiple categories)
    num_cols = [c for c in bdf.columns if c not in ['fk','substation','div_code','sdo_code','category']]
    bdf_agg = bdf.groupby('fk', sort=False)[num_cols].sum().reset_index()
    # Bring back substation name
    bdf_name = bdf.groupby('fk')['substation'].first().reset_index()
    bdf_agg  = bdf_agg.merge(bdf_name, on='fk', how='left', suffixes=('','_b'))

    # Merge
    merged = edf.merge(bdf_agg, on='fk', how='left', suffixes=('','_b'))
    merged['substation'] = merged['substation'].fillna(merged.get('substation_b', ''))
    merged['join_status'] = np.where(merged['fk'].isin(bdf_agg['fk']), 'MATCHED', 'UNMATCHED')

    # Fill numeric nulls
    fill_cols = [c for c in bdf_agg.columns if c not in ['fk','substation']]
    for c in fill_cols:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors='coerce').fillna(0)

    merged = _calc_kpis(merged)

    # Apply filters
    df = merged.copy()
    if zone_filter     and zone_filter     != "All Zones":
        df = df[df['zone']     == zone_filter]
    if circle_filter   and circle_filter   != "All Circles":
        df = df[df['circle']   == circle_filter]
    if division_filter and division_filter != "All Divisions":
        df = df[df['division'] == division_filter]

    df = df.sort_values('atc_loss_pct', ascending=False).reset_index(drop=True)

    # Summaries
    zone_df     = df.groupby('zone',     sort=False).apply(_agg_kpis).reset_index() if 'zone'     in df.columns else pd.DataFrame()
    circle_df   = df.groupby('circle',   sort=False).apply(_agg_kpis).reset_index() if 'circle'   in df.columns else pd.DataFrame()
    division_df = df.groupby('division', sort=False).apply(_agg_kpis).reset_index() if 'division' in df.columns else pd.DataFrame()

    # Grand total
    inp  = df['input_energy_kwh'].sum()
    sold = df['sold_energy_kwh'].sum()
    rev  = df['revenue_realized'].sum()
    ass  = df['net_assessment_sub'].sum()
    be   = sold/inp if inp>0 else 0
    ce   = rev/ass  if ass>0 else 0
    gt = {
        'input_energy_kwh':            round(inp,  2),
        'sold_energy_kwh':             round(sold, 2),
        'net_assessment_sub':          round(ass,  2),
        'revenue_realized':            round(rev,  2),
        'consumers':                   int(df['consumers'].sum())            if 'consumers'            in df else 0,
        'billed_consumers':            int(df['billed_consumers'].sum())     if 'billed_consumers'     in df else 0,
        'paid_consumers':              int(df['paid_consumers'].sum())       if 'paid_consumers'       in df else 0,
        'smart_meter_consumers':       int(df['smart_meter_consumers'].sum())if 'smart_meter_consumers'in df else 0,
        'outstanding_amount':          round(df['outstanding_amount'].sum(), 2) if 'outstanding_amount' in df else 0,
        'tariff_subsidy':              round(df['tariff_subsidy'].sum(),     2) if 'tariff_subsidy'     in df else 0,
        'ptw_subsidy':                 round(df['ptw_subsidy'].sum(),        2) if 'ptw_subsidy'        in df else 0,
        'powerloom_subsidy':           round(df['powerloom_subsidy'].sum(),  2) if 'powerloom_subsidy'  in df else 0,
        'line_loss_pct':               round((inp-sold)/inp*100, 2) if inp>0 else 0,
        'billing_efficiency_pct':      round(be*100, 2),
        'collection_efficiency_pct':   round(ce*100, 2),
        'atc_loss_pct':                round((1-be*ce)*100, 2),
    }

    funnel = {
        'Total Consumers':  int(df['consumers'].sum())       if 'consumers'       in df else 0,
        'Billed Consumers': int(df['billed_consumers'].sum())if 'billed_consumers' in df else 0,
        'Paid Consumers':   int(df['paid_consumers'].sum())  if 'paid_consumers'   in df else 0,
    }

    # Slab histogram
    bins   = [-999,0,10,15,25,40,60,999]
    labels = ['Negative','<10%','10-15%','15-25%','25-40%','40-60%','>60%']
    df['atc_bucket'] = pd.cut(df['atc_loss_pct'], bins=bins, labels=labels)
    hist_df = (df.groupby('atc_bucket', observed=True)
                 .agg(substation_count=('atc_loss_pct','count'),
                      avg_atc         =('atc_loss_pct','mean'))
                 .reset_index())
    hist_df['avg_atc'] = hist_df['avg_atc'].round(1)

    unmatched_df = df[df['join_status']=='UNMATCHED'][
        [c for c in ['substation','zone','circle','division','input_energy_kwh','feeder_count']
         if c in df.columns]
    ].copy()

    zones_list     = sorted(merged['zone'].dropna().unique().tolist())     if 'zone'     in merged.columns else []
    circles_list   = sorted(merged['circle'].dropna().unique().tolist())   if 'circle'   in merged.columns else []
    divisions_list = sorted(merged['division'].dropna().unique().tolist()) if 'division' in merged.columns else []

    return {
        'df':            df,
        'zone_df':       zone_df,
        'circle_df':     circle_df,
        'division_df':   division_df,
        'gt':            gt,
        'funnel':        funnel,
        'hist_df':       hist_df,
        'unmatched_df':  unmatched_df,
        'zones_list':    zones_list,
        'circles_list':  circles_list,
        'divisions_list':divisions_list,
    }