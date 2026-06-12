"""
queries.py — OPTIMIZED DuckDB queries for DVVNL Feeder Analytics
KEY FIX: Energy table is aggregated to 1 row per feeder in SQL to prevent duplication.
Billing table is pre-aggregated, so no row-level date/load parsing is needed.
"""
from duckdb import df
import pandas as pd
import numpy as np
from config import (
    ENERGY_TABLE, BILLING_TABLE,
    ENERGY_COLS as EC, BILLING_COLS as BC,
    KPI_THRESHOLDS
)

# Add at top of queries.py after imports
import hashlib
import json

def get_filter_hash(zone_filter, circle_filter, nature_filter):
    """Generate a hash for filter combination"""
    key = f"{zone_filter}|{circle_filter}|{nature_filter}"
    return hashlib.md5(key.encode()).hexdigest()


def _norm_series(s: pd.Series) -> pd.Series:
    """Normalize feeder key: uppercase, strip, remove non-alphanumeric."""
    return s.astype(str).str.upper().str.strip().str.replace(r'[^A-Z0-9]', '', regex=True)

def _calc_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all AT&C KPIs from energy/billing columns."""
    inp  = df['input_energy_kwh'].replace(0, np.nan)
    sold = df['sold_energy_kwh'].replace(0, np.nan)
    rev  = df['revenue_realized'].replace(0, np.nan)
#    ass  = df['current_assessment'].replace(0, np.nan)

    ass = df['net_assessment'].replace(0, np.nan)
    
    df['line_loss_pct']             = ((inp - sold) / inp * 100).round(2).fillna(0)
    df['billing_efficiency_pct']    = (sold / inp * 100).round(2).fillna(0)
    df['collection_efficiency_pct'] = (rev  / ass * 100).round(2).fillna(0)
    
    be = (sold / inp).fillna(0)
    ce = (rev  / ass).fillna(0)
    df['atc_loss_pct']              = ((1 - be * ce) * 100).round(2).clip(upper=100)
    
    df['abr_rs_per_kwh']            = (df['net_assessment'] / sold.replace(0, np.nan)).round(2).fillna(0)
    df['avg_collection_rate']       = (rev / sold.replace(0, np.nan)).round(2).fillna(0)
    df['realization_rate']          = (rev / inp).round(2).fillna(0)
    return df

def load_all_data(con, month_start: str, month_end: str):
    """Single DuckDB execution loads both tables. Reset index immediately to prevent duplicate label errors."""
    
    # ── ENERGY TABLE: AGGREGATE TO FEEDER LEVEL ─────────────────────────────
    energy_sql = f"""
    SELECT
    TRIM("{EC['substation']}") AS substation,
    TRIM("{EC['outgoing_feeder']}") AS outgoing_feeder,

    MAX(TRIM("{EC['discom']}")) AS discom,
    MAX(TRIM("{EC['zone']}")) AS zone,
    MAX(TRIM("{EC['circle']}")) AS circle,
    MAX(TRIM("{EC['division']}")) AS division,
    MAX(TRIM("{EC['meter_status']}")) AS meter_status,
    MAX(TRIM("{EC['feeder_nature']}")) AS feeder_nature,

    SUM(
        COALESCE(
            TRY_CAST("{EC['total_energy']}" AS DOUBLE),
            0
        ) * 1000
    ) AS input_energy_kwh

    FROM {ENERGY_TABLE}

    WHERE "{EC['outgoing_feeder']}" IS NOT NULL

    GROUP BY
    TRIM("{EC['substation']}"),
    TRIM("{EC['outgoing_feeder']}")
    """
    energy_df = con.execute(energy_sql).df().reset_index(drop=True)

    # ── BILLING TABLE: ALREADY PRE-AGGREGATED AT FEEDER LEVEL ───────────────
    billing_sql = f"""
    SELECT
    TRIM("{BC['substation']}") AS substation,
    TRIM("{BC['feeder']}") AS feeder,

    SUM(
        COALESCE(
            TRY_CAST("{BC['consumers']}" AS DOUBLE),
            0
        )
    ) AS consumers,

    SUM(
        COALESCE(
            TRY_CAST("{BC['billed_consumers']}" AS DOUBLE),
            0
        )
    ) AS billed_consumers,

    SUM(
        COALESCE(
            TRY_CAST("{BC['paid_consumers']}" AS DOUBLE),
            0
        )
    ) AS paid_consumers,

        SUM(
        COALESCE(
            TRY_CAST("{BC['smart_meter_consumers']}" AS DOUBLE),
            0
        )
    ) AS smart_meter_consumers,

    SUM(
        COALESCE(
            TRY_CAST("{BC['sold_energy_kwh']}" AS DOUBLE),
            0
        )
    ) AS sold_energy_kwh,

    SUM(
        COALESCE(
            TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),
            0
        )
    ) AS assessment_ex_subsidy,

    SUM(
        COALESCE(
            TRY_CAST("{BC['revenue_realized']}" AS DOUBLE),
            0
        )
    ) AS revenue_realized,

    SUM(
        COALESCE(
            TRY_CAST("{BC['total_outstanding_amount']}" AS DOUBLE),
            0
        )
    ) AS total_outstanding_amount,

    SUM(
        COALESCE(
            TRY_CAST("{BC['total_inoperative_amount']}" AS DOUBLE),
            0
        )
    ) AS total_inoperative_amount,

    SUM(
        COALESCE(
            TRY_CAST("{BC['td_consumers']}" AS DOUBLE),
            0
        )
    ) AS td_consumers,

    SUM(
        COALESCE(
            TRY_CAST("{BC['govt_code_consumers']}" AS DOUBLE),
            0
        )
    ) AS govt_code_consumers,

        SUM(
        CASE
        WHEN UPPER(TRIM("{BC['category']}"))='LMV-5'
        THEN COALESCE(TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv5_assessment,

        SUM(
        CASE
        WHEN UPPER(TRIM("{BC['category']}"))='LMV-3'
        THEN COALESCE(TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv3_assessment,    

        SUM(
        CASE
        WHEN UPPER(TRIM("{BC['category']}"))='LMV-7'
        THEN COALESCE(TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv7_assessment,

        SUM(    
        CASE
        WHEN UPPER(TRIM("{BC['category']}"))='LMV-8'
        THEN COALESCE(TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS lmv8_assessment,  

        SUM(
        CASE
        WHEN UPPER(TRIM("{BC['category']}"))='HV-4'
        THEN COALESCE(TRY_CAST("{BC['assessment_ex_subsidy']}" AS DOUBLE),0)
        ELSE 0
        END
            ) AS hv4_assessment,     
        
        SUM(COALESCE(TRY_CAST("{BC['govt_lmv4_assessment']}" AS DOUBLE),0))    AS govt_assessment,

        SUM(COALESCE(TRY_CAST("{BC['ptw_assessment']}"       AS DOUBLE),0))    AS ptw_assessment


    


    FROM {BILLING_TABLE}

    GROUP BY
    TRIM("{BC['substation']}"),
    TRIM("{BC['feeder']}")
    """

    billing_df = con.execute(billing_sql).df().reset_index(drop=True)

    billing_df['net_assessment'] = (
    billing_df['assessment_ex_subsidy']
    - billing_df['lmv5_assessment']
    - billing_df['lmv3_assessment']
    - billing_df['lmv7_assessment']
    - billing_df['lmv8_assessment']
    - billing_df['hv4_assessment']
    - billing_df['govt_assessment']
    + billing_df['ptw_assessment']
    )

    return energy_df, billing_df

def process_all(energy_df: pd.DataFrame, billing_df: pd.DataFrame,
                month_start: str, month_end: str,
                zone_filter: str, circle_filter: str, nature_filter: str):
    """All processing in pandas after single DB fetch."""
#    print("ENERGY COLUMNS")
#    print(energy_df.columns.tolist())

#    print("BILLING COLUMNS")
#    print(billing_df.columns.tolist())
    # 1. Normalize feeder keys
    energy_df = energy_df.copy()

    energy_df['fk'] = (
    _norm_series(energy_df['substation']) +
    _norm_series(energy_df['outgoing_feeder'])
)
    billing_df = billing_df.copy()
    billing_df['fk'] = (
    _norm_series(billing_df['substation']) +
    _norm_series(billing_df['feeder'])
)
    
    

#    print("Energy Rows:", len(energy_df))
#    print("Energy Unique FK:", energy_df['fk'].nunique())

#    print("Billing Rows:", len(billing_df))
#    print("Billing Unique FK:", billing_df['fk'].nunique())

    energy_dups = energy_df[
    energy_df.duplicated('fk', keep=False)
]

#    print("Energy Duplicate Count:", len(energy_dups))

    billing_dups = billing_df[
    billing_df.duplicated('fk', keep=False)
]

 #   print("Billing Duplicate Count:", len(billing_dups))
    # 2. Merge: Energy (left) with Billing (right)
   
    merged = pd.merge(
    energy_df,
    billing_df,
    on='fk',
    how='left'
)
    merged['substation'] = merged['substation_x'].fillna(
    merged['substation_y']
)
#    print("MERGED COLUMNS:")
#    print(merged.columns.tolist())
    merged = merged.drop_duplicates(
    subset=['substation', 'outgoing_feeder']
)
    merged = merged.reset_index(drop=True)
    # CRITICAL FIX: Reset index immediately after merge to guarantee unique labels
    
    # 3. Standardize column names (clean up merge suffixes)
    merged = merged.drop(columns=['fk'], errors='ignore')
    
    # Drop all columns with _eng or _bill suffixes, and the 'fk' key
    cols_to_keep = ['outgoing_feeder'] + [
        c for c in merged.columns 
        if not c.endswith('_eng') and not c.endswith('_bill') and c != 'fk'
    ]
    merged = merged[cols_to_keep]
    
    # Fill missing energy data with 0
    if 'input_energy_kwh' in merged.columns:
        merged['input_energy_kwh'] = merged['input_energy_kwh'].fillna(0)
        
    # 4. Compute KPIs
    merged = _calc_kpis(merged)
    numeric_cols = [
    'input_energy_kwh',
    'sold_energy_kwh',
    'net_assessment',
    'revenue_realized',
    'consumers',
    'billed_consumers',
    'paid_consumers'
]

    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(
            merged[col],
            errors='coerce'
        ).fillna(0)

    # 5. Apply filters
    df = merged.copy()
    if zone_filter and zone_filter != "All Zones":
        df = df[df['zone'] == zone_filter]
    if circle_filter and circle_filter != "All Circles":
        df = df[df['circle'] == circle_filter]
    if nature_filter and nature_filter != "All Types":
        df = df[df['feeder_nature'] == nature_filter]

    # CRITICAL FIX: Reset index after filtering to maintain clean boolean operations
    df = df.sort_values('atc_loss_pct', ascending=False).reset_index(drop=True)

    # 6. Zone summary
    def _agg_kpis(g):
        inp  = g['input_energy_kwh'].sum()
        sold = g['sold_energy_kwh'].sum()
        rev  = g['revenue_realized'].sum()
        ass  = g['net_assessment'].sum()
        be   = sold / inp if inp > 0 else 0
        ce   = rev / ass if ass > 0 else 0
        return pd.Series({
            'feeder_count': len(g),
            'total_input': round(inp, 2),
            'total_sold': round(sold, 2),
            'total_assessment': round(ass, 2),
            'total_revenue': round(rev, 2),
            'line_loss_pct': round((inp-sold)/inp*100, 2) if inp > 0 else 0,
            'billing_efficiency_pct': round(be*100, 2),
            'collection_efficiency_pct': round(ce*100, 2),
            'atc_loss_pct': round((1-be*ce)*100, 2),
        })

    zone_df = df.groupby('zone', sort=False).apply(_agg_kpis).reset_index()
    circle_df = df.groupby('circle', sort=False).apply(_agg_kpis).reset_index()
    nature_df = df.groupby('feeder_nature', sort=False).apply(_agg_kpis).reset_index()

    # 7. Grand total
    inp  = df['input_energy_kwh'].sum()
    sold = df['sold_energy_kwh'].sum()
    rev  = df['revenue_realized'].sum()
    ass  = df['net_assessment'].sum()
    be   = sold/inp if inp > 0 else 0
    ce   = rev/ass if ass > 0 else 0
    gt = {
        'input_energy_kwh': round(inp, 2),
        'sold_energy_kwh': round(sold, 2),
        'net_assessment': round(ass, 2),
        'revenue_realized': round(rev, 2),
        'consumers': int(df['consumers'].sum()),
        'billed_consumers': int(df['billed_consumers'].sum()),
        'paid_consumers': int(df['paid_consumers'].sum()),
        'smart_meter_consumers': int(df['smart_meter_consumers'].sum()),
        'total_outstanding_amount': round(df['total_outstanding_amount'].sum(), 2) if 'total_outstanding_amount' in df else 0,
        'line_loss_pct': round((inp-sold)/inp*100, 2) if inp > 0 else 0,
        'billing_efficiency_pct': round(be*100, 2),
        'collection_efficiency_pct': round(ce*100, 2),
        'atc_loss_pct': round((1-be*ce)*100, 2),
    }

    # 8. Consumer funnel
    funnel = {
        'Total Consumers': int(df['consumers'].sum()),
        'Billed Consumers': int(df['billed_consumers'].sum()),
        'Paid Consumers': int(df['paid_consumers'].sum()),
    }

    # 9. Loss histogram
    bins = [-999, 0, 10, 15, 25, 40, 60, 999]
    labels = ['Negative', '< 10%', '10-15%', '15-25%', '25-40%', '40-60%', '> 60%']
    df['atc_bucket'] = pd.cut(df['atc_loss_pct'], bins=bins, labels=labels)
    hist_df = (df.groupby('atc_bucket', observed=True)
                 .agg(feeder_count=('atc_loss_pct', 'count'),
                      avg_atc=('atc_loss_pct', 'mean'))
                 .reset_index()
                 .rename(columns={'atc_bucket': 'atc_bucket'}))
    hist_df['avg_atc'] = hist_df['avg_atc'].round(1)



    # 10. Unmatched feeders (Safe from duplicate index errors)
    req_cols = ['outgoing_feeder', 'zone', 'circle', 'substation', 'input_energy_kwh']
   
    df = df.loc[:, ~df.columns.duplicated()]

    avail_cols = [c for c in req_cols if c in df.columns]



    unmatched_df = df[df['outgoing_feeder'].isna() | (df['input_energy_kwh'] == 0)][avail_cols].copy()

    # 11. Filter options for sidebar
    zones_list = sorted(merged['zone'].dropna().unique().tolist())
    circles_list = sorted(merged['circle'].dropna().unique().tolist())

    return {
        'df': df,
        'zone_df': zone_df,
        'circle_df': circle_df,
        'nature_df': nature_df,
        'gt': gt,
        'funnel': funnel,
        'hist_df': hist_df,
        'unmatched_df': unmatched_df,
        'zones_list': zones_list,
        'circles_list': circles_list,
    }