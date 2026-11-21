import streamlit as st

st.set_page_config(
    page_title="NBA Injury Rate Explorer",
    layout="wide"
)

st.title("🏀 NBA Injury Risk Explorer")
st.write("Explore NBA injury incidence using athlete-game exposure data.")


team_age_data = {
    "Atlanta Hawks": 808,
    "Boston Celtics": 864,
    "Brooklyn Nets": 838,
    "Charlotte Hornets": 870,
    "Chicago Bulls": 919,
    "Cleveland Cavaliers": 914,
    "Dallas Mavericks": 882,
    "Denver Nuggets": 857,
    "Detroit Pistons": 881,
    "Golden State Warriors": 946,
    "Houston Rockets": 861,
    "Indiana Pacers": 915,
    "LA Clippers": 900,
    "Los Angeles Lakers": 848,
    "Memphis Grizzlies": 932,
    "Miami Heat": 832,
    "Milwaukee Bucks": 894,
    "Minnesota Timberwolves": 856,
    "New Orleans Pelicans": 827,
    "New York Knicks": 824,
    "Oklahoma City Thunder": 917,
    "Orlando Magic": 925,
    "Philadelphia 76ers": 832,
    "Phoenix Suns": 887,
    "Portland Trail Blazers": 880,
    "Sacramento Kings": 886,
    "San Antonio Spurs": 926,
    "Toronto Raptors": 862,
    "Utah Jazz": 833,
    "Washington Wizards": 890
}

total_age = sum(team_age_data.values())



col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Teams Tracked", "30")

with col2:
    st.metric("Games Analyzed", "164")

with col3:
    st.metric("Total Age", total_age)



team_data = {
    "Golden State Warriors" : {
       "Regular season games" : 82,
       "Standard game length" : "240 minutes",
       "Games that went to overtime" : "2 (each +15 minutes)",
       "Total minutes played (season)":  "19,730 minutes",
        "Minutes per game (avg.)" : "240.61 minutes/game" ,
        "Total players rostered (season)"  : 1070 ,
        "Players rostered per game (avg.)" :  13.05,
        "Players entered individual games (AGE)" : 946,
        "Players entered per game (avg.)" : 11.54 ,
        "Injuries recorded" : 15
    },
    "LA Clippers" : 
      {
        "Regular season games" : 82,
       "Players entered individual games (AGE)" : 900,
        "Players entered per game (avg.)" : 10.98 ,
        "Injuries recorded" : 7,
        "Injury rate" : "7.78 per 1,000 AGE",
        "Standard game length" : "240 minutes",
        "Games that went to overtime" : 5,
        "Total minutes played (season)" : "19805 minutes",
        "Minutes per game (avg.)" : "241.52 minutes/game",
        "Total players rostered":  1064, 
        "Total player entered (season)": 900,
        "Players rostered per game" : 13.05,
        "Players entering per game": 10.98,
        "Injuries recorded" : 7
    }
}


st.divider()


# Filters
col1, col2, col3 = st.columns(3)

teams = [
    "All Teams",
    "Atlanta Hawks",
    "Boston Celtics",
    "Brooklyn Nets",
    "Washington Wizards"
    "Golden State Warriors"
    "LA Clippers"


]

seasons = [
    "2025-2026",
    "2024-2025"
]

metrics = [
    "Age method",
    "Games Missed",
    "Injury Rate",
    "Player Availability"
]


with col1:
    team = st.selectbox(
        "Team",
        teams
    )

with col2:
    season = st.selectbox(
        "Season",
        seasons
    )

with col3:
    metric = st.selectbox(
        "Metric",
        metrics
    )


st.write("**Selected Team:**", team)
st.write("**Selected Season:**", season)
st.write("**Selected Metric:**", metric)