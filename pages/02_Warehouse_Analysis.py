```python
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest

# ============================================================
# DATA LOADING (simulated warehouse data)
# ============================================================
@st.cache_data
def load_warehouse_data():
    """Generate synthetic warehouse data for demonstration."""
    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", end="2025-03-31", freq="D")
    n = len(dates)

    data = {
        "date": dates,
        "daily_orders": np.random.poisson(120, n) + np.random.randint(-10, 10, n),
        "inbound_qty": np.random.poisson(250, n) + np.random.randint(-20, 20, n),
        "outbound_qty": np.random.poisson(200, n) + np.random.randint(-15, 15, n),
        "inventory_level": np.cumsum(
            np.random.poisson(250, n) - np.random.poisson(200, n)
        ) + 5000,
        "idle_workers": np.random.randint(0, 15, n),
        "available_slots": np.random.randint(50, 200, n),
    }
    df = pd.DataFrame(data)
    df["slot_utilization"] = 100 * (1 - df["available_slots"] / 300)
    df["weekday"] = df["date"].dt.day_name()
    df["month"] = df["date"].dt.month_name()
    return df

# ============================================================
# AI INSIGHT FUNCTIONS
# ============================================================
def detect_anomalies(df, col="daily_orders"):
    """Isolation Forest to flag unusual daily orders."""
    model = IsolationForest(contamination=0.05, random_state=42)
    X = df[[col]].values
    df["anomaly"] = model.fit_predict(X)  # -1 = anomaly
    return df

def forecast_trend(df, col="daily_orders", days=7):
    """Simple linear regression forecast for next 'days' days."""
    last_date = df["date"].max()
    X = np.arange(len(df)).reshape(-1, 1)
    y = df[col].values
    model = LinearRegression()
    model.fit(X, y)
    future_X = np.arange(len(df), len(df) + days).reshape(-1, 1)
    pred = model.predict(future_X)
    future_dates = [last_date + timedelta(days=i+1) for i in range(days)]
    return future_dates, pred

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(page_title="Warehouse Analysis", layout="wide")
st.title("ð­ Warehouse Operations Analytics")
st.markdown("Gain insights into warehouse performance, daily trends, idle analysis, and sizing signals powered by AI.")

# Load data
df = load_warehouse_data()
df_with_anomalies = detect_anomalies(df)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "ð Summary",
    "ð Daily Trend",
    "â³ Idle Analysis",
    "ð¦ Sizing Signals"
])

# ---------- TAB 1: Summary ----------
with tab1:
    st.header("Warehouse Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Orders (period)", f"{df['daily_orders'].sum():,}")
    with col2:
        avg_inv = int(df["inventory_level"].mean())
        st.metric("Avg Inventory Level", f"{avg_inv:,}")
    with col3:
        avg_orders = int(df["daily_orders"].mean())
        st.metric("Avg Daily Orders", f"{avg_orders}")
    with col4:
        avg_idle = int(df["idle_workers"].mean())
        st.metric("Avg Idle Workers", f"{avg_idle}")

    st.subheader("AI Insight â Anomaly Detection")
    anomalies = df_with_anomalies[df_with_anomalies["anomaly"] == -1]
    if not anomalies.empty:
        st.warning(f"ð {len(anomalies)} anomalous days detected in daily orders. Check dates: {anomalies['date'].dt.strftime('%Y-%m-%d').tolist()}")
    else:
        st.success("No anomalies detected in daily orders.")

    # pie chart: weekday order distribution
    weekday_orders = df.groupby("weekday")["daily_orders"].sum().reset_index()
    fig_pie = px.pie(weekday_orders, values="daily_orders", names="weekday",
                     title="Order Distribution by Weekday")
    st.plotly_chart(fig_pie, use_container_width=True)

# ---------- TAB 2: Daily Trend ----------
with tab2:
    st.header("Daily Operational Trends")

    # choose metric
    metric = st.selectbox("Select Metric", ["daily_orders", "inbound_qty", "outbound_qty", "inventory_level"])

    # line chart
    fig_line = px.line(df, x="date", y=metric, title=f"{metric.replace('_',' ').title()} Over Time")
    st.plotly_chart(fig_line, use_container_width=True)

    # forecast
    st.subheader("AI Insight â 7-Day Forecast")
    future_dates, pred = forecast_trend(df, col=metric, days=7)
    forecast_df = pd.DataFrame({"date": future_dates, "forecast": pred})
    fig_forecast = go.Figure()
    fig_forecast.add_trace(go.Scatter(x=df["date"], y=df[metric], mode="lines", name="Historical"))
    fig_forecast.add_trace(go.Scatter(x=forecast_df["date"], y=forecast_df["forecast"], mode="lines+markers", name="Forecast", line=dict(dash="dot")))
    fig_forecast.update_layout(title=f"Forecast for {metric.replace('_',' ').title()}")
    st.plotly_chart(fig_forecast, use_container_width=True)

# ---------- TAB 3: Idle Analysis ----------
with tab3:
    st.header("Idle Worker & Resource Analysis")

    # histogram of idle workers
    fig_hist = px.histogram(df, x="idle_workers", nbins=20, title="Distribution of Idle Workers per Day")
    st.plotly_chart(fig_hist, use_container_width=True)

    # correlation with orders
    fig_scatter = px.scatter(df, x="daily_orders", y="idle_workers", trendline="ols",
                             title="Idle Workers vs. Daily Orders")
    st.plotly_chart(fig_scatter, use_container_width=True)

    # AI insight: high idle days
    high_idle = df[df["idle_workers"] > df["idle_workers"].quantile(0.75)]
    st.info(f"ð High idle days (>75th percentile): {len(high_idle)} days identified. Consider crossâtraining or reallocation.")

# ---------- TAB 4: Sizing Signals ----------
with tab4:
    st.header("Warehouse Sizing & Capacity Signals")

    # slot utilization over time
    fig_util = px.line(df, x="date", y="slot_utilization", title="Slot Utilization (%)")
    fig_util.add_hline(y=85, line_dash="dash", line_color="red", annotation_text="Threshold 85%")
    st.plotly_chart(fig_util, use_container_width=True)

    # inventory vs available slots
    fig_scatter2 = px.scatter(df, x="inventory_level", y="available_slots",
                              color="slot_utilization", size="daily_orders",
                              title="Inventory vs Available Slots (size = orders)")
    st.plotly_chart(fig_scatter2, use_container_width=True)

    # AI insight: recommend expansion
    recent_util = df.tail(30)["slot_utilization"].mean()
    if recent_util > 80:
        st.warning(f"â ï¸ Average slot utilization in last 30 days is **{recent_util:.1f}%**. Consider expanding capacity.")
    else:
        st.success(f"â Average slot utilization in last 30 days is **{recent_util:.1f}%**. Capacity is adequate.")

# ============================================================
# SIDEBAR (optional additional info)
# ============================================================
st.sidebar.header("Data Overview")
st.sidebar.dataframe(df.describe())
st.sidebar.markdown("---")
st.sidebar.info("This is simulated data for demonstration. Replace with real warehouse data.")
```
