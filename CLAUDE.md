# CLAUDE CODE EXECUTION GUIDE
## Snowflake Cost Analyzer — Complete Build Instructions

> **For Claude Code:** Read this entire file before writing any code. Execute phases in order.
> Each phase has a verification step — do not proceed to the next phase until it passes.
> All files are listed with their exact path and complete content.

---

## Project Context

Build a multi-page **Streamlit in Snowflake (SiS)** application called **Snowflake Cost Analyzer**.
The app reads from `SNOWFLAKE.ACCOUNT_USAGE` views, renders interactive dashboards with Altair charts,
and generates AI-powered insights using `SNOWFLAKE.CORTEX.COMPLETE`. It will be packaged as a
Snowflake Native App for Marketplace distribution.

**Hard deadline:** Snowflake Marketplace submission on June 10, 2026.

---

## Prerequisites (Verify Before Starting)

- Snowflake account with ACCOUNTADMIN access available
- `SNOWFLAKE.ACCOUNT_USAGE` schema accessible (requires Enterprise Edition or higher for full feature set)
- Snowflake CLI installed: `snow --version` should return a version
- Python 3.11+ installed

---

## Repository Structure to Create

```
snowflake-cost-analyzer/
├── CLAUDE.md                         ← this file
├── environment.yml
├── streamlit_app.py
├── pages/
│   ├── 01_Overview.py
│   ├── 02_Warehouse_Analysis.py
│   ├── 03_Query_Intelligence.py
│   ├── 04_User_Analysis.py
│   └── 05_Storage.py
├── utils/
│   ├── __init__.py
│   ├── queries.py
│   ├── charts.py
│   └── ai_insights.py
└── deploy/
    ├── setup.sql
    └── native_app/
        ├── manifest.yml
        └── setup.sql
```

---

## PHASE 1 — Core Configuration Files

### File: `environment.yml`

```yaml
name: sf-env
channels:
  - snowflake
dependencies:
  - streamlit
  - altair
  - pandas
  - snowflake-snowpark-python
```

---

## PHASE 2 — Utility Modules

### File: `utils/__init__.py`

```python
```

*(empty file — makes utils a package)*

---

### File: `utils/queries.py`

```python
"""
All data-fetch functions for Snowflake Cost Analyzer.
Each function accepts a Snowpark Session and date range strings (YYYY-MM-DD).
The _session parameter prefix tells st.cache_data to skip it during cache key hashing.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from snowflake.snowpark import Session


# ---------------------------------------------------------------------------
# Overview / Metering
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_credits(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """Daily credits by service type from METERING_DAILY_HISTORY."""
    return _session.sql("""
        SELECT
            USAGE_DATE,
            SERVICE_TYPE,
            SUM(CREDITS_USED)    AS CREDITS_USED,
            SUM(CREDITS_BILLED)  AS CREDITS_BILLED,
            SUM(CREDITS_ADJUSTMENT_CLOUD_SERVICES) AS CREDITS_ADJUSTMENT
        FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
        WHERE USAGE_DATE BETWEEN ? AND ?
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, params=[date_from, date_to]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_period_comparison(_session: Session, date_from: str, date_to: str) -> dict:
    """
    Returns total billed credits for the current period and an equal-length prior period.
    Used for MoM or period-over-period KPI cards.
    """
    result = _session.sql("""
        WITH current_period AS (
            SELECT SUM(CREDITS_BILLED) AS total
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE USAGE_DATE BETWEEN ? AND ?
        ),
        prior_period AS (
            SELECT SUM(CREDITS_BILLED) AS total
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE USAGE_DATE BETWEEN
                DATEADD('day', -DATEDIFF('day', ?, ?), ?)
                AND DATEADD('day', -1, ?)
        )
        SELECT
            COALESCE(c.total, 0) AS current_total,
            COALESCE(p.total, 0) AS prior_total
        FROM current_period c, prior_period p
    """, params=[
        date_from, date_to,
        date_from, date_to, date_from,
        date_from
    ]).collect()

    row = result[0]
    current = float(row[0]) if row[0] else 0.0
    prior   = float(row[1]) if row[1] else 0.0
    return {"current": current, "prior": prior}


@st.cache_data(ttl=1800, show_spinner=False)
def get_service_type_totals(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """Total billed credits per service type for the period (donut chart data)."""
    return _session.sql("""
        SELECT
            SERVICE_TYPE,
            SUM(CREDITS_BILLED) AS CREDITS_BILLED
        FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
        WHERE USAGE_DATE BETWEEN ? AND ?
        GROUP BY 1
        ORDER BY 2 DESC
    """, params=[date_from, date_to]).to_pandas()


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_warehouse_summary(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Per-warehouse credit summary including idle time calculation.
    Idle credits = credits_used_compute - credits_attributed_compute_queries
    """
    return _session.sql("""
        SELECT
            WAREHOUSE_NAME,
            SUM(CREDITS_USED_COMPUTE)                    AS COMPUTE_CREDITS,
            SUM(CREDITS_USED_CLOUD_SERVICES)             AS CLOUD_SERVICE_CREDITS,
            SUM(CREDITS_USED)                            AS TOTAL_CREDITS,
            SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES)      AS QUERY_CREDITS,
            SUM(CREDITS_USED_COMPUTE)
                - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES) AS IDLE_CREDITS,
            ROUND(
                ZEROIFNULL(
                    (SUM(CREDITS_USED_COMPUTE) - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES))
                    / NULLIF(SUM(CREDITS_USED_COMPUTE), 0)
                ) * 100, 1
            ) AS IDLE_PCT
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE DATE(START_TIME) BETWEEN ? AND ?
        GROUP BY 1
        ORDER BY 3 DESC
    """, params=[date_from, date_to]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_warehouse_daily_trend(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """Daily credit trend per warehouse (for multi-line chart)."""
    return _session.sql("""
        SELECT
            DATE(START_TIME)          AS USAGE_DATE,
            WAREHOUSE_NAME,
            SUM(CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
            SUM(CREDITS_USED)         AS TOTAL_CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE DATE(START_TIME) BETWEEN ? AND ?
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, params=[date_from, date_to]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_warehouse_sizing_signals(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Combines warehouse metering with query history to produce sizing signals.
    Signals: OVERLOADED (high queue), OVER_PROVISIONED (high idle), BALANCED.
    """
    return _session.sql("""
        WITH wh_stats AS (
            SELECT
                WAREHOUSE_NAME,
                SUM(CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
                SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES) AS QUERY_CREDITS,
                ROUND(
                    ZEROIFNULL(
                        (SUM(CREDITS_USED_COMPUTE) - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES))
                        / NULLIF(SUM(CREDITS_USED_COMPUTE), 0)
                    ) * 100, 1
                ) AS IDLE_PCT
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE DATE(START_TIME) BETWEEN ? AND ?
            GROUP BY 1
        ),
        qh_stats AS (
            SELECT
                WAREHOUSE_NAME,
                WAREHOUSE_SIZE,
                COUNT(*) AS QUERY_COUNT,
                AVG(TOTAL_ELAPSED_TIME) AS AVG_ELAPSED_MS,
                SUM(QUEUED_OVERLOAD_TIME) AS TOTAL_QUEUED_MS,
                SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) AS TOTAL_REMOTE_SPILL
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME BETWEEN ? AND ?
              AND EXECUTION_STATUS = 'SUCCESS'
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT
            w.WAREHOUSE_NAME,
            q.WAREHOUSE_SIZE,
            w.COMPUTE_CREDITS,
            w.IDLE_PCT,
            q.QUERY_COUNT,
            ROUND(q.AVG_ELAPSED_MS / 1000, 1) AS AVG_ELAPSED_SEC,
            ROUND(q.TOTAL_QUEUED_MS / NULLIF(q.QUERY_COUNT * q.AVG_ELAPSED_MS, 0) * 100, 1) AS QUEUE_PCT,
            q.TOTAL_REMOTE_SPILL,
            CASE
                WHEN q.TOTAL_QUEUED_MS > (q.QUERY_COUNT * q.AVG_ELAPSED_MS * 0.1) THEN 'OVERLOADED'
                WHEN w.IDLE_PCT > 40 THEN 'OVER_PROVISIONED'
                ELSE 'BALANCED'
            END AS SIZING_SIGNAL
        FROM wh_stats w
        LEFT JOIN qh_stats q ON w.WAREHOUSE_NAME = q.WAREHOUSE_NAME
        ORDER BY w.COMPUTE_CREDITS DESC
    """, params=[date_from, date_to, date_from + " 00:00:00", date_to + " 23:59:59"]).to_pandas()


# ---------------------------------------------------------------------------
# Query Intelligence
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_top_queries_by_duration(_session: Session, date_from: str, date_to: str, limit: int = 50) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            QUERY_ID,
            USER_NAME,
            WAREHOUSE_NAME,
            WAREHOUSE_SIZE,
            ROUND(TOTAL_ELAPSED_TIME / 1000, 1)          AS ELAPSED_SEC,
            ROUND(BYTES_SCANNED / POWER(1024, 3), 3)     AS GB_SCANNED,
            ROUND(PERCENTAGE_SCANNED_FROM_CACHE * 100, 1) AS CACHE_HIT_PCT,
            ROUND(BYTES_SPILLED_TO_REMOTE_STORAGE / POWER(1024, 3), 3) AS REMOTE_SPILL_GB,
            CREDITS_USED_CLOUD_SERVICES,
            EXECUTION_STATUS,
            START_TIME,
            LEFT(COALESCE(QUERY_TEXT, '[query text unavailable]'), 500) AS QUERY_PREVIEW
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
          AND WAREHOUSE_NAME IS NOT NULL
        ORDER BY TOTAL_ELAPSED_TIME DESC
        LIMIT ?
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59", limit]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_top_queries_by_bytes(_session: Session, date_from: str, date_to: str, limit: int = 50) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            QUERY_ID,
            USER_NAME,
            WAREHOUSE_NAME,
            WAREHOUSE_SIZE,
            ROUND(BYTES_SCANNED / POWER(1024, 3), 3)      AS GB_SCANNED,
            ROUND(TOTAL_ELAPSED_TIME / 1000, 1)            AS ELAPSED_SEC,
            ROUND(PERCENTAGE_SCANNED_FROM_CACHE * 100, 1)  AS CACHE_HIT_PCT,
            ROUND(BYTES_SPILLED_TO_REMOTE_STORAGE / POWER(1024, 3), 3) AS REMOTE_SPILL_GB,
            START_TIME,
            LEFT(COALESCE(QUERY_TEXT, '[query text unavailable]'), 500) AS QUERY_PREVIEW
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
          AND WAREHOUSE_NAME IS NOT NULL
          AND BYTES_SCANNED > 0
        ORDER BY BYTES_SCANNED DESC
        LIMIT ?
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59", limit]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_spill_queries(_session: Session, date_from: str, date_to: str, limit: int = 50) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            QUERY_ID,
            USER_NAME,
            WAREHOUSE_NAME,
            WAREHOUSE_SIZE,
            ROUND(BYTES_SPILLED_TO_LOCAL_STORAGE / POWER(1024, 3), 3)  AS LOCAL_SPILL_GB,
            ROUND(BYTES_SPILLED_TO_REMOTE_STORAGE / POWER(1024, 3), 3) AS REMOTE_SPILL_GB,
            ROUND(BYTES_SCANNED / POWER(1024, 3), 3)                    AS GB_SCANNED,
            ROUND(TOTAL_ELAPSED_TIME / 1000, 1)                         AS ELAPSED_SEC,
            START_TIME,
            LEFT(COALESCE(QUERY_TEXT, '[query text unavailable]'), 500) AS QUERY_PREVIEW
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
          AND (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0)
        ORDER BY BYTES_SPILLED_TO_REMOTE_STORAGE DESC
        LIMIT ?
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59", limit]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_poor_cache_queries(_session: Session, date_from: str, date_to: str, limit: int = 50) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            QUERY_ID,
            USER_NAME,
            WAREHOUSE_NAME,
            ROUND(PERCENTAGE_SCANNED_FROM_CACHE * 100, 1)  AS CACHE_HIT_PCT,
            ROUND(BYTES_SCANNED / POWER(1024, 3), 3)        AS GB_SCANNED,
            ROUND(TOTAL_ELAPSED_TIME / 1000, 1)             AS ELAPSED_SEC,
            START_TIME,
            LEFT(COALESCE(QUERY_TEXT, '[query text unavailable]'), 500) AS QUERY_PREVIEW
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
          AND BYTES_SCANNED > 1073741824
          AND PERCENTAGE_SCANNED_FROM_CACHE < 0.2
        ORDER BY GB_SCANNED DESC
        LIMIT ?
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59", limit]).to_pandas()


# ---------------------------------------------------------------------------
# User Analysis
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_user_stats(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            USER_NAME,
            COUNT(*)                                              AS QUERY_COUNT,
            ROUND(SUM(TOTAL_ELAPSED_TIME) / 1000 / 3600, 2)     AS TOTAL_ELAPSED_HRS,
            ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000, 1)             AS AVG_ELAPSED_SEC,
            ROUND(SUM(BYTES_SCANNED) / POWER(1024, 3), 2)        AS TOTAL_GB_SCANNED,
            ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POWER(1024, 3), 3) AS TOTAL_SPILL_GB,
            ROUND(AVG(PERCENTAGE_SCANNED_FROM_CACHE) * 100, 1)   AS AVG_CACHE_HIT_PCT,
            COUNT(DISTINCT WAREHOUSE_NAME)                        AS WAREHOUSES_USED,
            MAX(START_TIME)                                       AS LAST_QUERY_TIME
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
          AND USER_NAME IS NOT NULL
        GROUP BY 1
        ORDER BY 2 DESC
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59"]).to_pandas()


@st.cache_data(ttl=1800, show_spinner=False)
def get_user_activity_heatmap(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    """Returns query count by day-of-week and hour-of-day for heatmap."""
    return _session.sql("""
        SELECT
            DAYNAME(START_TIME)           AS DAY_OF_WEEK,
            DATE_PART('hour', START_TIME) AS HOUR_OF_DAY,
            COUNT(*)                      AS QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME BETWEEN ? AND ?
          AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY 1, 2
        ORDER BY 2
    """, params=[date_from + " 00:00:00", date_to + " 23:59:59"]).to_pandas()


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def get_storage_trend(_session: Session, date_from: str, date_to: str) -> pd.DataFrame:
    return _session.sql("""
        SELECT
            USAGE_DATE,
            ROUND(STORAGE_BYTES  / POWER(1024, 4), 4) AS TABLE_TB,
            ROUND(STAGE_BYTES    / POWER(1024, 4), 4) AS STAGE_TB,
            ROUND(FAILSAFE_BYTES / POWER(1024, 4), 4) AS FAILSAFE_TB,
            ROUND((STORAGE_BYTES + STAGE_BYTES + FAILSAFE_BYTES) / POWER(1024, 4), 4) AS TOTAL_TB
        FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
        WHERE USAGE_DATE BETWEEN ? AND ?
        ORDER BY 1
    """, params=[date_from, date_to]).to_pandas()


# ---------------------------------------------------------------------------
# Data Freshness
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_data_freshness(_session: Session) -> dict:
    """Returns the latest data timestamps for each view to display freshness banners."""
    try:
        wh = _session.sql(
            "SELECT MAX(END_TIME) FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY"
        ).collect()[0][0]
        qh = _session.sql(
            "SELECT MAX(END_TIME) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY"
        ).collect()[0][0]
        st = _session.sql(
            "SELECT MAX(USAGE_DATE) FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE"
        ).collect()[0][0]
        return {"warehouse": wh, "queries": qh, "storage": st}
    except Exception:
        return {"warehouse": None, "queries": None, "storage": None}
```

