```python
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import calendar

st.set_page_config(page_title="User Analysis", page_icon="ð¥", layout="wide")

st.title("ð¥ User Analysis Dashboard")
st.markdown("---")

# Initialize session state for data if not exists
if 'data' not in st.session_state:
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    
    data = {
        'date': [],
        'user_id': [],
        'activity_type': [],
        'duration_minutes': [],
        'country': []
    }
    
    countries = ['USA', 'UK', 'Canada', 'Germany', 'France', 'Australia', 'Japan', 'Brazil']
    activities = ['Login', 'View', 'Purchase', 'Comment', 'Like', 'Share', 'Search', 'Logout']
    
    for d in dates:
        num_users = np.random.randint(50, 200)
        for _ in range(num_users):
            data['date'].append(d)
            data['user_id'].append(f'U{np.random.randint(1000, 9999)}')
            data['activity_type'].append(np.random.choice(activities))
            data['duration_minutes'].append(np.random.randint(1, 120))
            data['country'].append(np.random.choice(countries))
    
    df = pd.DataFrame(data)
    df['weekday'] = df['date'].dt.day_name()
    df['month'] = df['date'].dt.month_name()
    df['hour'] = np.random.randint(0, 24, size=len(df))
    st.session_state.data = df

df = st.session_state.data.copy()

# Sidebar filters
st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date Range",
    value=(df['date'].min(), df['date'].max()),
    min_value=df['date'].min(),
    max_value=df['date'].max()
)

selected_countries = st.sidebar.multiselect(
    "Countries",
    options=df['country'].unique(),
    default=df['country'].unique()
)

selected_activities = st.sidebar.multiselect(
    "Activity Types",
    options=df['activity_type'].unique(),
    default=df['activity_type'].unique()
)

# Apply filters
if len(date_range) == 2:
    start_date, end_date = date_range
    df = df[(df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))]

if selected_countries:
    df = df[df['country'].isin(selected_countries)]

if selected_activities:
    df = df[df['activity_type'].isin(selected_activities)]

# Dashboard layout
col1, col2, col3 = st.columns(3)

with col1:
    total_users = df['user_id'].nunique()
    st.metric("Total Active Users", f"{total_users:,}")

with col2:
    total_activities = len(df)
    st.metric("Total Activities", f"{total_activities:,}")

with col3:
    avg_duration = df['duration_minutes'].mean()
    st.metric("Avg Session Duration", f"{avg_duration:.1f} min")

st.markdown("---")

# Top Users Chart
st.subheader("ð Top Active Users")
top_users = df['user_id'].value_counts().head(10).reset_index()
top_users.columns = ['User ID', 'Activity Count']

fig_top_users = px.bar(
    top_users,
    x='User ID',
    y='Activity Count',
    title="Top 10 Users by Activity Count",
    color='Activity Count',
    color_continuous_scale='Viridis',
    text='Activity Count'
)
fig_top_users.update_traces(textposition='outside')
fig_top_users.update_layout(
    xaxis_title="User ID",
    yaxis_title="Number of Activities",
    showlegend=False,
    height=400
)
st.plotly_chart(fig_top_users, use_container_width=True)

# Stats Table
st.subheader("ð User Statistics Summary")

# Aggregate statistics
user_stats = df.groupby('user_id').agg(
    Total_Activities=('activity_type', 'count'),
    Unique_Activities=('activity_type', 'nunique'),
    Avg_Duration=('duration_minutes', 'mean'),
    Last_Activity=('date', 'max')
).reset_index()

user_stats.columns = ['User ID', 'Total Activities', 'Unique Activity Types', 'Avg Duration (min)', 'Last Activity Date']
user_stats['Avg Duration (min)'] = user_stats['Avg Duration (min)'].round(1)
user_stats['Last Activity Date'] = user_stats['Last Activity Date'].dt.date

# Display top 20 users
st.dataframe(
    user_stats.sort_values('Total Activities', ascending=False).head(20),
    use_container_width=True,
    hide_index=True,
    column_config={
        'User ID': st.column_config.TextColumn('User ID', width='small'),
        'Total Activities': st.column_config.NumberColumn('Total Activities', format='%d'),
        'Unique Activity Types': st.column_config.NumberColumn('Unique Activity Types', format='%d'),
        'Avg Duration (min)': st.column_config.NumberColumn('Avg Duration (min)', format='%.1f'),
        'Last Activity Date': st.column_config.DateColumn('Last Activity Date')
    }
)

# Download button for stats
csv = user_stats.to_csv(index=False).encode('utf-8')
st.download_button(
    label="ð¥ Download User Statistics (CSV)",
    data=csv,
    file_name=f'user_statistics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
    mime='text/csv'
)

st.markdown("---")

# Activity Heatmap
st.subheader("ðï¸ Activity Heatmap")

# Prepare data for heatmap
df['hour'] = df['hour'].astype(int)
heatmap_data = df.groupby(['weekday', 'hour']).size().reset_index(name='count')

# Order weekdays
weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
heatmap_data['weekday'] = pd.Categorical(heatmap_data['weekday'], categories=weekday_order, ordered=True)
heatmap_data = heatmap_data.sort_values('weekday')

# Create pivot table
pivot_table = heatmap_data.pivot_table(
    values='count',
    index='weekday',
    columns='hour',
    fill_value=0
)

# Create heatmap
fig_heatmap = go.Figure(data=go.Heatmap(
    z=pivot_table.values,
    x=pivot_table.columns,
    y=pivot_table.index,
    colorscale='YlOrRd',
    text=pivot_table.values,
    texttemplate='%{text}',
    textfont={"size": 10},
    hovertemplate='Day: %{y}<br>Hour: %{x}<br>Activity Count: %{z}<extra></extra>'
))

fig_heatmap.update_layout(
    title="User Activity Heatmap (Day of Week vs Hour of Day)",
    xaxis_title="Hour of Day (24h)",
    yaxis_title="Day of Week",
    height=500,
    xaxis=dict(tickmode='linear', tick0=0, dtick=2),
    yaxis=dict(tickmode='array', tickvals=list(range(7)), ticktext=weekday_order)
)

st.plotly_chart(fig_heatmap, use_container_width=True)

# Monthly activity distribution
st.subheader("ð Monthly Activity Distribution")
monthly_data = df.groupby('month').size().reset_index(name='count')
month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
               'July', 'August', 'September', 'October', 'November', 'December']
monthly_data['month'] = pd.Categorical(monthly_data['month'], categories=month_order, ordered=True)
monthly_data = monthly_data.sort_values('month')

fig_monthly = px.line(
    monthly_data,
    x='month',
    y='count',
    title="Monthly User Activity",
    markers=True,
    line_shape='spline'
)
fig_monthly.update_layout(
    xaxis_title="Month",
    yaxis_title="Activity Count",
    height=400
)
st.plotly_chart(fig_monthly, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("*Data is updated in real-time. Use filters to customize the analysis.*")
```
