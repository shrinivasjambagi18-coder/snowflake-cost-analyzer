```python
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

@st.cache_data(ttl=1800)
def get_daily_credits(session, start_date, end_date):
    query = """
    SELECT 
        TO_DATE(USAGE_DATE) AS usage_date,
        SUM(CREDITS_USED) AS total_credits,
        SUM(CREDITS_USED_COMPUTE) AS compute_credits,
        SUM(CREDITS_USED_CLOUD_SERVICES) AS cloud_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE USAGE_DATE BETWEEN ? AND ?
    GROUP BY TO_DATE(USAGE_DATE)
    ORDER BY usage_date
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_period_comparison(session, current_start, current_end, previous_start, previous_end):
    query = """
    SELECT 
        TO_DATE(USAGE_DATE) AS usage_date,
        SUM(CREDITS_USED) AS total_credits,
        CASE 
            WHEN USAGE_DATE BETWEEN ? AND ? THEN 'current'
            ELSE 'previous'
        END AS period
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE (USAGE_DATE BETWEEN ? AND ?) OR (USAGE_DATE BETWEEN ? AND ?)
    GROUP BY usage_date, period
    ORDER BY usage_date
    """
    return session.sql(query, params=[current_start, current_end, previous_start, previous_end, current_start, current_end, previous_start, previous_end]).to_pandas()

@st.cache_data(ttl=1800)
def get_service_type_totals(session, start_date, end_date):
    query = """
    SELECT 
        SERVICE_TYPE,
        SUM(CREDITS_USED) AS total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
    WHERE USAGE_DATE BETWEEN ? AND ?
    GROUP BY SERVICE_TYPE
    ORDER BY total_credits DESC
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_warehouse_summary(session, start_date, end_date):
    query = """
    SELECT 
        WAREHOUSE_NAME,
        SUM(CREDITS_USED) AS total_credits,
        COUNT(*) AS total_queries,
        AVG(CREDITS_USED) AS avg_credits_per_query,
        SUM(TOTAL_ELAPSED_TIME) / 1000 AS total_elapsed_seconds
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND WAREHOUSE_NAME IS NOT NULL
        AND WAREHOUSE_SIZE IS NOT NULL
    GROUP BY WAREHOUSE_NAME
    ORDER BY total_credits DESC
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_warehouse_daily_trend(session, warehouse_name, start_date, end_date):
    query = """
    SELECT 
        TO_DATE(START_TIME) AS usage_date,
        WAREHOUSE_NAME,
        SUM(CREDITS_USED) AS total_credits,
        COUNT(*) AS total_queries,
        AVG(TOTAL_ELAPSED_TIME) / 1000 AS avg_elapsed_ms
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE WAREHOUSE_NAME = ?
        AND START_TIME BETWEEN ? AND ?
    GROUP BY usage_date, WAREHOUSE_NAME
    ORDER BY usage_date
    """
    return session.sql(query, params=[warehouse_name, start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_warehouse_sizing_signals(session, start_date, end_date):
    query = """
    SELECT 
        WAREHOUSE_NAME,
        WAREHOUSE_SIZE,
        COUNT(*) AS query_count,
        AVG(TOTAL_ELAPSED_TIME) / 1000 AS avg_elapsed_sec,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY TOTAL_ELAPSED_TIME) / 1000 AS median_elapsed_sec,
        SUM(BYTES_SCANNED) / 1e9 AS total_gb_scanned,
        SUM(CREDITS_USED) AS total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND WAREHOUSE_NAME IS NOT NULL
        AND WAREHOUSE_SIZE IS NOT NULL
    GROUP BY WAREHOUSE_NAME, WAREHOUSE_SIZE
    ORDER BY total_credits DESC
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_top_queries_by_duration(session, start_date, end_date, limit=20):
    query = """
    SELECT 
        QUERY_ID,
        QUERY_TEXT,
        WAREHOUSE_NAME,
        WAREHOUSE_SIZE,
        TOTAL_ELAPSED_TIME / 1000 AS elapsed_seconds,
        CREDITS_USED,
        BYTES_SCANNED,
        ROWS_PRODUCED,
        START_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND WAREHOUSE_NAME IS NOT NULL
    ORDER BY TOTAL_ELAPSED_TIME DESC
    LIMIT ?
    """
    return session.sql(query, params=[start_date, end_date, limit]).to_pandas()

@st.cache_data(ttl=1800)
def get_top_queries_by_scan(session, start_date, end_date, limit=20):
    query = """
    SELECT 
        QUERY_ID,
        QUERY_TEXT,
        WAREHOUSE_NAME,
        WAREHOUSE_SIZE,
        BYTES_SCANNED / 1e9 AS gb_scanned,
        TOTAL_ELAPSED_TIME / 1000 AS elapsed_seconds,
        CREDITS_USED,
        PARTITIONS_SCANNED,
        START_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND WAREHOUSE_NAME IS NOT NULL
    ORDER BY BYTES_SCANNED DESC
    LIMIT ?
    """
    return session.sql(query, params=[start_date, end_date, limit]).to_pandas()

@st.cache_data(ttl=1800)
def get_spill_queries(session, start_date, end_date, limit=20):
    query = """
    SELECT 
        QUERY_ID,
        QUERY_TEXT,
        WAREHOUSE_NAME,
        WAREHOUSE_SIZE,
        TOTAL_ELAPSED_TIME / 1000 AS elapsed_seconds,
        CREDITS_USED,
        BYTES_SPILLED_TO_LOCAL_STORAGE / 1e9 AS gb_spilled_local,
        BYTES_SPILLED_TO_REMOTE_STORAGE / 1e9 AS gb_spilled_remote,
        START_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0)
        AND WAREHOUSE_NAME IS NOT NULL
    ORDER BY (BYTES_SPILLED_TO_LOCAL_STORAGE + BYTES_SPILLED_TO_REMOTE_STORAGE) DESC
    LIMIT ?
    """
    return session.sql(query, params=[start_date, end_date, limit]).to_pandas()

@st.cache_data(ttl=1800)
def get_poor_cache_queries(session, start_date, end_date, min_cache_ratio=0.1, limit=20):
    query = """
    SELECT 
        QUERY_ID,
        QUERY_TEXT,
        WAREHOUSE_NAME,
        WAREHOUSE_SIZE,
        TOTAL_ELAPSED_TIME / 1000 AS elapsed_seconds,
        CREDITS_USED,
        BYTES_SCANNED / 1e9 AS gb_scanned,
        BYTES_SCANNED / NULLIF(BYTES_SCANNED + BYTES_CACHED, 0) AS cache_miss_ratio,
        START_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND WAREHOUSE_NAME IS NOT NULL
        AND BYTES_SCANNED > 0
        AND BYTES_SCANNED / NULLIF(BYTES_SCANNED + BYTES_CACHED, 0) > ?
    ORDER BY cache_miss_ratio DESC
    LIMIT ?
    """
    return session.sql(query, params=[start_date, end_date, min_cache_ratio, limit]).to_pandas()

@st.cache_data(ttl=1800)
def get_user_stats(session, start_date, end_date):
    query = """
    SELECT 
        USER_NAME,
        COUNT(*) AS query_count,
        SUM(CREDITS_USED) AS total_credits,
        SUM(TOTAL_ELAPSED_TIME) / 1000 AS total_elapsed_seconds,
        AVG(CREDITS_USED) AS avg_credits_per_query,
        COUNT(DISTINCT WAREHOUSE_NAME) AS warehouses_used
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND USER_NAME IS NOT NULL
    GROUP BY USER_NAME
    ORDER BY total_credits DESC
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_user_activity_heatmap(session, start_date, end_date):
    query = """
    SELECT 
        USER_NAME,
        EXTRACT(HOUR FROM START_TIME) AS hour_of_day,
        EXTRACT(DOW FROM START_TIME) AS day_of_week,
        COUNT(*) AS query_count,
        SUM(CREDITS_USED) AS total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME BETWEEN ? AND ?
        AND USER_NAME IS NOT NULL
    GROUP BY USER_NAME, hour_of_day, day_of_week
    ORDER BY USER_NAME, day_of_week, hour_of_day
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_storage_trend(session, start_date, end_date):
    query = """
    SELECT 
        TO_DATE(USAGE_DATE) AS usage_date,
        AVG(AVERAGE_STAGE_BYTES) / 1e9 AS avg_stage_gb,
        AVG(AVERAGE_DATABASE_BYTES) / 1e9 AS avg_database_gb,
        AVG(AVERAGE_FAILSAFE_BYTES) / 1e9 AS avg_failsafe_gb,
        AVG(AVERAGE_STAGE_BYTES + AVERAGE_DATABASE_BYTES + AVERAGE_FAILSAFE_BYTES) / 1e9 AS avg_total_gb
    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
    WHERE USAGE_DATE BETWEEN ? AND ?
    GROUP BY TO_DATE(USAGE_DATE)
    ORDER BY usage_date
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()

@st.cache_data(ttl=1800)
def get_data_freshness(session, start_date, end_date):
    query = """
    SELECT 
        TABLE_CATALOG AS database_name,
        TABLE_SCHEMA AS schema_name,
        TABLE_NAME,
        TABLE_TYPE,
        LAST_ALTERED,
        ROW_COUNT,
        BYTES / 1e9 AS size_gb,
        DATEDIFF('day', LAST_ALTERED, CURRENT_TIMESTAMP()) AS days_since_last_change
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
    WHERE TABLE_CATALOG NOT IN ('SNOWFLAKE', 'UTIL_DB', 'INFORMATION_SCHEMA')
        AND DELETED IS NULL
        AND LAST_ALTERED BETWEEN ? AND ?
    ORDER BY LAST_ALTERED DESC
    """
    return session.sql(query, params=[start_date, end_date]).to_pandas()
```
