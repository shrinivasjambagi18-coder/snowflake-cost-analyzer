import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ---------------------------
# Helper: Load or generate data
# ---------------------------
@st.cache_data
def load_query_data():
    """Return a sample DataFrame representing query intelligence data."""
    np.random.seed(42)
    n = 100
    now = datetime.now()
    query_ids = [f"q_{i:04d}" for i in range(n)]
    query_texts = [
        f"SELECT * FROM table_{i%10} WHERE col_{i%5} = {i} ORDER BY col_{i%7}"
        for i in range(n)
    ]
    query_previews = [qt[:80] + "..." if len(qt) > 80 else qt for qt in query_texts]
    start_times = [now - timedelta(hours=np.random.randint(0, 72)) for _ in range(n)]
    durations = np.random.exponential(scale=2.0, size=n)  # seconds
    bytes_scanned = np.random.randint(1e6, 1e10, size=n)
    spill_bytes = np.random.choice([0, 0, 0, 0, np.random.randint(1e3, 1e7)], size=n)
    cache_hit_ratio = np.random.uniform(0.0, 1.0, size=n)

    df = pd.DataFrame({
        "QUERY_ID": query_ids,
        "QUERY_TEXT": query_texts,
        "QUERY_PREVIEW": query_previews,
        "START_TIME": start_times,
        "DURATION_SEC": durations,
        "BYTES_SCANNED": bytes_scanned,
        "SPILL_BYTES": spill_bytes,
        "CACHE_HIT_RATIO": cache_hit_ratio,
    })
    return df

# ---------------------------
# Page configuration
# ---------------------------
st.set_page_config(page_title="Query Intelligence", layout="wide")
st.title("ð Query Intelligence")

df = load_query_data()

# ---------------------------
# Tab definitions
# ---------------------------
tab_labels = ["Slowest", "Most Scanned", "Spill", "Poor Cache"]
tabs = st.tabs(tab_labels)

# We'll store the current selection in session state
if "selected_query_id" not in st.session_state:
    st.session_state.selected_query_id = None

# ---------------------------
# Process each tab
# ---------------------------
with tabs[0]:
    st.subheader("Slowest Queries (by duration)")
    sorted_df = df.sort_values("DURATION_SEC", ascending=False)
    display_df = sorted_df[["QUERY_ID", "QUERY_PREVIEW", "DURATION_SEC"]].copy()
    display_df["DURATION_SEC"] = display_df["DURATION_SEC"].round(2)
    selected = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "QUERY_ID": "ID",
            "QUERY_PREVIEW": st.column_config.TextColumn("Query Preview", width="large"),
            "DURATION_SEC": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
        },
        key="slowest_table",
        on_select="rerun",
        selection_mode="single-row",
    )
    if selected["selection"]["rows"]:
        row_idx = selected["selection"]["rows"][0]
        st.session_state.selected_query_id = sorted_df.iloc[row_idx]["QUERY_ID"]

with tabs[1]:
    st.subheader("Most Scanned Queries")
    sorted_df = df.sort_values("BYTES_SCANNED", ascending=False)
    display_df = sorted_df[["QUERY_ID", "QUERY_PREVIEW", "BYTES_SCANNED"]].copy()
    display_df["BYTES_SCANNED"] = display_df["BYTES_SCANNED"].apply(
        lambda x: f"{x/1e9:.2f} GB"
    )
    selected = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "QUERY_ID": "ID",
            "QUERY_PREVIEW": st.column_config.TextColumn("Query Preview", width="large"),
            "BYTES_SCANNED": "Bytes Scanned",
        },
        key="most_scanned_table",
        on_select="rerun",
        selection_mode="single-row",
    )
    if selected["selection"]["rows"]:
        row_idx = selected["selection"]["rows"][0]
        st.session_state.selected_query_id = sorted_df.iloc[row_idx]["QUERY_ID"]

with tabs[2]:
    st.subheader("Queries with Spill")
    spill_df = df[df["SPILL_BYTES"] > 0].sort_values("SPILL_BYTES", ascending=False)
    if spill_df.empty:
        st.info("No queries with spill detected.")
    else:
        display_df = spill_df[["QUERY_ID", "QUERY_PREVIEW", "SPILL_BYTES"]].copy()
        display_df["SPILL_BYTES"] = display_df["SPILL_BYTES"].apply(
            lambda x: f"{x/1e6:.2f} MB"
        )
        selected = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "QUERY_ID": "ID",
                "QUERY_PREVIEW": st.column_config.TextColumn("Query Preview", width="large"),
                "SPILL_BYTES": "Spill",
            },
            key="spill_table",
            on_select="rerun",
            selection_mode="single-row",
        )
        if selected["selection"]["rows"]:
            row_idx = selected["selection"]["rows"][0]
            st.session_state.selected_query_id = spill_df.iloc[row_idx]["QUERY_ID"]

with tabs[3]:
    st.subheader("Poor Cache Hit Ratio (< 0.5)")
    poor_cache_df = df[df["CACHE_HIT_RATIO"] < 0.5].sort_values("CACHE_HIT_RATIO")
    if poor_cache_df.empty:
        st.info("No queries with poor cache hit ratio.")
    else:
        display_df = poor_cache_df[["QUERY_ID", "QUERY_PREVIEW", "CACHE_HIT_RATIO"]].copy()
        display_df["CACHE_HIT_RATIO"] = display_df["CACHE_HIT_RATIO"].round(2)
        selected = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "QUERY_ID": "ID",
                "QUERY_PREVIEW": st.column_config.TextColumn("Query Preview", width="large"),
                "CACHE_HIT_RATIO": st.column_config.NumberColumn("Cache Hit Ratio", format="%.2f"),
            },
            key="poor_cache_table",
            on_select="rerun",
            selection_mode="single-row",
        )
        if selected["selection"]["rows"]:
            row_idx = selected["selection"]["rows"][0]
            st.session_state.selected_query_id = poor_cache_df.iloc[row_idx]["QUERY_ID"]

# ---------------------------
# Display selected query preview (QUERY_PREVIEW only)
# ---------------------------
st.divider()
if st.session_state.selected_query_id:
    selected_row = df[df["QUERY_ID"] == st.session_state.selected_query_id]
    if not selected_row.empty:
        query_preview = selected_row.iloc[0]["QUERY_TEXT"]  # full query text
        st.subheader("Selected Query Full Text")
        st.code(query_preview, language="sql")
    else:
        st.error("Selected query not found in dataset.")
else:
    st.info("Select a query row from one of the tabs above to see its full SQL.")
