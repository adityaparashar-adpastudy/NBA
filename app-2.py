import streamlit as st

st.set_page_config(
    page_title="NBA Injury Rate Explorer",
    layout="wide"
)

st.title("🏀 NBA Injury Risk Explorer")
st.write("Explore NBA injury incidence using athlete-game exposure data.")

# Top Metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Teams Tracked", "2")

with col2:
    st.metric("Games Analyzed", "164")

with col3:
    st.metric("Injury Rate (Age)", "3.2%")

st.divider()

# Filters
col1, col2, col3 = st.columns(3)

with col1:
    team = st.selectbox(
        "Team",
        ["All Teams", "Lakers"]
    )

with col2:
    Season = st.selectbox(
        "Season",
        ["2024-2025", "2025-2026"]
    )

with col3:
    metric = st.selectbox(
        "Metric",
        ["Age Methods", "Games Missed"]
    )

# Display selected values
st.write("**Selected Team:**", team)
st.write("**Selected Season:**", Season)
st.write("**Selected Metric:**", metric)