---

### File: `utils/charts.py`

```python
"""
Reusable Altair chart builders for the Snowflake Cost Analyzer.
All functions accept a pandas DataFrame and return an altair.Chart object.
No data fetching happens here — pure presentation layer.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

# Consistent color scheme
SNOWFLAKE_BLUE  = "#29B5E8"
SNOWFLAKE_NAVY  = "#1A3E6B"
COLOR_SCHEME    = "tableau10"


def credit_trend_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Line chart: daily credits by service type.
    Expects columns: USAGE_DATE, SERVICE_TYPE, CREDITS_BILLED
    """
    return (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("USAGE_DATE:T", title="Date", axis=alt.Axis(format="%b %d")),
            y=alt.Y("CREDITS_BILLED:Q", title="Credits Billed"),
            color=alt.Color("SERVICE_TYPE:N", scale=alt.Scale(scheme=COLOR_SCHEME), title="Service Type"),
            tooltip=[
                alt.Tooltip("USAGE_DATE:T", title="Date", format="%b %d %Y"),
                alt.Tooltip("SERVICE_TYPE:N", title="Service"),
                alt.Tooltip("CREDITS_BILLED:Q", title="Credits", format=".3f"),
            ],
        )
        .properties(height=300)
        .interactive()
    )


def service_type_donut(df: pd.DataFrame) -> alt.Chart:
    """
    Donut chart: credits by service type.
    Expects columns: SERVICE_TYPE, CREDITS_BILLED
    """
    return (
        alt.Chart(df)
        .mark_arc(innerRadius=60, outerRadius=120)
        .encode(
            theta=alt.Theta("CREDITS_BILLED:Q"),
            color=alt.Color(
                "SERVICE_TYPE:N",
                scale=alt.Scale(scheme=COLOR_SCHEME),
                title="Service Type",
            ),
            tooltip=[
                alt.Tooltip("SERVICE_TYPE:N", title="Service"),
                alt.Tooltip("CREDITS_BILLED:Q", title="Credits", format=".3f"),
            ],
        )
        .properties(height=280)
    )


def warehouse_bar_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Horizontal bar chart: top warehouses by total credits.
    Expects columns: WAREHOUSE_NAME, COMPUTE_CREDITS, CLOUD_SERVICE_CREDITS
    """
    df_melted = df[["WAREHOUSE_NAME", "COMPUTE_CREDITS", "CLOUD_SERVICE_CREDITS"]].melt(
        id_vars="WAREHOUSE_NAME", var_name="TYPE", value_name="CREDITS"
    )
    return (
        alt.Chart(df_melted)
        .mark_bar()
        .encode(
            x=alt.X("CREDITS:Q", title="Credits Used", stack="zero"),
            y=alt.Y("WAREHOUSE_NAME:N", sort="-x", title="Warehouse"),
            color=alt.Color(
                "TYPE:N",
                scale=alt.Scale(
                    domain=["COMPUTE_CREDITS", "CLOUD_SERVICE_CREDITS"],
                    range=[SNOWFLAKE_BLUE, SNOWFLAKE_NAVY],
                ),
                title="Credit Type",
            ),
            tooltip=[
                alt.Tooltip("WAREHOUSE_NAME:N", title="Warehouse"),
                alt.Tooltip("TYPE:N", title="Type"),
                alt.Tooltip("CREDITS:Q", title="Credits", format=".3f"),
            ],
        )
        .properties(height=max(200, len(df) * 35))
    )


def warehouse_trend_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Multi-line chart: daily compute credits per warehouse.
    Expects columns: USAGE_DATE, WAREHOUSE_NAME, TOTAL_CREDITS
    """
    return (
        alt.Chart(df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("USAGE_DATE:T", title="Date", axis=alt.Axis(format="%b %d")),
            y=alt.Y("TOTAL_CREDITS:Q", title="Credits"),
            color=alt.Color("WAREHOUSE_NAME:N", scale=alt.Scale(scheme=COLOR_SCHEME), title="Warehouse"),
            tooltip=[
                alt.Tooltip("USAGE_DATE:T", title="Date", format="%b %d %Y"),
                alt.Tooltip("WAREHOUSE_NAME:N", title="Warehouse"),
                alt.Tooltip("TOTAL_CREDITS:Q", title="Credits", format=".3f"),
            ],
        )
        .properties(height=300)
        .interactive()
    )


def idle_time_bar_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Horizontal bar showing idle vs. query credits per warehouse.
    Expects columns: WAREHOUSE_NAME, QUERY_CREDITS, IDLE_CREDITS
    """
    df_melted = df[["WAREHOUSE_NAME", "QUERY_CREDITS", "IDLE_CREDITS"]].melt(
        id_vars="WAREHOUSE_NAME", var_name="TYPE", value_name="CREDITS"
    )
    return (
        alt.Chart(df_melted)
        .mark_bar()
        .encode(
            x=alt.X("CREDITS:Q", stack="normalize", title="Credit Distribution", axis=alt.Axis(format="%")),
            y=alt.Y("WAREHOUSE_NAME:N", sort="-x", title="Warehouse"),
            color=alt.Color(
                "TYPE:N",
                scale=alt.Scale(
                    domain=["QUERY_CREDITS", "IDLE_CREDITS"],
                    range=[SNOWFLAKE_BLUE, "#E8726A"],
                ),
                title="Type",
            ),
            tooltip=[
                alt.Tooltip("WAREHOUSE_NAME:N", title="Warehouse"),
                alt.Tooltip("TYPE:N", title="Type"),
                alt.Tooltip("CREDITS:Q", title="Credits", format=".3f"),
            ],
        )
        .properties(height=max(200, len(df) * 35))
    )


def user_bar_chart(df: pd.DataFrame, top_n: int = 15) -> alt.Chart:
    """
    Horizontal bar: top users by query count.
    Expects columns: USER_NAME, QUERY_COUNT, TOTAL_GB_SCANNED
    """
    top_df = df.head(top_n).copy()
    return (
        alt.Chart(top_df)
        .mark_bar(color=SNOWFLAKE_BLUE)
        .encode(
            x=alt.X("QUERY_COUNT:Q", title="Query Count"),
            y=alt.Y("USER_NAME:N", sort="-x", title="User"),
            tooltip=[
                alt.Tooltip("USER_NAME:N", title="User"),
                alt.Tooltip("QUERY_COUNT:Q", title="Queries"),
                alt.Tooltip("TOTAL_GB_SCANNED:Q", title="GB Scanned", format=".2f"),
                alt.Tooltip("AVG_ELAPSED_SEC:Q", title="Avg Elapsed (s)", format=".1f"),
            ],
        )
        .properties(height=max(200, top_n * 30))
    )


def user_heatmap_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Heatmap: query activity by day-of-week and hour-of-day.
    Expects columns: DAY_OF_WEEK, HOUR_OF_DAY, QUERY_COUNT
    """
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return (
        alt.Chart(df)
        .mark_rect(stroke="white", strokeWidth=1)
        .encode(
            x=alt.X("HOUR_OF_DAY:O", title="Hour of Day (UTC)"),
            y=alt.Y("DAY_OF_WEEK:O", sort=day_order, title="Day of Week"),
            color=alt.Color(
                "QUERY_COUNT:Q",
                scale=alt.Scale(scheme="blues"),
                title="Query Count",
            ),
            tooltip=[
                alt.Tooltip("DAY_OF_WEEK:O", title="Day"),
                alt.Tooltip("HOUR_OF_DAY:O", title="Hour"),
                alt.Tooltip("QUERY_COUNT:Q", title="Queries"),
            ],
        )
        .properties(height=220)
    )


def storage_area_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Stacked area chart: storage breakdown over time.
    Expects columns: USAGE_DATE, TABLE_TB, STAGE_TB, FAILSAFE_TB
    """
    df_melted = df[["USAGE_DATE", "TABLE_TB", "STAGE_TB", "FAILSAFE_TB"]].melt(
        id_vars="USAGE_DATE", var_name="TYPE", value_name="TB"
    )
    label_map = {"TABLE_TB": "Table", "STAGE_TB": "Stage", "FAILSAFE_TB": "Fail-safe"}
    df_melted["TYPE_LABEL"] = df_melted["TYPE"].map(label_map)

    return (
        alt.Chart(df_melted)
        .mark_area(opacity=0.8)
        .encode(
            x=alt.X("USAGE_DATE:T", title="Date", axis=alt.Axis(format="%b %d")),
            y=alt.Y("TB:Q", stack="zero", title="Storage (TB)"),
            color=alt.Color(
                "TYPE_LABEL:N",
                scale=alt.Scale(scheme=COLOR_SCHEME),
                title="Storage Type",
            ),
            tooltip=[
                alt.Tooltip("USAGE_DATE:T", title="Date", format="%b %d %Y"),
                alt.Tooltip("TYPE_LABEL:N", title="Type"),
                alt.Tooltip("TB:Q", title="TB", format=".4f"),
            ],
        )
        .properties(height=280)
        .interactive()
    )
```

