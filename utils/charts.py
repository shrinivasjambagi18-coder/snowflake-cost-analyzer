import altair as alt
import pandas as pd

# Define the color palette
COLOR_PRIMARY = "#29B5E8"
COLOR_SECONDARY = "#1A3E6B"

def credit_trend_chart(df: pd.DataFrame, date_col: str = "date", credit_col: str = "credits") -> alt.Chart:
    """
    Create a line chart showing credit trend over time.
    
    Parameters
    ----------
    df : DataFrame
        Must contain date_col and credit_col.
    date_col : str, optional
        Name of the date column.
    credit_col : str, optional
        Name of the credit/amount column.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_line(color=COLOR_PRIMARY, point=True).encode(
        x=alt.X(f"{date_col}:T", title="Date"),
        y=alt.Y(f"{credit_col}:Q", title="Credits"),
        tooltip=[date_col, credit_col]
    ).properties(
        title="Credit Trend Over Time",
        width=600,
        height=400
    ).interactive()
    return chart

def service_type_donut(df: pd.DataFrame, category_col: str = "service_type", value_col: str = "count") -> alt.Chart:
    """
    Create a donut chart for service type distribution.
    
    Parameters
    ----------
    df : DataFrame
        Must contain category_col and value_col.
    category_col : str, optional
        Column with service type categories.
    value_col : str, optional
        Column with numeric values.
        
    Returns
    -------
    alt.Chart
    """
    # Compute angles for donut
    total = df[value_col].sum()
    df = df.copy()
    df["angle"] = df[value_col] / total * 360
    
    base = alt.Chart(df).encode(
        theta=alt.Theta("angle:Q", stack=True),
        color=alt.Color(f"{category_col}:N", scale=alt.Scale(
            range=[COLOR_PRIMARY, COLOR_SECONDARY, "#4A90D9", "#1C6B9E"]
        )),
        tooltip=[category_col, value_col]
    ).properties(
        width=300,
        height=300
    )
    
    pie = base.mark_arc(innerRadius=60, outerRadius=120)
    text = base.mark_text(radius=140, size=12).encode(text=f"{value_col}:Q")
    
    return pie + text

def warehouse_bar_chart(df: pd.DataFrame, category_col: str = "warehouse", value_col: str = "inventory") -> alt.Chart:
    """
    Create a horizontal bar chart for warehouse inventory.
    
    Parameters
    ----------
    df : DataFrame
        Must contain category_col and value_col.
    category_col : str, optional
        Warehouse names or categories.
    value_col : str, optional
        Numeric values (e.g., inventory count).
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_bar(color=COLOR_PRIMARY).encode(
        y=alt.Y(f"{category_col}:N", sort="-x", title="Warehouse"),
        x=alt.X(f"{value_col}:Q", title="Inventory"),
        tooltip=[category_col, value_col]
    ).properties(
        title="Warehouse Inventory",
        width=600,
        height=400
    )
    return chart

def warehouse_trend_chart(df: pd.DataFrame, date_col: str = "date", warehouse_col: str = "warehouse", 
                          value_col: str = "metric") -> alt.Chart:
    """
    Create a multi-line chart showing warehouse metrics over time.
    
    Parameters
    ----------
    df : DataFrame
        Must contain date_col, warehouse_col, and value_col.
    date_col : str
        Column with dates.
    warehouse_col : str
        Column identifying warehouses.
    value_col : str
        Column with metric values.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X(f"{date_col}:T", title="Date"),
        y=alt.Y(f"{value_col}:Q", title="Metric"),
        color=alt.Color(f"{warehouse_col}:N", scale=alt.Scale(
            range=[COLOR_PRIMARY, COLOR_SECONDARY, "#4A90D9", "#1C6B9E"]
        )),
        tooltip=[date_col, warehouse_col, value_col]
    ).properties(
        title="Warehouse Trend",
        width=700,
        height=400
    ).interactive()
    return chart

def idle_time_bar_chart(df: pd.DataFrame, category_col: str = "machine", value_col: str = "idle_time") -> alt.Chart:
    """
    Create a vertical bar chart for idle time per machine.
    
    Parameters
    ----------
    df : DataFrame
        Must contain category_col and value_col.
    category_col : str
        Machine names.
    value_col : str
        Idle time values.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_bar(color=COLOR_PRIMARY).encode(
        x=alt.X(f"{category_col}:N", title="Machine"),
        y=alt.Y(f"{value_col}:Q", title="Idle Time"),
        tooltip=[category_col, value_col]
    ).properties(
        title="Idle Time per Machine",
        width=600,
        height=400
    )
    return chart

def user_bar_chart(df: pd.DataFrame, user_col: str = "user", value_col: str = "actions") -> alt.Chart:
    """
    Create a horizontal bar chart for user activity.
    
    Parameters
    ----------
    df : DataFrame
        Must contain user_col and value_col.
    user_col : str
        Column with usernames.
    value_col : str
        Column with activity count.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_bar(color=COLOR_SECONDARY).encode(
        y=alt.Y(f"{user_col}:N", sort="-x", title="User"),
        x=alt.X(f"{value_col}:Q", title="Actions"),
        tooltip=[user_col, value_col]
    ).properties(
        title="User Activity",
        width=600,
        height=400
    )
    return chart

def user_heatmap_chart(df: pd.DataFrame, x_col: str = "hour", y_col: str = "day_of_week", 
                       value_col: str = "count") -> alt.Chart:
    """
    Create a heatmap of user activity by hour and day of week.
    
    Parameters
    ----------
    df : DataFrame
        Must contain x_col, y_col, and value_col.
    x_col : str
        Column for x-axis (e.g., hour).
    y_col : str
        Column for y-axis (e.g., day of week).
    value_col : str
        Column with counts or values.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X(f"{x_col}:O", title="Hour"),
        y=alt.Y(f"{y_col}:O", title="Day of Week"),
        color=alt.Color(f"{value_col}:Q", scale=alt.Scale(
            scheme="blues", range=[COLOR_PRIMARY, COLOR_SECONDARY]
        )),
        tooltip=[x_col, y_col, value_col]
    ).properties(
        title="User Activity Heatmap",
        width=400,
        height=300
    )
    return chart

def storage_area_chart(df: pd.DataFrame, area_col: str = "area", value_col: str = "usage") -> alt.Chart:
    """
    Create a bar chart for storage area usage.
    
    Parameters
    ----------
    df : DataFrame
        Must contain area_col and value_col.
    area_col : str
        Column with area names.
    value_col : str
        Column with usage values.
        
    Returns
    -------
    alt.Chart
    """
    chart = alt.Chart(df).mark_bar(color=COLOR_PRIMARY).encode(
        x=alt.X(f"{area_col}:N", title="Storage Area"),
        y=alt.Y(f"{value_col}:Q", title="Usage"),
        tooltip=[area_col, value_col]
    ).properties(
        title="Storage Area Usage",
        width=600,
        height=400
    )
    return chart
