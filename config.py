"""
config.py — DVVNL Dashboard Configuration
⚠️  EDIT THIS FILE BEFORE RUNNING THE DASHBOARD
"""

# ── DATABASE PATH ─────────────────────────────────────────────────────────────
DB_PATH = r"C:\Users\ksas2\dvvnl.duckdb"

# ── BILLING PERIOD ────────────────────────────────────────────────────────────
APRIL_START = "2026-04-01"
APRIL_END   = "2026-04-30"

# ── TABLE NAMES ───────────────────────────────────────────────────────────────
ENERGY_TABLE  = "DVVNL_ENERGY_APRIL26"
BILLING_TABLE = "DVVNL_MASTER_APRIL26_FEEDERS"  # ← Your new pre-aggregated table
SUBSTATION_TABLE   = "DVVNL_MASTER_APRIL26_SUBSTATIONS"   # ← NEW

# ── KPI THRESHOLDS ────────────────────────────────────────────────────────────
KPI_THRESHOLDS = {
    "atc_good": 15.0,
    "atc_ok": 30.0,
    "atc_high": 50.0,
    "be_good": 85.0,
    "be_warn": 70.0,
    "ce_good": 90.0,
    "ce_warn": 75.0,
}

# ── CHART COLORS ─────────────────────────────────────────────────────────────
COLOR_PALETTE = [
    "#00d4ff", "#ff6b35", "#7fff6b", "#ff6bde",
    "#ffe66b", "#6b8fff", "#ff6b6b", "#6bffde",
    "#ffa86b", "#b46bff", "#34d399", "#fbbf24",
]

# ── ENERGY COLUMN MAPPING ─────────────────────────────────────────────────────
ENERGY_COLS = {
    "discom": "Discom",
    "zone": "Zone",
    "circle": "Circle",
    "division": "Division",
    "substation": "Substation",
    "outgoing_feeder": "Outgoing Feeder",
    "meter_status": "Meter Status",
    "total_energy": "Total Energy Consumption",
    "energy_assessed": "Energy Assessed",
    "overall_mf": "OverallMF",
    "feeder_nature": "Feeder Nature",
}

# ── BILLING COLUMN MAPPING (Pre-aggregated Feeder Table) ──────────────────────
BILLING_COLS = {
    "div_code": "DIV_CODE",
    "sdo_code": "SDO_CODE",
    "substation": "SUBSTATION",
    "feeder": "FEEDER",
    "category": "CATEGORY",
    "consumers": "OPERATIVE_CONSUMERS",
    "billed_consumers": "BILLED_CONSUMERS",
    "paid_consumers": "PAID_COUNT",
    "sold_energy_kwh": "APR26_CONSUMPTION_KWH",
    "current_assessment": "APR26_ASSESSMENT_AMT",
    "revenue_realized": "PAID_AMOUNT",
    "total_outstanding_amount": "TOTAL_OUTSTANDING_AMOUNT",
    "total_inoperative_amount": "TOTAL_INOPERATIVE_AMOUNT",
    "td_consumers": "TD_CONSUMERS",
    "govt_code_consumers": "GOVT_CODE_CONSUMERS",
    
    "ptw_assessment": "PTW_CONSUMERS_ASSESSMENT",

    "tariff_subsidy": "TARIFF_SUBSIDY",

    "ptw_subsidy": "PTW_SUBSIDY",

    "powerloom_subsidy": "POWERLOOM_SUBSIDY",

"assessment_ex_subsidy":       "CA_EX_SUBS_MASTER_AMOUNT",

   "govt_lmv4_assessment":        "GOVT_LMV4_HV1_ASSESSMENT",
       "smart_meter_consumers":       "SMART_METER_CONSUMERS",

}


# ── SUBSTATION TABLE COLUMN MAPPING ──────────────────────────────────────────
SUBSTATION_COLS = {
    "div_code":                    "DIV_CODE",
    "sdo_code":                    "SDO_CODE",
    "substation":                  "SUBSTATION",
    "category":                    "CATEGORY",
    "consumers":                   "OPERATIVE_CONSUMERS",
    "operative_load_kw":           "OPERATIVE_LOAD_KW",
    "sold_energy_kwh":             "APR26_CONSUMPTION_KWH",
    "current_assessment":          "APR26_ASSESSMENT_AMT",
    "billed_amount":               "APR26_BILLED_AMOUNT",
    "billed_consumers":            "BILLED_CONSUMERS",
    "inf_bill_consumers":          "INF_BILL_Y_CONSUMERS",
    "smart_meter_consumers":       "SMART_METER_CONSUMERS",
    "paid_consumers":              "PAID_COUNT",
    "revenue_realized":            "PAID_AMOUNT",
    "tariff_subsidy":              "TARIFF_SUBSIDY",
    "ptw_subsidy":                 "PTW_SUBSIDY",
    "powerloom_subsidy":           "POWERLOOM_SUBSIDY",
    "outstanding_amount":          "TOTAL_OUTSTANDING_AMOUNT",
    "inoperative_amount":          "TOTAL_INOPERATIVE_AMOUNT",
    "inoperative_count":           "TOTAL_INOPERATIVE_AMOUNT_COUNT",
    "lpsc_amount":                 "CURRENT_CYCLE_LPSC_AMOUNT",
    "assessment_ex_subsidy":       "CA_EX_SUBS_MASTER_AMOUNT",
    "current_assessment_master":   "CURRENT_ASSESSMENT_MASTER_AMOUNT",
    "lt_metering_charges":         "LTMETERING_CHARGES_AMOUNT",
    "cap_charges":                 "CAP_CHARGES_AMOUNT",
    "td_consumers":                "TD_CONSUMERS",
    "td_6mnth_consumers":          "TD_6MNTH_CONSUMERS",
    "nsc_consumers":               "NSC_CONSUMERS",
    "govt_code_consumers":         "GOVT_CODE_CONSUMERS",
    "mu_consumers":                "MU_CONSUMERS",
    "ceil_consumers":              "CEIL_CONSUMERS",
    "ass_consumers":               "ASS_CONSUMERS",
    "prov_consumers":              "PROV_CONSUMERS",
    "billtype_prov_consumers":     "BILLTYPE_PROV_CONSUMERS",
    "rdf_consumers":               "RDF_CONSUMERS",
    "idf_consumers":               "IDF_CONSUMERS",
    "tdmr_consumers":              "TDMR_CONSUMERS",
    "unmetered_consumers":         "UNMETERED_CONSUMERS",
    "govt_lmv4_consumers":         "GOVT_LMV4_HV1_CONSUMERS",
    "govt_lmv4_load_kw":           "GOVT_LMV4_HV1_LOAD_KW",
    "govt_lmv4_units_kwh":         "GOVT_LMV4_HV1_UNITS_KWH",
    "govt_lmv4_assessment":        "GOVT_LMV4_HV1_ASSESSMENT",
    "govt_lmv4_revenue":           "GOVT_LMV4_HV1_REVENUE",
    "ptw_load_kw":                 "PTW_LOAD_KW",
    "ptw_units_kwh":               "PTW_CONSUMERS_UNITS_KWH",
    "ptw_assessment":              "PTW_CONSUMERS_ASSESSMENT",
    "qb_consumers":                "QB_CONSUMERS",
}