---

### File: `utils/ai_insights.py`

```python
"""
Snowflake Cortex AI integration for the Cost Analyzer.

Security note: Raw QUERY_TEXT from QUERY_HISTORY is NEVER passed to Cortex.
Only pre-aggregated statistics are sent to prevent prompt injection from
maliciously crafted SQL stored in query history.
"""
from __future__ import annotations

import streamlit as st
from snowflake.snowpark import Session


def detect_cortex(_session: Session) -> bool:
    """
    Detects whether Cortex is available in this account/region.
    Runs a minimal completion call to confirm access.
    Result is cached in session state after first check.
    """
    try:
        _session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', 'Reply OK') AS R"
        ).collect()
        return True
    except Exception:
        return False


def generate_insight(
    _session: Session,
    page: str,
    context: dict,
    model: str = "mistral-large2",
) -> str:
    """
    Generates an AI insight for the given page using Cortex.
    Falls back to rule_based_insight() if Cortex is unavailable.

    Args:
        _session:  Active Snowpark session
        page:      Page identifier: 'overview' | 'warehouse' | 'query' | 'user' | 'storage'
        context:   Pre-aggregated statistics dict (no raw SQL text)
        model:     Cortex model name

    Returns:
        Insight text string (plain text, no markdown headers)
    """
    if not st.session_state.get("cortex_available", False):
        return rule_based_insight(page, context)

    prompt = _build_prompt(page, context)
    try:
        result = _session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS INSIGHT",
            params=[model, prompt],
        ).collect()
        raw = result[0][0] if result else ""
        return raw.strip() if raw else rule_based_insight(page, context)
    except Exception:
        return rule_based_insight(page, context)


def generate_query_tip(
    _session: Session,
    query_stats: dict,
    model: str = "mistral-large2",
) -> str:
    """
    Generates a single optimization tip for one query based on its stats.
    NEVER includes raw query text in the prompt.
    """
    if not st.session_state.get("cortex_available", False):
        return _rule_based_query_tip(query_stats)

    prompt = (
        "You are a Snowflake query optimization expert. "
        "Give ONE specific, actionable recommendation in 2–3 sentences. "
        "Do not use markdown formatting.\n\n"
        f"Query stats: elapsed={query_stats.get('elapsed_sec', 0):.1f}s, "
        f"GB scanned={query_stats.get('gb_scanned', 0):.2f}, "
        f"cache hit={query_stats.get('cache_hit_pct', 0):.0f}%, "
        f"remote spill={query_stats.get('remote_spill_gb', 0):.2f} GB, "
        f"warehouse size={query_stats.get('warehouse_size', 'unknown')}. "
        "What is the most impactful single change to reduce cost or execution time?"
    )
    try:
        result = _session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS TIP",
            params=[model, prompt],
        ).collect()
        raw = result[0][0] if result else ""
        return raw.strip() if raw else _rule_based_query_tip(query_stats)
    except Exception:
        return _rule_based_query_tip(query_stats)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(page: str, context: dict) -> str:
    system = (
        "You are a Snowflake cost optimization expert. "
        "Provide 3 to 5 specific, actionable bullet points. "
        "Be concise — under 250 words. "
        "Do not use markdown headers or code blocks. "
        "Start each point with a dash."
    )

    if page == "overview":
        user = (
            f"Account cost summary for the selected period:\n"
            f"- Total credits billed: {context.get('total_credits', 0):.2f}\n"
            f"- vs prior period: {context.get('period_change_pct', 0):+.1f}%\n"
            f"- Top service type: {context.get('top_service', 'VIRTUAL_WAREHOUSE')} "
            f"({context.get('top_service_pct', 0):.1f}% of spend)\n"
            f"- Number of active warehouses: {context.get('warehouse_count', 0)}\n"
            f"- Storage TB: {context.get('storage_tb', 0):.2f}\n"
            "What are the top 3–5 cost optimization priorities for this account?"
        )

    elif page == "warehouse":
        user = (
            f"Warehouse usage summary:\n"
            f"- Total warehouses: {context.get('warehouse_count', 0)}\n"
            f"- Top warehouse: {context.get('top_wh_name', 'N/A')} "
            f"({context.get('top_wh_pct', 0):.1f}% of total credits)\n"
            f"- Average idle credit waste: {context.get('avg_idle_pct', 0):.1f}%\n"
            f"- Warehouses flagged OVERLOADED: {context.get('overloaded_count', 0)}\n"
            f"- Warehouses flagged OVER_PROVISIONED: {context.get('over_provisioned_count', 0)}\n"
            f"- Largest warehouse sizes in use: {context.get('warehouse_sizes', 'unknown')}\n"
            "What specific warehouse configuration changes would reduce cost most?"
        )

    elif page == "query":
        user = (
            f"Query workload summary:\n"
            f"- Total queries analyzed: {context.get('query_count', 0)}\n"
            f"- Queries with remote spill: {context.get('spill_count', 0)} "
            f"({context.get('spill_pct', 0):.1f}% of queries)\n"
            f"- Queries with <20% cache hit and >1GB scanned: {context.get('poor_cache_count', 0)}\n"
            f"- Average cache hit rate: {context.get('avg_cache_pct', 0):.1f}%\n"
            f"- Top user by query count: {context.get('top_user', 'N/A')}\n"
            "What query optimization strategies would have the highest cost impact?"
        )

    elif page == "user":
        user = (
            f"User activity summary:\n"
            f"- Active users: {context.get('user_count', 0)}\n"
            f"- Top user: {context.get('top_user', 'N/A')} "
            f"({context.get('top_user_pct', 0):.1f}% of total queries)\n"
            f"- Top user total GB scanned: {context.get('top_user_gb', 0):.1f} GB\n"
            f"- Users with >0 remote spill queries: {context.get('spill_users', 0)}\n"
            "What governance or workload management recommendations apply here?"
        )

    elif page == "storage":
        user = (
            f"Storage usage summary:\n"
            f"- Current total storage: {context.get('total_tb', 0):.3f} TB\n"
            f"- Table storage: {context.get('table_tb', 0):.3f} TB\n"
            f"- Stage storage: {context.get('stage_tb', 0):.3f} TB\n"
            f"- Fail-safe storage: {context.get('failsafe_tb', 0):.3f} TB\n"
            f"- Storage trend: {context.get('trend', 'stable')}\n"
            "What actions would reduce storage costs?"
        )
    else:
        user = "Summarize cost optimization opportunities for this Snowflake account."

    return f"{system}\n\n{user}"


def rule_based_insight(page: str, context: dict) -> str:
    """Rule-based fallback for accounts without Cortex access."""
    tips: list[str] = []

    if page == "overview":
        change = context.get("period_change_pct", 0)
        if change > 20:
            tips.append(f"- Costs increased {change:.1f}% vs. the prior period. Investigate WAREHOUSE_METERING_HISTORY for sudden spikes.")
        if context.get("top_service_pct", 0) > 80:
            tips.append(f"- {context.get('top_service', 'Virtual warehouses')} account for over 80% of spend. Focus optimization there first.")
        tips.append("- Review warehouses with AUTO_SUSPEND > 300 seconds — idle time after query completion still consumes credits.")
        tips.append("- Enable result caching (SET USE_CACHED_RESULT = TRUE) to reduce redundant query execution across users.")

    elif page == "warehouse":
        if context.get("avg_idle_pct", 0) > 30:
            tips.append(f"- Average idle time is {context.get('avg_idle_pct', 0):.1f}%. Set AUTO_SUSPEND = 60 on most warehouses to reduce waste.")
        if context.get("overloaded_count", 0) > 0:
            tips.append(f"- {context.get('overloaded_count', 0)} warehouse(s) show high queue times. Consider upsizing or enabling multi-cluster.")
        if context.get("over_provisioned_count", 0) > 0:
            tips.append(f"- {context.get('over_provisioned_count', 0)} warehouse(s) are over-provisioned. Downsize by one tier to reduce idle cost.")
        tips.append("- Consider consolidating development/ad-hoc warehouses into a single shared warehouse with auto-suspend.")

    elif page == "query":
        if context.get("spill_pct", 0) > 5:
            tips.append(f"- {context.get('spill_pct', 0):.1f}% of queries spill to remote storage. Upsize the warehouse or refactor to reduce memory pressure.")
        if context.get("avg_cache_pct", 0) < 30:
            tips.append(f"- Average cache hit rate is only {context.get('avg_cache_pct', 0):.1f}%. Enable USE_CACHED_RESULT and consider clustering keys on hot tables.")
        tips.append("- Review queries scanning >10 GB without filters — add WHERE clauses or clustering/partitioning to prune micro-partitions.")
        tips.append("- Queries with remote spill > 1 GB should be run on a larger warehouse or rewritten to reduce intermediate data size.")

    elif page == "user":
        tips.append("- Set resource monitors on warehouses used by high-volume users to cap credit consumption.")
        tips.append("- Review the top user's most frequent queries for optimization opportunities using the Query Intelligence page.")
        tips.append("- Consider dedicated warehouses with size limits per team to isolate and control costs.")

    elif page == "storage":
        if context.get("failsafe_tb", 0) > context.get("table_tb", 0) * 0.5:
            tips.append("- Fail-safe storage is large relative to table storage. Review Time Travel settings (DATA_RETENTION_TIME_IN_DAYS) — reducing from 90 to 7 days on low-priority tables saves cost.")
        if context.get("stage_tb", 0) > 0.1:
            tips.append(f"- Stage storage is {context.get('stage_tb', 0):.3f} TB. Audit internal stages for stale files that can be removed.")
        tips.append("- Use external stages (S3/GCS/Azure Blob) for raw landing data to avoid Snowflake storage charges on inbound files.")

    if not tips:
        tips.append("- No specific recommendations at current usage levels. Review after more data accumulates.")

    return "\n".join(tips)


def _rule_based_query_tip(stats: dict) -> str:
    spill = stats.get("remote_spill_gb", 0)
    cache = stats.get("cache_hit_pct", 0)
    gb    = stats.get("gb_scanned", 0)

    if spill > 1:
        return f"This query spilled {spill:.1f} GB to remote storage. Run it on a larger warehouse size to keep intermediate data in memory and reduce elapsed time."
    if cache < 10 and gb > 1:
        return f"Only {cache:.0f}% of data was served from cache. Ensure USE_CACHED_RESULT is enabled and consider clustering the scanned table on the filter columns."
    if gb > 10:
        return f"This query scanned {gb:.1f} GB. Add or refine WHERE clause filters and review table clustering to enable micro-partition pruning."
    return "Query stats appear within normal range. Profile in Snowsight Query Profile to identify bottlenecks."
```

