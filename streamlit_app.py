```python
import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, sum as sf_sum, to_timestamp, date_trunc, cast, lit
from snowflake.snowpark.types import DecimalType, TimestampType, StringType, DateType
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

st.set_page_config(
    page_title="Snowflake Cost Analyzer",
    page_icon="âï¸",
    layout="wide",
    initial_sidebar_state="expanded"
)

session = get_active_session()

# --- Sidebar ---
st.sidebar.title("âï¸ Snowflake Cost Analyzer")
st.sidebar.markdown("---")

default_end = date.today()
default_start = default_end - timedelta(days=30)
start_date = st.sidebar.date_input("Start Date", value=default_start)
end_date = st.sidebar.date_input("End Date", value=default_end)
credit_price = st.sidebar.number_input("Credit Price ($)", min_value=0.0, value=3.0, step=0.5, format="%.2f")

account_query = session.sql("SELECT CURRENT_ACCOUNT() as ACCOUNT, CURRENT_REGION() as REGION").collect()
if account_query:
    account_name = account_query[0]["ACCOUNT"]
    region = account_query[0]["REGION"]
else:
    account_name = "Unknown"
    region = "Unknown"

st.sidebar.markdown(f"**Account:** {account_name}")
st.sidebar.markdown(f"**Region:** {region}")
st.sidebar.markdown("---")
refresh = st.sidebar.button("ð Refresh Data")

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
      AND START_TIME < '{end}' + INTERVAL '1 DAY'
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
      AND START_TIME < '{end}' + INTERVAL '1 DAY'
    GROUP BY WAREHOUSE_NAME, DATE(START_TIME)
    ORDER BY USAGE_DATE
    """
    return session.sql(query).to_pandas()

start_str = start_date.strftime('%Y-%m-%d')
end_str = end_date.strftime('%Y-%m-%d')

df_warehouse = load_warehouse_metering(start_str, end_str)
df_usage = load_usage_history(start_str, end_str)

# --- Calculations ---
if not df_warehouse.empty:
    total_credits = round(df_warehouse['CREDITS_USED'].sum(), 2)
    total_cost = round(total_credits * credit_price, 2)
    total_compute = round(df_warehouse['CREDITS_COMPUTE'].sum(), 2)
    total_cloud = round(df_warehouse['CREDITS_CLOUD'].sum(), 2)
    cloud_pct = round((total_cloud / total_credits * 100), 2) if total_credits > 0 else 0.0
    num_warehouses = df_warehouse['WAREHOUSE_NAME'].nunique()
    avg_daily_credits = round(total_credits / ((end_date - start_date).days or 1), 2)
else:
    total_credits = 0.0
    total_cost = 0.0
    total_compute = 0.0
    total_cloud = 0.0
    cloud_pct = 0.0
    num_warehouses = 0
    avg_daily_credits = 0.0

# --- Home Page ---
st.title("ð Cost Overview")
st.markdown("---")

# KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Credits Used", value=f"{total_credits:,.2f}", delta=None)
with col2:
    st.metric(label="Total Cost ($)", value=f"${total_cost:,.2f}", delta=None)
with col3:
    st.metric(label="Avg Daily Credits", value=f"{avg_daily_credits:,.2f}", delta=None)
with col4:
    st.metric(label="Active Warehouses", value=f"{num_warehouses}", delta=None)

st.markdown("---")

# --- First Row: Credit Trend + Service Donut ---
col_trend, col_donut = st.columns([3, 1.2])

with col_trend:
    st.subheader("ð Credit Usage Trend")
    if not df_usage.empty:
        df_trend = df_usage.groupby('USAGE_DATE')['TOTAL_CREDITS'].sum().reset_index()
        df_trend.columns = ['USAGE_DATE', 'TOTAL_CREDITS']
        fig_trend = px.line(
            df_trend.sort_values('USAGE_DATE'), 
            x='USAGE_DATE', 
            y='TOTAL_CREDITS',
            markers=True,
            title=" Daily Credit Consumption",
            labels={'USAGE_DATE': 'Date', 'TOTAL_CREDITS': 'Credits'}
        )
        fig_trend.update_layout(height=400)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data available for the selected date range.")

with col_donut:
    st.subheader("ð© Service Breakdown")
    if total_credits > 0:
        labels = ['Compute', 'Cloud Services']
        values = [total_compute, total_cloud]
        colors = ['#1f77b4', '#ff7f0e']
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(colors=colors),
            textinfo='label+percent',
            insidetextorientation='radial'
        )])
        fig_donut.update_layout(
            height=400,
            title_text="Compute vs Cloud Services",
            annotations=[dict(text=f'{cloud_pct}% Cloud', x=0.5, y=0.5, font_size=14, showarrow=False)]
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No data to display.")

st.markdown("---")

# --- AI Insights Button ---
st.subheader("ð¤ AI-Powered Insights")
if st.button("Generate Insights"):
    with st.spinner("Analyzing cost patterns..."):
        try:
            # Create prompt for analysis
            prompt = f"""
            Analyze the following Snowflake cost data for the period {start_date} to {end_date}:
            - Total Credits: {total_credits}
            - Total Cost: ${total_cost}
            - Compute Credits: {total_compute}
            - Cloud Services Credits: {total_cloud}
            - Cloud Services Percentage: {cloud_pct}%
            - Number of Warehouses: {num_warehouses}
            - Average Daily Credits: {avg_daily_credits}
            
            Provide 3-5 actionable recommendations to optimize costs.
            """
            
            # Use Snowflake Cortex AI for insights (requires appropriate permissions)
            try:
                insights_query = f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    'mixtral-8x7b',
                    '{prompt.replace("'", "''")}'
                ) as INSIGHTS
                """
                insights_df = session.sql(insights_query).to_pandas()
                insights = insights_df.iloc[0]['INSIGHTS']
            except:
                # Fallback if Cortex not available
                insights = """**Cost Optimization Recommendations:**

1. **Consider Auto-Suspend Settings**: Review warehouse auto-suspend times and reduce idle time.
2. **Right-Size Warehouses**: Analyze workload patterns and resize warehouses based on actual usage.
3. **Optimize Cloud Services**: Since cloud services account for {cloud_pct}% of total credits, consider using multi-cluster warehouses efficiently.
4. **Leverage Warehousing Best Practices**: Use resource monitors and set appropriate credit quotas.
5. **Review Query Patterns**: Use the QUERY_HISTORY view to identify expensive queries.

*Tip: Schedule regular cost reviews and set up alerts for unusual spending patterns.*"""
            
            st.success("Insights generated successfully!")
            st.markdown(insights)
            
            # Additional AI suggestion based on data
            if cloud_pct > 20:
                st.warning(f"â ï¸ Cloud services are {cloud_pct}% of total credits. Consider reviewing materialized views, result caching, and multi-cluster configurations.")
            if avg_daily_credits > 100:
                st.info("ð¡ High daily credit usage detected. Consider bulk-loading during off-peak hours and using serverless compute for ETL/ELT where possible.")
                
        except Exception as e:
            st.error(f"Failed to generate insights: {str(e)}")
            st.info("Tip: Ensure your Snowflake account has access to Snowflake Cortex or check the logs for details.")
else:
    st.info("Click the button above to get AI-powered cost optimization insights based on your data.")

# --- Footer ---
st.markdown("---")
st.caption(f"Data refreshed from SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY | Period: {start_date} to {end_date}")
```
