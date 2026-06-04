```python
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Storage Analytics", layout="wide")

# --- TITLE ---
st.title("ð¦ Storage Analytics & Cost Estimation")
st.markdown("Monitor storage usage trends, key performance indicators, and projected costs.")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(datetime.now() - timedelta(days=30), datetime.now()),
    max_value=datetime.now()
)
cost_per_gb = st.sidebar.number_input("Cost per GB ($)", min_value=0.0, value=0.10, step=0.01)
forecast_days = st.sidebar.slider("Forecast Days", min_value=7, max_value=90, value=30)

# --- GENERATE SAMPLE DATA ---
# In production, replace with actual data source (e.g., database query)
def generate_storage_data(start_date, end_date):
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    # Simulate gradual increase with some noise
    base = 100  # GB
    trend = np.linspace(0, 20, len(dates))
    noise = np.random.normal(0, 2, len(dates))
    usage = base + trend + noise
    df = pd.DataFrame({'Date': dates, 'Storage_GB': usage.round(2)})
    return df

if len(date_range) == 2:
    start_dt, end_dt = date_range[0], date_range[1]
else:
    start_dt = date_range[0]
    end_dt = start_dt + timedelta(days=30)

df = generate_storage_data(start_dt, end_dt)

# --- KEY PERFORMANCE INDICATORS (KPIs) ---
current_usage = df['Storage_GB'].iloc[-1]
avg_daily_change = df['Storage_GB'].diff().mean()
total_increase = current_usage - df['Storage_GB'].iloc[0]
current_cost = current_usage * cost_per_gb
avg_daily_cost = avg_daily_change * cost_per_gb

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Current Storage", f"{current_usage:.2f} GB")
kpi2.metric("Avg Daily Change", f"{avg_daily_change:.2f} GB", delta=avg_daily_change)
kpi3.metric("Estimated Monthly Cost", f"${current_cost:.2f}")
kpi4.metric("Total Change (Period)", f"{total_increase:.2f} GB", delta=total_increase)

st.divider()

# --- STORAGE TREND CHART ---
st.subheader("ð Storage Usage Trend")

# Simple line chart
fig = px.line(df, x='Date', y='Storage_GB', markers=True,
              title=f"Storage Usage ({start_dt} to {end_dt})")
fig.update_layout(xaxis_title='Date', yaxis_title='Storage (GB)', hovermode='x unified')
st.plotly_chart(fig, use_container_width=True)

# --- FORECAST / COST ESTIMATE ---
st.subheader("ð° Cost Forecast & Projections")

# Simple linear regression for future cost estimate
from sklearn.linear_model import LinearRegression

# Prepare data
df['Days'] = (df['Date'] - df['Date'].min()).dt.days
X = df[['Days']].values
y = df['Storage_GB'].values

model = LinearRegression()
model.fit(X, y)

# Forecast future days
last_day = df['Days'].max()
future_days = np.arange(last_day+1, last_day+forecast_days+1).reshape(-1, 1)
forecast_storage = model.predict(future_days)
forecast_dates = [df['Date'].max() + timedelta(days=int(d)) for d in range(1, forecast_days+1)]

forecast_df = pd.DataFrame({
    'Date': forecast_dates,
    'Storage_GB': forecast_storage.round(2),
    'Type': 'Forecast'
})
historical_df = df.copy()
historical_df['Type'] = 'Historical'
combined_df = pd.concat([historical_df[['Date','Storage_GB','Type']], forecast_df])

# Plot forecast
fig2 = px.line(combined_df, x='Date', y='Storage_GB', color='Type',
               title=f"Storage Forecast (Next {forecast_days} Days)")
fig2.update_layout(xaxis_title='Date', yaxis_title='Storage (GB)')
st.plotly_chart(fig2, use_container_width=True)

# Cost estimate table
st.subheader("Projected Cost Summary")
col1, col2 = st.columns(2)

with col1:
    # Current period cost
    total_cost_period = df['Storage_GB'].sum() * cost_per_gb / len(df)  # average daily cost
    st.metric("Average Daily Cost (Historical)", f"${total_cost_period:.2f}")
    st.metric("Projected Monthly Cost (Next Month)", f"${forecast_storage.mean() * cost_per_gb:.2f}")

with col2:
    # Worst-case / best-case using forecast bounds (simple)
    next_month_avg = forecast_storage.mean()
    total_cost_forecast = next_month_avg * cost_per_gb * 30
    st.metric("Total Forecast Cost (30 days)", f"${total_cost_forecast:.2f}")

# Optional: display raw data
with st.expander("Show Raw Data"):
    st.dataframe(df)

# --- ADDITIONAL INSIGHTS (Optional) ---
st.divider()
st.subheader("ð Insights")
col1, col2, col3 = st.columns(3)

storage_growth_rate = ((df['Storage_GB'].iloc[-1] / df['Storage_GB'].iloc[0]) - 1) * 100
col1.info(f"Growth Rate (Period): {storage_growth_rate:.2f}%")

peak_usage = df['Storage_GB'].max()
peak_date = df.loc[df['Storage_GB'].idxmax(), 'Date'].date()
col2.info(f"Peak Usage: {peak_usage:.2f} GB on {peak_date}")

# Days until threshold (e.g., 200 GB)
threshold = st.number_input("Alert Threshold (GB)", min_value=0, value=200)
if forecast_storage[-1] >= threshold:
    exceed_day = None
    for i, val in enumerate(forecast_storage):
        if val >= threshold:
            exceed_day = forecast_dates[i]
            break
    if exceed_day:
        col3.warning(f"â ï¸ Will exceed {threshold} GB on {exceed_day.date()}")
    else:
        col3.success(f"â Below {threshold} GB in forecast period")
else:
    col3.success(f"â Below {threshold} GB in forecast period")
```