---

## PHASE 3 — Main App Entry Point

### File: `streamlit_app.py`

```python
"""
Snowflake Cost Analyzer — Main Entry Point
Initializes session, sidebar controls, and shared session state.
All pages inherit state from st.session_state.
"""
import streamlit as st
from datetime import date, timedelta
from snowflake.snowpark.context import get_active_session

from utils.ai_insights import detect_cortex

st.set_page_config(
    page_title="Snowflake Cost Analyzer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session initialization (runs once per browser session)
# ---------------------------------------------------------------------------
if "snowpark_session" not in st.session_state:
    try:
        session = get_active_session()
        st.session_state["snowpark_session"] = session
        with st.spinner("Checking Cortex availability…"):
            st.session_state["cortex_available"] = detect_cortex(session)
    except Exception as e:
        st.error(f"Failed to initialize Snowflake session: {e}")
        st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/f/ff/Snowflake_Logo.svg",
        width=140,
    )
    st.title("Cost Analyzer")
    st.divider()

    st.subheader("📅 Date Range")
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("From", value=date.today() - timedelta(days=30))
    with col_to:
        date_to = st.date_input("To", value=date.today())

    if date_from > date_to:
        st.error("'From' date must be before 'To' date.")
        st.stop()

    st.session_state["date_from"] = str(date_from)
    st.session_state["date_to"]   = str(date_to)

    st.divider()

    st.subheader("💲 Credit Price")
    credit_price = st.number_input(
        "Price per Credit (USD)",
        min_value=0.01,
        max_value=99.99,
        value=4.00,
        step=0.50,
        format="%.2f",
        help="Your contracted Snowflake credit price. Used to estimate dollar costs.",
    )
    st.session_state["credit_price"] = credit_price

    st.divider()

    st.subheader("🤖 AI Settings")
    if st.session_state.get("cortex_available", False):
        cortex_model = st.selectbox(
            "Cortex Model",
            options=["mistral-large2", "mistral-7b", "snowflake-arctic"],
            index=0,
            help="Higher quality models cost more Cortex credits.",
        )
        st.session_state["cortex_model"] = cortex_model
        st.caption("✅ Cortex AI is available")
    else:
        st.session_state["cortex_model"] = "mistral-large2"
        st.caption("⚠️ Cortex unavailable — showing rule-based insights")

    st.divider()

    if st.button("🔄 Refresh Data", use_container_width=True, type="secondary"):
        st.cache_data.clear()
        st.rerun()

    st.caption("Data reflects Account Usage views with up to 3-hour latency.")

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
st.title("❄️ Snowflake Cost Analyzer")
st.markdown(
    "Use the **sidebar** to set your date range and credit price, then navigate "
    "to any page using the menu on the left."
)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.info("**📊 Overview**\n\nCost trends, KPIs, projected spend")
with c2:
    st.info("**🏭 Warehouse**\n\nCredits, idle time, sizing signals")
with c3:
    st.info("**🔍 Queries**\n\nExpensive, slow, spilling queries")
with c4:
    st.info("**👤 Users**\n\nTop spenders, activity heatmap")
with c5:
    st.info("**💾 Storage**\n\nStorage costs and trend")

st.divider()

# Show account-level context
session = st.session_state["snowpark_session"]
try:
    account_info = session.sql(
        "SELECT CURRENT_ACCOUNT() AS ACCT, CURRENT_REGION() AS REGION, CURRENT_ROLE() AS ROLE"
    ).collect()[0]
    st.caption(
        f"Connected to **{account_info[0]}** · Region: `{account_info[1]}` · Role: `{account_info[2]}`"
    )
except Exception:
    pass
```

