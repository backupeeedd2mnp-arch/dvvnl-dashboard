# ⚡ DVVNL Feeder-wise AT&C Loss Analytics Dashboard

**Dakshinanchal Vidyut Vitran Nigam Limited**  
Powered by: **DuckDB + Streamlit + Plotly**

---

## 📁 File Structure

```
dvvnl_dashboard/
├── app.py               ← Main Streamlit app (run this)
├── config.py            ← ⚠️ EDIT THIS: DB path & table names
├── queries.py           ← All DuckDB SQL queries
├── charts.py            ← All Plotly chart functions
├── requirements.txt     ← Python dependencies
├── START_DASHBOARD.bat  ← Windows one-click launcher
└── README.md
```

---

## ⚙️ STEP 1: Edit config.py

Open `config.py` and set your DuckDB file path:

```python
DB_PATH = "C:/Users/YourName/Documents/dvvnl.duckdb"
```

Also verify table names match your DuckDB:
```python
ENERGY_TABLE  = "DVVNL_ENERGY_APRIL26"   # your energy table
BILLING_TABLE = "DVVNL_MASTER_APRIL26"   # your billing table
```

---

## 📦 STEP 2: Install Dependencies

Open Command Prompt in this folder and run:

```cmd
pip install -r requirements.txt
```

Or on Snapdragon/ARM Windows:
```cmd
pip install streamlit plotly duckdb pandas openpyxl
```

---

## 🚀 STEP 3: Run the Dashboard

**Option A: Double-click `START_DASHBOARD.bat`**

**Option B: Command line:**
```cmd
cd dvvnl_dashboard
streamlit run app.py
```
 ** python -m streamlit run app.py   **
Then opeet_prop(prop, value)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5276, in _set_prop
    raise err
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5271, in _set_prop
    val = validator.validate_coerce(val)
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 796, in validate_coerce
    self.raise_invalid_elements(some_invalid_els)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 328, in raise_invalid_elements
                raise ValueError(
    ...<10 lines>...
                )
ValueError: 
    Invalid element(s) received for the 'size' property of scattergl.marker
        Invalid elements include: [nan, nan, nan, nan]

    The 'size' property is a number and may be specified as:
      - An int or float in the interval [0, inf]
      - A tuple, list, or one-dimensional numpy array of the above
2026-06-02 14:01:00.733 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:00.779 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:00.819 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:00.868 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:00.889 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:01.279 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:01:01.310 Uncaught app execution
Traceback (most recent call last):
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 129, in exec_func_with_error_handling
    result = func()
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 789, in code_to_exec
    exec(code, module.__dict__)  # noqa: S102
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dashbaord feeder\app.py", line 360, in <module>
    fig = px.scatter(df, x="billing_efficiency_pct", y="atc_loss_pct",
                     color="atc_loss_pct", size="input_energy_kwh",
                     color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                     hover_name="outgoing_feeder", hover_data=["zone","collection_efficiency_pct"])
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\express\_chart_types.py", line 69, in scatter
    return make_figure(args=locals(), constructor=go.Scatter)
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\express\_core.py", line 2706, in make_figure
    trace.update(patch)
    ~~~~~~~~~~~~^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5197, in update
    BaseFigure._perform_update(self, dict1, overwrite=overwrite)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 3971, in _perform_update
    BaseFigure._perform_update(plotly_obj[key], val)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 3992, in _perform_update
    plotly_obj[key] = val
    ~~~~~~~~~~^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 4932, in __setitem__
    self._set_prop(prop, value)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5276, in _set_prop
    raise err
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5271, in _set_prop
    val = validator.validate_coerce(val)
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 796, in validate_coerce
    self.raise_invalid_elements(some_invalid_els)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 328, in raise_invalid_elements
                raise ValueError(
    ...<10 lines>...
                )
ValueError: 
    Invalid element(s) received for the 'size' property of scattergl.marker
        Invalid elements include: [nan, nan, nan, nan]

    The 'size' property is a number and may be specified as:
      - An int or float in the interval [0, inf]
      - A tuple, list, or one-dimensional numpy array of the above
