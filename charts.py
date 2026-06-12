"""
charts.py — All Plotly chart functions for DVVNL Analytics Dashboard
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from config import COLOR_PALETTE, KPI_THRESHOLDS


# ── SHARED BASE LAYOUT ───────────────────────────────────────────────────────
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
        colorway=COLOR_PALETTE,
    )
    base.update(kwargs)
    return base


def atc_color(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "#64748b"
    if v < KPI_THRESHOLDS["atc_good"]:  return "#22c55e"
    if v < KPI_THRESHOLDS["atc_ok"]:    return "#eab308"
    if v < KPI_THRESHOLDS["atc_high"]:  return "#f97316"
    return "#ef4444"


# ── 1. AT&C GAUGE HORIZONTAL BAR CHART ───────────────────────────────────────
def chart_atc_gauge_bars(df: pd.DataFrame) -> go.Figure:
    """Horizontal gauge-style bar chart, one row per feeder."""
    if df.empty or "atc_loss_pct" not in df.columns:
        return go.Figure()

    colors = [atc_color(v) for v in df["atc_loss_pct"]]
    labels = [f"{row.get('outgoing_feeder','?')} ({row.get('zone','?')})"
              for _, row in df.iterrows()]

    fig = go.Figure(go.Bar(
        y=labels,
        x=df["atc_loss_pct"],
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=df["atc_loss_pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        textfont=dict(size=10, color="#0f172a"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "AT&C Loss: %{x:.1f}%<br>"
            "<extra></extra>"
        )
    ))

    # Reference lines
    for x_val, label, color in [
        (KPI_THRESHOLDS["atc_good"], "Target 15%", "#22c55e"),
        (KPI_THRESHOLDS["atc_ok"],   "Warning 25%","#eab308"),
        (KPI_THRESHOLDS["atc_high"], "Alert 40%",  "#ef4444"),
    ]:
        fig.add_vline(x=x_val, line_dash="dash", line_color=color, opacity=0.6,
                      annotation_text=label, annotation_font_color=color,
                      annotation_font_size=10)

    fig.update_layout(
        **dark_layout(
            height=max(400, len(df) * 28),
            xaxis_title="AT&C Loss %",
            xaxis_range=[0, max(df["atc_loss_pct"].max() * 1.15, 60)],
            showlegend=False,
        )
    )
    return fig


# ── 2. ZONE RADAR CHART ───────────────────────────────────────────────────────
def chart_zone_radar(zone_df: pd.DataFrame) -> go.Figure:
    """Spider/radar chart comparing zones across KPIs."""
    if zone_df.empty:
        return go.Figure()

    metrics = ["billing_efficiency_pct", "collection_efficiency_pct",
               "line_loss_pct", "atc_loss_pct"]
    metric_labels = ["Billing Eff %", "Collection Eff %", "Line Loss %", "AT&C Loss %"]

    # Normalize to 0–100 (invert loss metrics so higher = better)
    fig = go.Figure()
    for i, row in zone_df.iterrows():
        values = []
        for m in metrics:
            v = row.get(m, 0) or 0
            if "loss" in m:
                values.append(max(0, 100 - v))  # invert
            else:
                values.append(min(100, v))
        values.append(values[0])  # close the polygon

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=metric_labels + [metric_labels[0]],
            fill="toself",
            name=row.get("zone", f"Zone {i}"),
            line_color=COLOR_PALETTE[i % len(COLOR_PALETTE)],
            fillcolor=COLOR_PALETTE[i % len(COLOR_PALETTE)],
            opacity=0.25,
            hovertemplate=f"<b>{row.get('zone','')}</b><br>%{{theta}}: %{{r:.1f}}<extra></extra>"
        ))

    fig.update_layout(
        paper_bgcolor="#eef2ff",
        plot_bgcolor="#eef2ff",
        font=dict(family="'Inter', 'Syne', sans-serif", color="#0f172a", size=12),
        polar=dict(
            bgcolor="#eef2ff",
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(color="#475569", size=10),
                            gridcolor="#dbeafe"),
            angularaxis=dict(tickfont=dict(color="#0f172a", size=12), gridcolor="#dbeafe")
        ),
        legend=dict(bgcolor="#eef2ff", bordercolor="#c7d2fe", font=dict(color="#0f172a", size=12)),
        margin=dict(l=40, r=40, t=40, b=40),
    )
    return fig


# ── 3. TREEMAP — AT&C ─────────────────────────────────────────────────────────
def chart_treemap_atc(df: pd.DataFrame) -> go.Figure:
    """Treemap: box size = input energy, color = AT&C loss %."""
    if df.empty:
        return go.Figure()

    req = ["outgoing_feeder", "input_energy_kwh", "atc_loss_pct"]
    for c in req:
        if c not in df.columns:
            return go.Figure()

    path = []
    if "zone" in df.columns:   path.append("zone")
    if "circle" in df.columns: path.append("circle")
    path.append("outgoing_feeder")

    fig = px.treemap(
        df,
        path=path,
        values="input_energy_kwh",
        color="atc_loss_pct",
        color_continuous_scale=[
            [0.0,  "#22c55e"],
            [0.25, "#eab308"],
            [0.5,  "#f97316"],
            [1.0,  "#ef4444"],
        ],
        color_continuous_midpoint=25,
        hover_data=["billing_efficiency_pct", "collection_efficiency_pct",
                    "line_loss_pct"] if all(c in df.columns for c in
                    ["billing_efficiency_pct","collection_efficiency_pct","line_loss_pct"]) else None,
        custom_data=["atc_loss_pct"] if "atc_loss_pct" in df.columns else None,
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>AT&C: %{color:.1f}%",
        textfont_size=12,
        marker_line_width=2,
        marker_line_color="#eef2ff",
    )
    fig.update_layout(
    paper_bgcolor="#eef2ff",
    margin=dict(l=10, r=10, t=20, b=10),
    height=450,
    coloraxis_colorbar=dict(
        title=dict(
            text="AT&C %",
            font=dict(
                color="#0f172a",
                size=12
            )
        ),
        tickfont=dict(
            color="#0f172a",
            size=11
        ),
        bgcolor="#eef2ff",
        outlinecolor="#c7d2fe",
    )
)
    return fig


# ── 4. TREEMAP — REVENUE ──────────────────────────────────────────────────────
def chart_treemap_revenue(df: pd.DataFrame) -> go.Figure:
    """Treemap: box size = revenue, color = collection efficiency %."""
    if df.empty or "revenue_realized" not in df.columns:
        return go.Figure()

    path = []
    if "zone" in df.columns: path.append("zone")
    path.append("outgoing_feeder")

    fig = px.treemap(
        df, path=path, values="revenue_realized",
        color="collection_efficiency_pct" if "collection_efficiency_pct" in df.columns else "revenue_realized",
        color_continuous_scale=[[0,"#ef4444"],[0.5,"#eab308"],[1,"#22c55e"]],
        color_continuous_midpoint=80,
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>CE: %{color:.1f}%",
        textfont_size=12,
        marker_line_width=2,
        marker_line_color="#eef2ff",
    )
    fig.update_layout(
        paper_bgcolor="#eef2ff",
        margin=dict(l=10, r=10, t=20, b=10),
        height=350,
    )
    return fig


# ── 5. SCATTER MATRIX ─────────────────────────────────────────────────────────
def chart_scatter_matrix(df: pd.DataFrame) -> go.Figure:
    """Plotly scatter matrix (splom) across key numeric KPIs."""
    if df.empty:
        return go.Figure()

    dims = ["line_loss_pct","billing_efficiency_pct","collection_efficiency_pct","atc_loss_pct"]
    dims = [d for d in dims if d in df.columns]
    if len(dims) < 2:
        return go.Figure()

    fig = px.scatter_matrix(
        df, dimensions=dims,
        color="atc_loss_pct" if "atc_loss_pct" in df.columns else dims[0],
        color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
        hover_name="outgoing_feeder" if "outgoing_feeder" in df.columns else None,
    )
    fig.update_traces(diagonal_visible=False, showupperhalf=False, marker_size=5)
    fig.update_layout(**dark_layout(height=500, showlegend=False))
    return fig


# ── 6. ENERGY SANKEY ─────────────────────────────────────────────────────────
def chart_energy_sankey(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()

    total_input = float(df.get("input_energy_kwh", pd.Series([0])).fillna(0).sum())
    total_sold = float(df.get("sold_energy_kwh", pd.Series([0])).fillna(0).sum())

    total_line_loss = max(0, total_input - total_sold)

    total_assess = float(df.get("net_assessment", pd.Series([0])).fillna(0).sum())
    total_revenue = float(df.get("revenue_realized", pd.Series([0])).fillna(0).sum())

    unrealized = max(0, total_assess - total_revenue)

    fig = go.Figure(
        go.Sankey(
            node=dict(
                label=[
                    "Input Energy",
                    "Sold Energy",
                    "Line Loss",
                    "Revenue Collected",
                    "Unrealized Revenue"
                ],
                color=[
                    "#6366f1",
                    "#22c55e",
                    "#ef4444",
                    "#06b6d4",
                    "#f97316"
                ],
                pad=20,
                thickness=30,
                line=dict(color="#cbd5e1", width=1)
            ),
            link=dict(
                source=[0, 0, 1, 1],
                target=[1, 2, 3, 4],
                value=[
                    total_sold,
                    total_line_loss,
                    total_revenue,
                    unrealized
                ],
                color=[
                    "rgba(34,197,94,0.3)",
                    "rgba(239,68,68,0.3)",
                    "rgba(6,182,212,0.3)",
                    "rgba(249,115,22,0.3)"
                ]
            )
        )
    )

    fig.update_layout(
        paper_bgcolor="#eef2ff",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20)
    )

    return fig


# ── 7. PERFORMANCE HEATMAP ────────────────────────────────────────────────────
def chart_performance_heatmap(df: pd.DataFrame) -> go.Figure:
    """Multi-KPI heatmap: rows=feeders, cols=KPIs."""
    if df.empty:
        return go.Figure()

    kpi_cols = {
        "atc_loss_pct":              "AT&C Loss %",
        "billing_efficiency_pct":    "Billing Eff %",
        "collection_efficiency_pct": "Collection Eff %",
        "line_loss_pct":             "Line Loss %",
    }
    avail = {k: v for k, v in kpi_cols.items() if k in df.columns}
    if not avail:
        return go.Figure()

    feeder_col = "outgoing_feeder" if "outgoing_feeder" in df.columns else df.columns[0]
    y_labels = df[feeder_col].tolist()

    # Build z matrix: invert loss columns so green = good everywhere
    z_matrix = []
    col_labels = []
    for col, label in avail.items():
        vals = df[col].fillna(0).tolist()
        if "loss" in col:
            normed = [max(0, min(100, 100 - v)) for v in vals]
        else:
            normed = [max(0, min(100, v)) for v in vals]
        z_matrix.append(normed)
        col_labels.append(label)

    fig = go.Figure(go.Heatmap(
        z=list(zip(*z_matrix)),   # transpose
        x=col_labels,
        y=y_labels,
        colorscale=[[0,"#ef4444"],[0.5,"#eab308"],[1,"#22c55e"]],
        zmin=0, zmax=100,
        hoverongaps=False,
        hovertemplate="Feeder: %{y}<br>KPI: %{x}<br>Score: %{z:.1f}<extra></extra>",
        xgap=2, ygap=1,
    ))
    fig.update_layout(
        **dark_layout(
            height=max(400, len(df) * 22),
            title="Performance Score Matrix (100 = Best)",
            title_font_color="#0f172a",
        )
    )
    return fig


# ── 8. CONSUMER FUNNEL ────────────────────────────────────────────────────────
def chart_funnel(funnel_data: dict) -> go.Figure:
    """Funnel chart: Total → Billed → Paid consumers."""
    if not funnel_data:
        return go.Figure()

    stages = list(funnel_data.keys())
    values = list(funnel_data.values())
    colors = ["#6366f1","#22c55e","#06b6d4"]

    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent initial",
        marker=dict(color=colors, line=dict(width=2, color="#eef2ff")),
        connector=dict(line=dict(color="#cbd5e1", width=3, dash="dot")),
        textfont=dict(family="'Inter', 'Syne', sans-serif", size=14, color="#0f172a"),
    ))
    fig.update_layout(
        paper_bgcolor="#eef2ff",
        plot_bgcolor="#eef2ff",
        font=dict(family="'Inter', 'Syne', sans-serif", color="#0f172a", size=13),
        margin=dict(l=150, r=40, t=30, b=20),
        height=300,
    )
    return fig


# ── 9. LOSS HISTOGRAM ─────────────────────────────────────────────────────────
def chart_loss_histogram(hist_df: pd.DataFrame) -> go.Figure:
    """Bar chart showing feeder count distribution by AT&C loss bucket."""
    if hist_df.empty:
        return go.Figure()

    bucket_colors = {
        "< 10%":         "#22c55e",
        "10–15%":        "#4ade80",
        "15–25%":        "#eab308",
        "25–40%":        "#f97316",
        "40–60%":        "#ef4444",
        "> 60%":         "#7f1d1d",
        "Negative (Error)": "#64748b",
    }
    colors = [bucket_colors.get(b, "#64748b") for b in hist_df.get("atc_bucket", [])]

    fig = go.Figure(go.Bar(
        x=hist_df.get("atc_bucket", []),
        y=hist_df.get("feeder_count", []),
        marker_color=colors,
        marker_line_width=0,
        text=hist_df.get("feeder_count", []),
        textposition="outside",
        textfont=dict(color="#e2e8f0"),
        hovertemplate="<b>%{x}</b><br>Feeders: %{y}<extra></extra>",
    ))
    fig.update_layout(
        **dark_layout(
            xaxis_title="AT&C Loss Range",
            yaxis_title="Number of Feeders",
            showlegend=False,
        )
    )
    return fig


# ── 10. WATERFALL DECOMPOSITION ───────────────────────────────────────────────
def chart_waterfall_decomposition(df: pd.DataFrame) -> go.Figure:
    """Stacked bar: Line Loss component + Collection Loss component = AT&C."""
    if df.empty or "atc_loss_pct" not in df.columns or "line_loss_pct" not in df.columns:
        return go.Figure()

    df2 = df.copy()
    df2["coll_loss_component"] = (df2["atc_loss_pct"] - df2["line_loss_pct"]).clip(lower=0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Line Loss Component",
        x=df2.get("outgoing_feeder", df2.index),
        y=df2["line_loss_pct"],
        marker_color="#f97316",
        hovertemplate="<b>%{x}</b><br>Line Loss: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Collection Loss Component",
        x=df2.get("outgoing_feeder", df2.index),
        y=df2["coll_loss_component"],
        marker_color="#ef4444",
        hovertemplate="<b>%{x}</b><br>Coll Loss: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **dark_layout(
            barmode="stack",
            xaxis_tickangle=-45,
            yaxis_title="AT&C Loss %",
        )
    )
    return fig