---

## PHASE 4 — Pages

### File: `pages/01_Overview.py`

```python
"""Cost Overview Dashboard — daily spend trends, KPIs, service type breakdown."""
import streamlit as st
from utils.queries import get_daily_credits, get_period_comparison, get_service_type_totals, get_data_freshness
from utils.charts import credit_trend_chart, service_type_donut
from utils.ai_insights import generate_insight

st.set_page_config(page_title="Overview – Cost Analyzer", layout="wide")

if "snowpark_session" not in st.session_state:
    st.warning("Return to the Home page to initialize the app.")
    st.stop()

session    = st.session_state["snowpark_session"]
date_from  = st.session_state.get("date_from", "")
date_to    = st.session_state.get("date_to", "")
credit_price = st.session_state.get("credit_price", 4.0)

if not date_from or not date_to:
    st.warning("Set a date range in the sidebar.")
    st.stop()

# Data freshness banner
freshness = get_data_freshness(session)
if freshness.get("warehouse"):
    st.caption(f"📡 Metering data last updated: {freshness['warehouse'].strftime('%Y-%m-%d %H:%M UTC') if hasattr(freshness['warehouse'], 'strftime') else freshness['warehouse']}")

st.title("📊 Cost Overview")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading cost data…"):
    df_daily   = get_daily_credits(session, date_from, date_to)
    comparison = get_period_comparison(session, date_from, date_to)
    df_service = get_service_type_totals(session, date_from, date_to)

if df_daily.empty:
    st.info("No metering data found for the selected date range. Account Usage views have up to 3-hour latency.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
current  = comparison["current"]
prior    = comparison["prior"]
change   = ((current - prior) / prior * 100) if prior > 0 else 0.0

num_days = (
    (__import__("datetime").date.fromisoformat(date_to) - __import__("datetime").date.fromisoformat(date_from)).days + 1
)
daily_avg = current / num_days if num_days > 0 else 0.0

today = __import__("datetime").date.today()
days_remaining = (
    (__import__("datetime").date(today.year, today.month + 1 if today.month < 12 else 1, 1)
     - today).days
)
projected = (current / num_days * (num_days + days_remaining)) if num_days > 0 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Credits", f"{current:,.2f}", delta=None)
k2.metric("vs. Prior Period", f"{change:+.1f}%", delta=f"{change:+.1f}%")
k3.metric("Daily Average", f"{daily_avg:,.2f}")
k4.metric("Projected Month-End", f"{projected:,.0f} cr")
k5.metric("Estimated Cost (USD)", f"${current * credit_price:,.0f}", help="Based on credit price set in sidebar")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
col_chart, col_donut = st.columns([3, 2])

with col_chart:
    st.subheader("Daily Credits by Service Type")
    st.altair_chart(credit_trend_chart(df_daily), use_container_width=True)

with col_donut:
    st.subheader("Credits by Service Type")
    if not df_service.empty:
        st.altair_chart(service_type_donut(df_service), use_container_width=True)
    else:
        st.info("No service type breakdown available.")

# ---------------------------------------------------------------------------
# AI Insight
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🤖 AI Insights")

top_service_row = df_service.iloc[0] if not df_service.empty else None
context = {
    "total_credits":       current,
    "period_change_pct":   change,
    "top_service":         top_service_row["SERVICE_TYPE"] if top_service_row is not None else "N/A",
    "top_service_pct":     (top_service_row["CREDITS_BILLED"] / current * 100) if (top_service_row is not None and current > 0) else 0,
    "warehouse_count":     df_service["SERVICE_TYPE"].nunique(),
    "storage_tb":          0,
}

if st.button("Generate Insights", key="overview_insight"):
    with st.spinner("Analyzing with Cortex AI…"):
        insight = generate_insight(session, "overview", context, st.session_state.get("cortex_model", "mistral-large2"))
    st.info(insight)
```

---

### File: `pages/02_Warehouse_Analysis.py`

```python
"""Warehouse Analysis — credit breakdown, idle time, sizing signals."""
import streamlit as st
import pandas as pd
from utils.queries import get_warehouse_summary, get_warehouse_daily_trend, get_warehouse_sizing_signals, get_data_freshness
from utils.charts import warehouse_bar_chart, warehouse_trend_chart, idle_time_bar_chart
from utils.ai_insights import generate_insight

st.set_page_config(page_title="Warehouse – Cost Analyzer", layout="wide")

if "snowpark_session" not in st.session_state:
    st.warning("Return to the Home page to initialize the app.")
    st.stop()

session      = st.session_state["snowpark_session"]
date_from    = st.session_state.get("date_from", "")
date_to      = st.session_state.get("date_to", "")
credit_price = st.session_state.get("credit_price", 4.0)

freshness = get_data_freshness(session)
if freshness.get("warehouse"):
    st.caption(f"📡 Metering data last updated: {freshness['warehouse']}")

st.title("🏭 Warehouse Analysis")

with st.spinner("Loading warehouse data…"):
    df_summary  = get_warehouse_summary(session, date_from, date_to)
    df_trend    = get_warehouse_daily_trend(session, date_from, date_to)
    df_signals  = get_warehouse_sizing_signals(session, date_from, date_to)

if df_summary.empty:
    st.info("No warehouse metering data for the selected date range.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
total_credits      = df_summary["TOTAL_CREDITS"].sum()
total_idle_credits = df_summary["IDLE_CREDITS"].sum()
avg_idle_pct       = (total_idle_credits / total_credits * 100) if total_credits > 0 else 0
wh_count           = len(df_summary)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Compute Credits", f"{total_credits:,.2f}")
k2.metric("Idle Credits Wasted",   f"{total_idle_credits:,.2f}", help="Compute credits used when no query was running")
k3.metric("Avg Idle %",            f"{avg_idle_pct:.1f}%")
k4.metric("Estimated Idle Cost",   f"${total_idle_credits * credit_price:,.0f}")

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Credits Breakdown", "📈 Trend", "⚠️ Idle Time", "🔬 Sizing Signals"])

with tab1:
    st.subheader("Credits by Warehouse")
    st.altair_chart(warehouse_bar_chart(df_summary), use_container_width=True)
    st.dataframe(
        df_summary[["WAREHOUSE_NAME", "COMPUTE_CREDITS", "CLOUD_SERVICE_CREDITS", "TOTAL_CREDITS", "IDLE_CREDITS", "IDLE_PCT"]],
        use_container_width=True,
        hide_index=True,
    )

with tab2:
    if df_trend.empty:
        st.info("No trend data available.")
    else:
        wh_options = ["All"] + sorted(df_trend["WAREHOUSE_NAME"].unique().tolist())
        selected_wh = st.selectbox("Filter Warehouse", options=wh_options)
        df_filtered = df_trend if selected_wh == "All" else df_trend[df_trend["WAREHOUSE_NAME"] == selected_wh]
        st.altair_chart(warehouse_trend_chart(df_filtered), use_container_width=True)

with tab3:
    st.subheader("Idle vs. Query Credit Distribution")
    st.caption("Red = idle (no query running). Ideal is a thin red bar.")
    st.altair_chart(idle_time_bar_chart(df_summary), use_container_width=True)
    st.markdown(
        "**Idle credits** = `CREDITS_USED_COMPUTE − CREDITS_ATTRIBUTED_COMPUTE_QUERIES`  \n"
        "Set `AUTO_SUSPEND = 60` on warehouses with high idle percentages."
    )

with tab4:
    if df_signals.empty:
        st.info("No sizing signal data available.")
    else:
        signal_colors = {
            "OVERLOADED":       "🔴",
            "OVER_PROVISIONED": "🟡",
            "BALANCED":         "🟢",
        }
        df_signals["SIGNAL"] = df_signals["SIZING_SIGNAL"].map(lambda x: f"{signal_colors.get(x, '')} {x}")
        st.dataframe(
            df_signals[["WAREHOUSE_NAME", "WAREHOUSE_SIZE", "COMPUTE_CREDITS", "IDLE_PCT", "AVG_ELAPSED_SEC", "QUEUE_PCT", "SIGNAL"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("OVERLOADED → high queue time, consider upsizing or multi-cluster. OVER_PROVISIONED → high idle %, consider downsizing.")

# ---------------------------------------------------------------------------
# AI Insight
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🤖 AI Insights")

overloaded_count = len(df_signals[df_signals["SIZING_SIGNAL"] == "OVERLOADED"]) if not df_signals.empty else 0
over_prov_count  = len(df_signals[df_signals["SIZING_SIGNAL"] == "OVER_PROVISIONED"]) if not df_signals.empty else 0
top_wh           = df_summary.iloc[0]
wh_sizes         = df_signals["WAREHOUSE_SIZE"].dropna().unique().tolist() if not df_signals.empty else []

context = {
    "warehouse_count":       wh_count,
    "top_wh_name":           top_wh["WAREHOUSE_NAME"],
    "top_wh_pct":            top_wh["TOTAL_CREDITS"] / total_credits * 100 if total_credits > 0 else 0,
    "avg_idle_pct":          avg_idle_pct,
    "overloaded_count":      overloaded_count,
    "over_provisioned_count": over_prov_count,
    "warehouse_sizes":       ", ".join(str(s) for s in wh_sizes),
}

if st.button("Generate Insights", key="wh_insight"):
    with st.spinner("Analyzing with Cortex AI…"):
        insight = generate_insight(session, "warehouse", context, st.session_state.get("cortex_model", "mistral-large2"))
    st.info(insight)
```

