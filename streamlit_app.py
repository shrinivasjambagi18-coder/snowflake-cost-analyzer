import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

st.set_page_config(
    page_title="Snowflake Cost Analyzer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

session = get_active_session()

# --- Sidebar ---
st.sidebar.title("❄️ Snowflake Cost Analyzer")
st.sidebar.markdown("---")

default_end = date.today()
default_start = default_end - timedelta(days=30)
start_date = st.sidebar.date_input("Start Date", value=default_start)
end_date = st.sidebar.date_input("End Date", value=default_end)
credit_price = st.sidebar.number_input("Credit Price ($)", min_value=0.0, value=3.0, step=0.5, format="%.2f")

try:
    account_query = session.sql("SELECT CURRENT_ACCOUNT() as ACCOUNT, CURRENT_REGION() as REGION").collect()
    if account_query:
        account_name = account_query[0]["ACCOUNT"]
        region = account_query[0]["REGION"]
    else:
        account_name = "Unknown"
        region = "Unknown"
except:
    account_name = "Unknown"
    region = "Unknown"

st.sidebar.markdown(f"**Account:** {account_name}")
st.sidebar.markdown(f"**Region:** {region}")
st.sidebar.markdown("---")
refresh = st.sidebar.button("🔄 Refresh Data")

if refresh:
    st.cache_data.clear()

# --- Data Loading ---
@st.cache_data(ttl=300)
def load_warehouse_metering(start, end):
    query = f"""
    SELECT 
        WAREHOUSE_NAME,
        DATE(START_TIME) as USAGE_DATE,
        SUM(CREDITS_USED) as CREDITS_USED,
        SUM(CREDITS_USED_COMPUTE) as CREDITS_COMPUTE,
        SUM(CREDITS_USED_CLOUD_SERVICES) as CREDITS_CLOUD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= '{start}'
      AND START_TIME < DATEADD(day, 1, '{end}'::DATE)
    GROUP BY WAREHOUSE_NAME, DATE(START_TIME)
    ORDER BY USAGE_DATE DESC
    """
    return session.sql(query).to_pandas()

@st.cache_data(ttl=300)
def load_usage_history(start, end):
    query = f"""
    SELECT 
        WAREHOUSE_NAME,
        DATE(START_TIME) as USAGE_DATE,
        SUM(CREDITS_USED) as TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= '{start}'
      AND START_TIME < DATEADD(day, 1, '{end}'::DATE)
    GROUP BY WAREHOUSE_NAME, DATE(START_TIME)
    ORDER BY USAGE_DATE
    """
    return session.sql(query).to_pandas()

start_str = start_date.strftime('%Y-%m-%d')
end_str = end_date.strftime('%Y-%m-%d')

try:
    df_warehouse = load_warehouse_metering(start_str, end_str)
    df_usage = load_usage_history(start_str, end_str)
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    df_warehouse = pd.DataFrame()
    df_usage = pd.DataFrame()

# --- Calculations ---
if not df_warehouse.empty:
    total_credits = round(float(df_warehouse['CREDITS_USED'].sum()), 2)
    total_cost = round(total_credits * credit_price, 2)
    total_compute = round(float(df_warehouse['CREDITS_COMPUTE'].sum()), 2)
    total_cloud = round(float(df_warehouse['CREDITS_CLOUD'].sum()), 2)
    cloud_pct = round((total_cloud / total_credits * 100), 2) if total_credits > 0 else 0.0
    num_warehouses = int(df_warehouse['WAREHOUSE_NAME'].nunique())
    days_diff = (end_date - start_date).days or 1
    avg_daily_credits = round(total_credits / days_diff, 2)
else:
    total_credits = 0.0
    total_cost = 0.0
    total_compute = 0.0
    total_cloud = 0.0
    cloud_pct = 0.0
    num_warehouses = 0
    avg_daily_credits = 0.0

# --- Home Page ---
st.title("❄️ Snowflake Cost Analyzer")
st.markdown("---")

# KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Credits Used", value=f"{total_credits:,.2f}")
with col2:
    st.metric(label="Total Cost ($)", value=f"${total_cost:,.2f}")
with col3:
    st.metric(label="Avg Daily Credits", value=f"{avg_daily_credits:,.2f}")
with col4:
    st.metric(label="Active Warehouses", value=f"{num_warehouses}")

st.markdown("---")

# --- Credit Trend + Service Donut ---
col_trend, col_donut = st.columns([3, 1.2])

with col_trend:
    st.subheader("📈 Credit Usage Trend")
    if not df_usage.empty:
        df_trend = df_usage.groupby('USAGE_DATE')['TOTAL_CREDITS'].sum().reset_index()
        fig_trend = px.line(
            df_trend.sort_values('USAGE_DATE'),
            x='USAGE_DATE',
            y='TOTAL_CREDITS',
            markers=True,
            title="Daily Credit Consumption",
            labels={'USAGE_DATE': 'Date', 'TOTAL_CREDITS': 'Credits'},
            color_discrete_sequence=['#29B5E8']
        )
        fig_trend.update_layout(height=400)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data available for the selected date range.")

with col_donut:
    st.subheader("🍩 Service Breakdown")
    if total_credits > 0:
        fig_donut = go.Figure(data=[go.Pie(
            labels=['Compute', 'Cloud Services'],
            values=[total_compute, total_cloud],
            hole=0.4,
            marker=dict(colors=['#29B5E8', '#1A3E6B']),
            textinfo='label+percent'
        )])
        fig_donut.update_layout(
            height=400,
            title_text="Compute vs Cloud Services"
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No data to display.")

st.markdown("---")

# --- Top Warehouses ---
st.subheader("🏭 Top Warehouses by Credits")
if not df_warehouse.empty:
    wh_summary = df_warehouse.groupby('WAREHOUSE_NAME')['CREDITS_USED'].sum().reset_index()
    wh_summary = wh_summary.sort_values('CREDITS_USED', ascending=True)
    fig_wh = px.bar(
        wh_summary,
        x='CREDITS_USED',
        y='WAREHOUSE_NAME',
        orientation='h',
        title="Credits by Warehouse",
        color_discrete_sequence=['#29B5E8']
    )
    st.plotly_chart(fig_wh, use_container_width=True)

st.markdown("---")

# --- AI Insights ---
st.subheader("🤖 AI-Powered Insights")
if st.button("Generate Insights"):
    with st.spinner("Analyzing cost patterns..."):
        try:
            prompt = f"Analyze Snowflake cost data: Total Credits={total_credits}, Cost=${total_cost}, Compute={total_compute}, Cloud={total_cloud}, Cloud%={cloud_pct}, Warehouses={num_warehouses}, Avg Daily={avg_daily_credits}. Give 3-5 actionable cost optimization tips."
            safe_prompt = prompt.replace("'", "''")
            insights_df = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', '{safe_prompt}') as INSIGHTS").to_pandas()
            st.success("Insights generated!")
            st.markdown(insights_df.iloc[0]['INSIGHTS'])
        except Exception:
            st.markdown(f"""**Cost Optimization Recommendations:**

1. **Auto-Suspend**: Set warehouses to auto-suspend after 60 seconds of inactivity.
2. **Right-Size**: Review warehouse sizes — downsize underutilized warehouses.
3. **Cloud Services**: At {cloud_pct}% cloud services, review materialized views and result caching.
4. **Resource Monitors**: Set credit quotas and alerts on each warehouse.
5. **Query Optimization**: Review expensive queries in Query History to reduce compute usage.""")

# --- Footer ---
st.markdown("---")
st.caption(f"Data from SNOWFLAKE.ACCOUNT_USAGE | Period: {start_date} to {end_date}")
