import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Overview", page_icon="ð")

st.title("ð Overview Dashboard")

if "usage_data" not in st.session_state:
    st.error("No data loaded. Please go to Data Load page to load data.")
    st.stop()

df = st.session_state.usage_data
if df.empty:
    st.warning("No data available.")
    st.stop()

# AI Insights
st.subheader("ð¤ AI Insights")
ai_insights = []
if "predictions" in st.session_state and st.session_state.predictions:
    pred = st.session_state.predictions
    if pred["expected_next_month"] > 0:
        ai_insights.append(f"ð **Cost Trend**: Expected next month cost: **${pred['expected_next_month']:.2f}** vs current: ${pred['current_month_cost']:.2f}")
        if pred["expected_next_month"] > pred["current_month_cost"] * 1.1:
            ai_insights.append("â ï¸ **Alert**: Significant cost increase predicted!")
        else:
            ai_insights.append("â **Stable**: Costs are within normal range.")
else:
    ai_insights.append("â¹ï¸ No predictions available. Use AI Prediction page for forecasting.")

# Anomaly detection
if "anomalies" in st.session_state and st.session_state.anomalies:
    anomalies = st.session_state.anomalies
    recent_anomalies = [a for a in anomalies if a["date"] >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
    if recent_anomalies:
        ai_insights.append(f"ð¨ **Anomalies detected**: {len(recent_anomalies)} anomalies in last 7 days (Avg: {recent_anomalies[0]['average']:.2f}, Actual: {recent_anomalies[0]['actual']:.2f})")
    else:
        ai_insights.append("â No recent anomalies.")
else:
    ai_insights.append("â¹ï¸ No anomaly detection data. Use AI Prediction page for analysis.")

# Data freshness
if "data_freshness" in st.session_state:
    df_fresh = st.session_state.data_freshness
    if df_fresh is not None and not df_fresh.empty:
        latest = df_fresh["last_loaded"].max()
        ai_insights.append(f"ð **Data Freshness**: Last loaded: {latest}")
        days_since = (datetime.now() - pd.to_datetime(latest)).days
        if days_since > 7:
            ai_insights.append("â ï¸ Data is over a week old, consider refreshing.")
        else:
            ai_insights.append("â Data is fresh.")
    else:
        ai_insights.append("â¹ï¸ Freshness data not available.")

st.info("\n\n".join(ai_insights))

# KPI Row
st.subheader("ð Period KPIs")
if "date_column" in st.session_state and "credit_column" in st.session_state:
    date_col = st.session_state.date_column
    credit_col = st.session_state.credit_column
    if date_col in df.columns and credit_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        total_credits = df[credit_col].sum()
        avg_daily = df[credit_col].mean()
        max_day = df.loc[df[credit_col].idxmax()] if not df.empty else None
        max_val = max_day[credit_col] if max_day is not None else 0
        max_date = max_day[date_col].strftime("%Y-%m-%d") if max_day is not None else "N/A"
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Credits", f"{total_credits:,.0f}")
        col2.metric("Avg Daily Credits", f"{avg_daily:,.0f}")
        col3.metric("Max Day", f"{max_val:,.0f}")
        col4.metric("Max Date", max_date)

# Daily Credits Trend
st.subheader("ð Daily Credits Trend")
if date_col in df.columns and credit_col in df.columns:
    daily = df.groupby(df[date_col].dt.date)[credit_col].sum().reset_index()
    daily.columns = ["date", "credits"]
    daily = daily.sort_values("date")
    st.bar_chart(daily.set_index("date"), use_container_width=True)

# Service Donut
st.subheader("ð© Service Distribution")
if "service_column" in st.session_state:
    service_col = st.session_state.service_column
    if service_col in df.columns and credit_col in df.columns:
        service_credits = df.groupby(service_col)[credit_col].sum().reset_index()
        # Prepare donut chart using Altair
        try:
            import altair as alt
            chart = alt.Chart(service_credits).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field=credit_col, type="quantitative"),
                color=alt.Color(field=service_col, type="nominal"),
                tooltip=[service_col, credit_col]
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            # Fallback to simple pie
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            ax.pie(service_credits[credit_col], labels=service_credits[service_col], autopct='%1.1f%%')
            ax.axis('equal')
            st.pyplot(fig)
    else:
        st.info("Service column not found.")
else:
    st.info("Service column not configured.")

st.caption(f"Data last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