---

### File: `pages/03_Query_Intelligence.py`

```python
"""Query Intelligence — expensive, slow, spilling, and cache-missing queries."""
import streamlit as st
from utils.queries import (
    get_top_queries_by_duration,
    get_top_queries_by_bytes,
    get_spill_queries,
    get_poor_cache_queries,
    get_data_freshness,
)
from utils.ai_insights import generate_insight, generate_query_tip

st.set_page_config(page_title="Queries – Cost Analyzer", layout="wide")

if "snowpark_session" not in st.session_state:
    st.warning("Return to the Home page to initialize the app.")
    st.stop()

session   = st.session_state["snowpark_session"]
date_from = st.session_state.get("date_from", "")
date_to   = st.session_state.get("date_to", "")

freshness = get_data_freshness(session)
if freshness.get("queries"):
    st.caption(f"📡 Query history last updated: {freshness['queries']}")

st.title("🔍 Query Intelligence")
st.caption("⚠️ Account Usage QUERY_HISTORY has up to 45-minute latency. Recent queries may not appear.")

LIMIT = st.sidebar.number_input("Rows to show", min_value=10, max_value=200, value=50, step=10)

with st.spinner("Loading query data…"):
    df_duration   = get_top_queries_by_duration(session, date_from, date_to, LIMIT)
    df_bytes      = get_top_queries_by_bytes(session, date_from, date_to, LIMIT)
    df_spill      = get_spill_queries(session, date_from, date_to, LIMIT)
    df_cache_miss = get_poor_cache_queries(session, date_from, date_to, LIMIT)

tab1, tab2, tab3, tab4 = st.tabs([
    f"⏱️ Slowest ({len(df_duration)})",
    f"📦 Most Bytes Scanned ({len(df_bytes)})",
    f"💧 Spilling to Disk ({len(df_spill)})",
    f"🎯 Cache Misses ({len(df_cache_miss)})",
])


def _render_query_table(df, cols):
    """Renders a query dataframe with an expandable AI tip button per row."""
    if df.empty:
        st.info("No queries match this criteria for the selected date range.")
        return

    st.dataframe(df[cols], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Per-Query AI Optimization Tip")
    st.caption("Select a query index (0-based) to get an AI optimization recommendation based on its performance stats.")

    idx = st.number_input("Query index", min_value=0, max_value=len(df) - 1, value=0, step=1, key=f"idx_{cols[0]}")
    row = df.iloc[idx]

    with st.expander("Query Preview (read-only)"):
        st.code(row.get("QUERY_PREVIEW", "[unavailable]"), language="sql")

    if st.button("Get AI Tip for this Query", key=f"tip_{cols[0]}"):
        stats = {
            "elapsed_sec":      row.get("ELAPSED_SEC", 0),
            "gb_scanned":       row.get("GB_SCANNED", 0),
            "cache_hit_pct":    row.get("CACHE_HIT_PCT", 0),
            "remote_spill_gb":  row.get("REMOTE_SPILL_GB", 0),
            "warehouse_size":   row.get("WAREHOUSE_SIZE", "unknown"),
        }
        with st.spinner("Generating optimization tip…"):
            tip = generate_query_tip(
                session, stats, st.session_state.get("cortex_model", "mistral-large2")
            )
        st.success(tip)


with tab1:
    _render_query_table(
        df_duration,
        ["USER_NAME", "WAREHOUSE_NAME", "WAREHOUSE_SIZE", "ELAPSED_SEC", "GB_SCANNED", "CACHE_HIT_PCT", "REMOTE_SPILL_GB", "START_TIME"],
    )

with tab2:
    _render_query_table(
        df_bytes,
        ["USER_NAME", "WAREHOUSE_NAME", "GB_SCANNED", "ELAPSED_SEC", "CACHE_HIT_PCT", "REMOTE_SPILL_GB", "START_TIME"],
    )

with tab3:
    if df_spill.empty:
        st.success("No spilling queries found. Your warehouse sizes appear appropriate for the workload.")
    else:
        _render_query_table(
            df_spill,
            ["USER_NAME", "WAREHOUSE_NAME", "WAREHOUSE_SIZE", "LOCAL_SPILL_GB", "REMOTE_SPILL_GB", "GB_SCANNED", "ELAPSED_SEC", "START_TIME"],
        )

with tab4:
    if df_cache_miss.empty:
        st.success("No significant cache misses found.")
    else:
        _render_query_table(
            df_cache_miss,
            ["USER_NAME", "WAREHOUSE_NAME", "CACHE_HIT_PCT", "GB_SCANNED", "ELAPSED_SEC", "START_TIME"],
        )

# ---------------------------------------------------------------------------
# Page-level AI Insight
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🤖 AI Insights — Query Workload")

spill_count       = len(df_spill)
total_queries     = len(df_duration)
avg_cache_pct     = df_duration["CACHE_HIT_PCT"].mean() if not df_duration.empty else 0
top_user          = df_duration["USER_NAME"].value_counts().idxmax() if not df_duration.empty else "N/A"
poor_cache_count  = len(df_cache_miss)

context = {
    "query_count":       total_queries,
    "spill_count":       spill_count,
    "spill_pct":         spill_count / total_queries * 100 if total_queries > 0 else 0,
    "avg_cache_pct":     avg_cache_pct,
    "poor_cache_count":  poor_cache_count,
    "top_user":          top_user,
}

if st.button("Generate Insights", key="query_insight"):
    with st.spinner("Analyzing with Cortex AI…"):
        insight = generate_insight(session, "query", context, st.session_state.get("cortex_model", "mistral-large2"))
    st.info(insight)
```

---

### File: `pages/04_User_Analysis.py`