2026-06-02 14:56:06.622 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:56:06.671 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:56:06.710 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:56:06.752 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:56:07.154 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `width="stretch"`, use `width='stretch'`. For `width="content"`, use `width='content'`.
2026-06-02 14:56:07.184 Uncaught app execution
Traceback (most recent call last):
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 129, in exec_func_with_error_handling
    result = func()
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 789, in code_to_exec
    exec(code, module.__dict__)  # noqa: S102
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dashbaord feeder\app.py", line 360, in <module>
    fig = px.scatter(df, x="billing_efficiency_pct", y="atc_loss_pct",
                     color="atc_loss_pct", size="input_energy_kwh",
                     color_continuous_scale=[[0,"#22c55e"],[0.5,"#f97316"],[1,"#ef4444"]],
                     hover_name="outgoing_feeder", hover_data=["zone","collection_efficiency_pct"])
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\express\_chart_types.py", line 69, in scatter
    return make_figure(args=locals(), constructor=go.Scatter)
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\express\_core.py", line 2706, in make_figure
    trace.update(patch)
    ~~~~~~~~~~~~^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5197, in update
    BaseFigure._perform_update(self, dict1, overwrite=overwrite)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 3971, in _perform_update
    BaseFigure._perform_update(plotly_obj[key], val)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 3992, in _perform_update
    plotly_obj[key] = val
    ~~~~~~~~~~^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 4932, in __setitem__
    self._set_prop(prop, value)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5276, in _set_prop
    raise err
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\plotly\basedatatypes.py", line 5271, in _set_prop
    val = validator.validate_coerce(val)
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 796, in validate_coerce
    self.raise_invalid_elements(some_invalid_els)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "C:\Users\ksas2\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\_plotly_utils\basevalidators.py", line 328, in raise_invalid_elements
                raise ValueError(
    ...<10 lines>...
                )
ValueError: 
    Invalid element(s) received for the 'size' property of scattergl.marker
        Invalid elements include: [nan, nan, nan, nan]

    The 'size' property is a number and may be specified as:
      - An int or float in the interval [0, inf]
      - A tuple, list, or one-dimensional numpy array of the above
n browser at: **http://localhost:8501**

---

## 📊 Dashboard Features (10 Tabs)

| Tab | Description |
|-----|-------------|
| 📊 Overview | AT&C bar, zone KPI compare, energy vs sold, nature pie, revenue gap |
| 🔴 AT&C Deep Dive | Gauge bars all feeders, BE×CE scatter, waterfall decomposition |
| ⚡ Energy Analysis | Zone area chart, line loss histogram, feeder energy ranking |
| 💰 Revenue & Collection | Gap chart, CE bars, ABR vs ACR, consumer funnel |
| 🏆 Feeder Rankings | Best/Worst N feeders, sortable KPI ranking table |
| 🗺️ Zone Comparison | Radar chart, circle bubble chart, heatmap table |
| 🔵 Scatter Analysis | 6 scatter plots across all KPI combinations |
| 🟦 Performance Matrix | Correlation heatmap, performance score matrix, feeder drill-down |
| 🌳 Treemap Views | Energy×AT&C, Revenue×CE, Zone→Circle→Feeder hierarchy |
| 📋 Data Table | Searchable, column-selector, CSV+Excel download |

---

## 🔢 KPI Formulas Used

| KPI | Formula |
|-----|---------|
| Input Energy | SUM(Total Energy) or Assessed if meter not OK |
| Sold Energy | SUM(CONSUMPTION_CURR_MNTH) — INF_BILL estimated as LOAD×140 |
| Line Loss % | (Input − Sold) / Input × 100 |
| Billing Efficiency % | Sold / Input × 100 |
| Collection Efficiency % | Revenue / Assessment × 100 |
| **AT&C Loss %** | **[1 − (BE × CE)] × 100** |
| ABR (₹/KWH) | Assessment / Sold Energy |
| Avg Collection Rate | Revenue / Sold Energy |

---

## 🎛️ Sidebar Filters

- **Billing Period**: Date range picker (default April 2026)
- **Zone**: Filter by DVVNL zone
- **Division/SDO**: Filter by billing division
- **Feeder Type**: Urban / Semi-Urban / Rural
- **Sort By**: Any KPI column
- **Refresh**: Clear cache and reload from DB

---

## ⚠️ Troubleshooting

| Issue | Fix |
|-------|-----|
| DB connection error | Check `DB_PATH` in `config.py` |
| Table not found | Verify table names in DuckDB Shell: `SHOW TABLES;` |
| Column mismatch | Update `ENERGY_COLS` / `BILLING_COLS` maps in `config.py` |
| Slow loading | First load is slow (data cached for 5 min after) |
| Port in use | Run: `streamlit run app.py --server.port 8502` |

---

## 🐍 Quick Test in DuckDB Shell

```sql
-- Verify your tables exist
SHOW TABLES;

-- Check energy table columns  
DESCRIBE DVVNL_ENERGY_APRIL26;

-- Check billing table columns
DESCRIBE DVVNL_MASTER_APRIL26;

-- Quick row count
SELECT COUNT(*) FROM DVVNL_ENERGY_APRIL26;
SELECT COUNT(*) FROM DVVNL_MASTER_APRIL26;
```

---

## 📞 Export Options

- **CSV**: Download filtered feeder KPI data
- **Excel**: Full formatted workbook
- **Unmatched Feeders**: List of energy feeders with no billing match

---

*Built for DVVNL | April 2026 | DuckDB + Streamlit + Plotly*