```python
"""User Analysis — top credit consumers, activity heatmap."""
import streamlit as st
from utils.queries import get_user_stats, get_user_activity_heatmap, get_data_freshness
from utils.charts import user_bar_chart, user_heatmap_chart
from utils.ai_insights import generate_insight

st.set_page_config(page_title="Users – Cost Analyzer", layout="wide")

if "snowpark_session" not in st.session_state:
    st.warning("Return to the Home page to initialize the app.")
    st.stop()

session   = st.session_state["snowpark_session"]
date_from = st.session_state.get("date_from", "")
date_to   = st.session_state.get("date_to", "")

freshness = get_data_freshness(session)
if freshness.get("queries"):
    st.caption(f"📡 Query history last updated: {freshness['queries']}")

st.title("👤 User Analysis")

with st.spinner("Loading user data…"):
    df_users   = get_user_stats(session, date_from, date_to)
    df_heatmap = get_user_activity_heatmap(session, date_from, date_to)

if df_users.empty:
    st.info("No user activity data found for the selected date range.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
total_queries = df_users["QUERY_COUNT"].sum()
top_user_row  = df_users.iloc[0]
active_users  = len(df_users)
spill_users   = len(df_users[df_users["TOTAL_SPILL_GB"] > 0])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Users",          active_users)
k2.metric("Total Queries",         f"{total_queries:,}")
k3.metric("Top User",              top_user_row["USER_NAME"])
k4.metric("Users with Spill",      spill_users, help="Users who ran at least one query that spilled to disk")

st.divider()

# ---------------------------------------------------------------------------
# Charts and tables
# ---------------------------------------------------------------------------
col_bar, col_heat = st.columns([2, 3])

with col_bar:
    st.subheader("Top Users by Query Count")
    st.altair_chart(user_bar_chart(df_users, top_n=15), use_container_width=True)

with col_heat:
    st.subheader("Query Activity Heatmap (UTC)")
    if not df_heatmap.empty:
        st.altair_chart(user_heatmap_chart(df_heatmap), use_container_width=True)
        st.caption("Darker = more queries. Helps identify off-hours batch jobs vs. interactive usage patterns.")
    else:
        st.info("No heatmap data available.")

st.subheader("Full User Detail")
st.dataframe(
    df_users[[
        "USER_NAME", "QUERY_COUNT", "TOTAL_ELAPSED_HRS", "AVG_ELAPSED_SEC",
        "TOTAL_GB_SCANNED", "AVG_CACHE_HIT_PCT", "TOTAL_SPILL_GB",
        "WAREHOUSES_USED", "LAST_QUERY_TIME",
    ]],
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# AI Insight
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🤖 AI Insights")

context = {
    "user_count":     active_users,
    "top_user":       top_user_row["USER_NAME"],
    "top_user_pct":   top_user_row["QUERY_COUNT"] / total_queries * 100 if total_queries > 0 else 0,
    "top_user_gb":    top_user_row["TOTAL_GB_SCANNED"],
    "spill_users":    spill_users,
}

if st.button("Generate Insights", key="user_insight"):
    with st.spinner("Analyzing with Cortex AI…"):
        insight = generate_insight(session, "user", context, st.session_state.get("cortex_model", "mistral-large2"))
    st.info(insight)
```

---

### File: `pages/05_Storage.py`

```python
"""Storage Cost Analysis — storage breakdown, trend, and cost estimate."""
import streamlit as st
from utils.queries import get_storage_trend, get_data_freshness
from utils.charts import storage_area_chart
from utils.ai_insights import generate_insight

st.set_page_config(page_title="Storage – Cost Analyzer", layout="wide")

if "snowpark_session" not in st.session_state:
    st.warning("Return to the Home page to initialize the app.")
    st.stop()

session      = st.session_state["snowpark_session"]
date_from    = st.session_state.get("date_from", "")
date_to      = st.session_state.get("date_to", "")
credit_price = st.session_state.get("credit_price", 4.0)

STORAGE_PRICE_PER_TB = st.sidebar.number_input(
    "Storage Price ($/TB/month)", min_value=1.0, max_value=100.0, value=23.0, step=1.0,
    help="Standard Snowflake on-demand storage price is ~$23/TB/month"
)

freshness = get_data_freshness(session)
if freshness.get("storage"):
    st.caption(f"📡 Storage data last updated: {freshness['storage']}")

st.title("💾 Storage Analysis")

with st.spinner("Loading storage data…"):
    df_storage = get_storage_trend(session, date_from, date_to)

if df_storage.empty:
    st.info("No storage data found for the selected date range.")
    st.stop()

# Latest values
latest = df_storage.iloc[-1]
earliest = df_storage.iloc[0]

total_tb     = float(latest["TOTAL_TB"])
table_tb     = float(latest["TABLE_TB"])
stage_tb     = float(latest["STAGE_TB"])
failsafe_tb  = float(latest["FAILSAFE_TB"])
monthly_cost = total_tb * STORAGE_PRICE_PER_TB

trend_change = ((total_tb - float(earliest["TOTAL_TB"])) / float(earliest["TOTAL_TB"]) * 100
                if float(earliest["TOTAL_TB"]) > 0 else 0)
trend_label  = "growing" if trend_change > 5 else ("shrinking" if trend_change < -5 else "stable")

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Storage",         f"{total_tb:.3f} TB")
k2.metric("Table Storage",         f"{table_tb:.3f} TB")
k3.metric("Stage Storage",         f"{stage_tb:.3f} TB")
k4.metric("Fail-safe Storage",     f"{failsafe_tb:.3f} TB")
k5.metric("Est. Monthly Cost",     f"${monthly_cost:,.0f}",
          help=f"Based on ${STORAGE_PRICE_PER_TB}/TB/month (configurable in sidebar)")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
st.subheader("Storage Trend")
st.altair_chart(storage_area_chart(df_storage), use_container_width=True)

st.subheader("Storage Breakdown (latest)")
col_table = {
    "Type": ["Table Data", "Stage Files", "Fail-safe"],
    "TB":   [table_tb, stage_tb, failsafe_tb],
    "Est. Monthly Cost (USD)": [
        f"${table_tb * STORAGE_PRICE_PER_TB:,.2f}",
        f"${stage_tb * STORAGE_PRICE_PER_TB:,.2f}",
        f"${failsafe_tb * STORAGE_PRICE_PER_TB:,.2f}",
    ],
}
import pandas as pd
st.dataframe(pd.DataFrame(col_table), use_container_width=True, hide_index=True)

st.caption(
    "**Fail-safe** storage cannot be reduced directly. Reducing `DATA_RETENTION_TIME_IN_DAYS` on tables "
    "decreases the fail-safe accumulation period. **Stage** storage can be cleaned with `REMOVE @stage_name`."
)

# ---------------------------------------------------------------------------
# AI Insight
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🤖 AI Insights")

context = {
    "total_tb":    total_tb,
    "table_tb":    table_tb,
    "stage_tb":    stage_tb,
    "failsafe_tb": failsafe_tb,
    "trend":       trend_label,
}

if st.button("Generate Insights", key="storage_insight"):
    with st.spinner("Analyzing with Cortex AI…"):
        insight = generate_insight(session, "storage", context, st.session_state.get("cortex_model", "mistral-large2"))
    st.info(insight)
```

---

## PHASE 5 — Snowflake Deployment SQL

### File: `deploy/setup.sql`

```sql
-- =============================================================================
-- Snowflake Cost Analyzer — Deployment Setup
-- Run this as ACCOUNTADMIN before deploying the Streamlit app.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- ---------------------------------------------------------------------------
-- 1. Database and schema
-- ---------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS COST_ANALYZER_DB
    COMMENT = 'Snowflake Cost Analyzer application database';

CREATE SCHEMA IF NOT EXISTS COST_ANALYZER_DB.COST_ANALYZER_SCHEMA
    COMMENT = 'Schema for Cost Analyzer app objects';

-- ---------------------------------------------------------------------------
-- 2. Dedicated warehouse (XS — sufficient for Account Usage aggregations)
-- ---------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS COST_ANALYZER_WH
    WAREHOUSE_SIZE    = 'XSMALL'
    AUTO_SUSPEND      = 60
    AUTO_RESUME       = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Warehouse for Snowflake Cost Analyzer queries';

-- ---------------------------------------------------------------------------
-- 3. Application role
-- ---------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS COST_ANALYZER_ROLE
    COMMENT = 'Role for the Cost Analyzer Streamlit app';

-- ---------------------------------------------------------------------------
-- 4. Grants to application role
-- ---------------------------------------------------------------------------
GRANT USAGE ON DATABASE COST_ANALYZER_DB            TO ROLE COST_ANALYZER_ROLE;
GRANT USAGE ON SCHEMA COST_ANALYZER_DB.COST_ANALYZER_SCHEMA TO ROLE COST_ANALYZER_ROLE;
GRANT USAGE ON WAREHOUSE COST_ANALYZER_WH            TO ROLE COST_ANALYZER_ROLE;

-- Grant access to Account Usage views (CRITICAL — without this the app has no data)
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE      TO ROLE COST_ANALYZER_ROLE;

-- Grant Cortex AI access (optional — app degrades gracefully without this)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER            TO ROLE COST_ANALYZER_ROLE;

-- ---------------------------------------------------------------------------
-- 5. Grant role to deploying user (replace with actual username)
-- ---------------------------------------------------------------------------
-- GRANT ROLE COST_ANALYZER_ROLE TO USER <YOUR_USERNAME>;

-- ---------------------------------------------------------------------------
-- 6. Verify setup
-- ---------------------------------------------------------------------------
SHOW GRANTS TO ROLE COST_ANALYZER_ROLE;
```

---

## PHASE 6 — Native App Packaging

### File: `deploy/native_app/manifest.yml`

```yaml
manifest_version: 1

version:
  name: v1_0
  label: "1.0.0"
  comment: "Snowflake Cost Analyzer v1.0 - AI-powered cost analytics"

artifacts:
  readme: README.md
  setup_script: setup.sql
  default_streamlit: COST_ANALYZER_SCHEMA.COST_ANALYZER_APP
  extension_code: true

privileges:
  - privilege: "IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE"
    description: >
      Required to read Account Usage views including WAREHOUSE_METERING_HISTORY,
      QUERY_HISTORY, METERING_DAILY_HISTORY, and STORAGE_USAGE.
      This data never leaves your Snowflake account.

  - privilege: "EXECUTE CORTEX FUNCTIONS"
    description: >
      Optional. Enables AI-generated cost optimization insights using
      Snowflake Cortex LLMs. The app works without this privilege
      using built-in rule-based recommendations.
```

### File: `deploy/native_app/setup.sql`

```sql
-- =============================================================================
-- Snowflake Cost Analyzer — Native App Setup Script
-- This script runs automatically when a consumer installs the app.
-- =============================================================================

-- Application role (consumers grant privileges to this role)
CREATE APPLICATION ROLE IF NOT EXISTS COST_ANALYZER_ROLE;

-- Schema to hold app objects
CREATE SCHEMA IF NOT EXISTS COST_ANALYZER_SCHEMA;

-- Register the Streamlit app
CREATE OR REPLACE STREAMLIT COST_ANALYZER_SCHEMA.COST_ANALYZER_APP
    FROM '/'
    MAIN_FILE = '/streamlit_app.py';

-- Grant app role access to the schema and Streamlit object
GRANT USAGE ON SCHEMA COST_ANALYZER_SCHEMA
    TO APPLICATION ROLE COST_ANALYZER_ROLE;

GRANT USAGE ON STREAMLIT COST_ANALYZER_SCHEMA.COST_ANALYZER_APP
    TO APPLICATION ROLE COST_ANALYZER_ROLE;
```

---

## PHASE 7 — Snowflake CLI Deployment Commands

Run these in order from the `snowflake-cost-analyzer/` directory.

### Step 7.1 — Configure Snowflake CLI connection

```bash
snow connection add \
  --connection-name cost-analyzer-dev \
  --account <YOUR_ACCOUNT_IDENTIFIER> \
  --user <YOUR_USERNAME> \
  --role COST_ANALYZER_ROLE \
  --warehouse COST_ANALYZER_WH \
  --database COST_ANALYZER_DB \
  --schema COST_ANALYZER_SCHEMA
```

### Step 7.2 — Run setup SQL (as ACCOUNTADMIN)

```bash
snow sql -f deploy/setup.sql --connection <ACCOUNTADMIN_CONNECTION>
```

### Step 7.3 — Deploy Streamlit app to SiS

```bash
snow streamlit deploy \
  --connection cost-analyzer-dev \
  --database COST_ANALYZER_DB \
  --schema COST_ANALYZER_SCHEMA \
  --warehouse COST_ANALYZER_WH \
  --open
```

### Step 7.4 — Verify deployment

```bash
snow streamlit list --connection cost-analyzer-dev
```

---

## PHASE 8 — Native App Packaging Commands

Run these in Snowflake (Snowsight or SnowSQL) as ACCOUNTADMIN.

### Step 8.1 — Create provider-side objects

```sql
USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS COST_ANALYZER_PROVIDER_DB;
CREATE SCHEMA IF NOT EXISTS COST_ANALYZER_PROVIDER_DB.APP_CODE;

CREATE STAGE IF NOT EXISTS COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Source code stage for Cost Analyzer Native App';

CREATE APPLICATION PACKAGE IF NOT EXISTS COST_ANALYZER_PKG
    COMMENT = 'Snowflake Cost Analyzer — Native App Package';
```

### Step 8.2 — Upload source files to stage

```bash
# Upload all app files using Snowflake CLI
snow stage copy . @COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE \
  --connection cost-analyzer-dev \
  --recursive \
  --overwrite
```

### Step 8.3 — Add version to application package

```sql
ALTER APPLICATION PACKAGE COST_ANALYZER_PKG
    ADD VERSION v1_0
    USING '@COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE'
    LABEL = '1.0.0'
    COMMENT = 'Initial release';
```

### Step 8.4 — Set default release directive

```sql
ALTER APPLICATION PACKAGE COST_ANALYZER_PKG
    SET DEFAULT RELEASE DIRECTIVE
    VERSION = v1_0
    PATCH = 0;
```

### Step 8.5 — Local install test

```sql
-- Install the app locally to test before publishing
CREATE APPLICATION COST_ANALYZER_TEST
    FROM APPLICATION PACKAGE COST_ANALYZER_PKG
    USING VERSION v1_0;

-- Grant required privileges to the test install
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE
    TO APPLICATION COST_ANALYZER_TEST;

GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER
    TO APPLICATION COST_ANALYZER_TEST;
```

### Step 8.6 — Verify local install

```sql
-- Open the app in Snowsight by navigating to:
-- Data Products → Apps → COST_ANALYZER_TEST

-- Or verify via SQL:
SHOW STREAMLITS IN APPLICATION COST_ANALYZER_TEST;
```

### Step 8.7 — Create Marketplace listing (Snowsight UI)

```
1. Go to Snowsight → Data Products → Provider Studio → + Listing
2. Select: "Snowflake Marketplace" (not Private Listing)
3. Listing title: "Snowflake Cost Analyzer"
4. Short description: "AI-powered cost analytics for Snowflake — warehouses, queries, users, and storage"
5. Long description: (see README.md)
6. Categories: Business Intelligence, Analytics, Cost Management
7. Data product: Select COST_ANALYZER_PKG
8. Pricing: Free
9. Regions: Select all commercial regions
10. Upload screenshots (minimum 5, minimum 1280x800)
11. Click "Submit for Review"
```

---

## PHASE 9 — Validation Checklist

Run through this checklist before Marketplace submission on June 10.

### Functional Tests

```
[ ] Home page loads, shows connected account/region/role
[ ] Date range picker works, changes propagate to all pages
[ ] Credit price input updates all dollar estimates
[ ] "Refresh Data" button clears cache and reloads
[ ] Overview: KPIs show values, trend chart renders, donut chart renders
[ ] Overview: "Generate Insights" button returns text
[ ] Warehouse: Credits table loads, idle column has values
[ ] Warehouse: All 4 tabs render without error
[ ] Warehouse: Sizing signals table shows BALANCED/OVERLOADED/OVER_PROVISIONED labels
[ ] Queries: All 4 tabs load data or show informative empty state
[ ] Queries: Per-query AI tip generates for selected row index
[ ] Users: Top users table loads, heatmap renders
[ ] Storage: Storage trend chart renders, cost estimate shows
[ ] All pages show data freshness timestamp
[ ] Empty state message shows when view returns no rows (test with future date range)
```

### Security Tests

```
[ ] Raw QUERY_TEXT is never sent to Cortex (code review utils/ai_insights.py)
[ ] All SQL in queries.py uses parameterized ? bindings (no f-strings with user input)
[ ] App has no write operations to any Snowflake object
[ ] App renders correctly when logged in as a non-admin user with only COST_ANALYZER_ROLE
[ ] Cortex fallback works: revoke SNOWFLAKE.CORTEX_USER, reload app, confirm rule-based insights appear
```

### Native App Tests

```
[ ] COST_ANALYZER_TEST installs without errors from APPLICATION PACKAGE
[ ] All pages work inside the installed native app (not just the SiS version)
[ ] Consumer privilege grant flow works: grant IMPORTED PRIVILEGES, confirm data loads
[ ] App renders correctly with no privileges granted (should show helpful error, not crash)
[ ] README.md renders correctly in Snowsight App detail view
[ ] manifest.yml privilege descriptions are accurate and clear
```

### Marketplace Submission Checklist

```
[ ] At least 5 screenshots captured at 1280x800 or higher
[ ] Listing title: "Snowflake Cost Analyzer"
[ ] Short description (140 chars max): written and reviewed
[ ] Long description: covers all 5 pages, prerequisites, what data is accessed
[ ] Contact/support email configured
[ ] Pricing set to: Free
[ ] All target regions selected
[ ] Application package version v1_0 set as default release directive
[ ] Submitted via Provider Studio → Submit for Review
[ ] Confirmation email received from Snowflake
[ ] Private listing created as backup for pilot customers during review period
```

---

## Troubleshooting

### "SQL compilation error: Object 'SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY' does not exist"

The active role does not have `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE`.
Run as ACCOUNTADMIN: `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE COST_ANALYZER_ROLE;`

### "Failed to initialize Snowflake session"

Running outside of SiS. `get_active_session()` only works when the code runs inside Snowflake.
Use `snow streamlit deploy` and open the app via Snowsight — do not run locally.

### "SNOWFLAKE.CORTEX.COMPLETE is not available"

The account is on Standard Edition, or the `SNOWFLAKE.CORTEX_USER` database role has not been granted.
The app will automatically show rule-based insights — no action needed.

### Charts render blank

Verify column names match exactly. `df.columns.tolist()` in a `st.write()` call helps debug column mismatches.

### Altair chart shows "No data to display"

Date range selected has no data in Account Usage. Try expanding the range. Account Usage has up to 3-hour latency.
```
