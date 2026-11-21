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
    },

    "Boston Celtics": {
        "Regular Season Games":82,
        "Standard Game length":"240 minutes",
        "Games that went to overtime":6,
        "Total minutes played (Season)":"19829.7 minutes",
        "minutes per game (avg)": "241.83 minutes/game",
        "total players restored (season)":1053,
        "players restored per game (avg)":12.84,
        "players entered individual games (AGE)":864,
        "players entered per game (avg)" :10.54,
        "injuries recorded" :26
    },

    "New York Knicks": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":8,
        "total minutes played (season)": "19880 minutes",
        "minutes per game (avg)":"242.44 minutes/game",
        "total players restored (season)":1061,
        "Players restored per game (avg)":12.94,
        "players entered individual games (AGE)":824,
        "players entered per game (avg)" :10.05,
        "injuries recorded" :13

    },

    "Philadelphia 76ers": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":5,
        "total minutes played (season)": "19804.9 minutes",
        "minutes per game (avg)":"241.52 minutes/game",
        "total players restored (season)":931,
        "Players restored per game (avg)":11.35,
        "players entered individual games (AGE)":832,
        "players entered per game (avg)" :10.15,
        "injuries recorded" :37

    },

    "Los Angeles Lakers": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":2,
        "total minutes played (season)": "19,729.9 minutes",
        "minutes per game (avg)":"240.61 minutes/game",
        "total players restored (season)":1029,
        "Players restored per game (avg)":12.55,
        "players entered individual games (AGE)":848,
        "players entered per game (avg)" :10.34,
        "injuries recorded" :12

    },

    "Minnesota Timberwolves": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":2,
        "total minutes played (season)": "19,830 minutes",
        "minutes per game (avg)":"241.83 minutes/game",
        "total players restored (season)":1123,
        "Players restored per game (avg)":13.70,
        "players entered individual games (AGE)":854,
        "players entered per game (avg)" :10.41,
        
    },

    "Miami Heat" :  {
        "Regular season games": 84,
        "Standard game length":"240 minutes",
        "games that went to overtime":9,
        "total minutes played (season)": "20,434.9 minutes",
        "minutes per game (avg)":"243.27 minutes/game",
        "total players restored (season)":1091,
        "Players restored per game (avg)":12.99,
        "players entered individual games (AGE)":852,
        "players entered per game (avg)" :10.14,
        
    },

    "Denver Nuggets":  {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":6,
        "total minutes played (season)": "19,854.9 minutes",
        "minutes per game (avg)":"242.13 minutes/game",
        "total players restored (season)":1114,
        "Players restored per game (avg)":13.59,
        "players entered individual games (AGE)":857,
        "players entered per game (avg)" :10.45,
        
    },

    "Oklahoma City Thunder": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":1,
        "total minutes played (season)": "19,705.0 minutes",
        "minutes per game (avg)":"240.30 minutes/game",
        "total players restored (season)":996,
        "Players restored per game (avg)":12.15,
        "players entered individual games (AGE)":917,
        "players entered per game (avg)" :11.18,
        
    },


    "Cleveland Cavaliers": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":2,
        "total minutes played (season)": "19,754.9 minutes",
        "minutes per game (avg)":"240.91 minutes/game",
        "total players restored (season)":1056,
        "Players restored per game (avg)":12.88,
        "players entered individual games (AGE)":914,
        "players entered per game (avg)" :11.15,
        
    },

    "Houston Rockets": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":4,
        "total minutes played (season)": "19,780.0 minutes",
        "minutes per game (avg)":"241.22 minutes/game",
        "total players restored (season)":1093,
        "Players restored per game (avg)":13.33,
        "players entered individual games (AGE)":860,
        "players entered per game (avg)" :10.49,
        
    },

    "Milwaukee Bucks": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":3,
        "total minutes played (season)": "19,754.8 minutes",
        "minutes per game (avg)":"240.91 minutes/game",
        "total players restored (season)":1127,
        "Players restored per game (avg)":13.74,
        "players entered individual games (AGE)":894,
        "players entered per game (avg)" :10.90,
        
    },

    "Phoenix Suns" : {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":6,
        "total minutes played (season)": "19,829.6 minutes",
        "minutes per game (avg)":"241.82 minutes/game",
        "total players restored (season)":1104,
        "Players restored per game (avg)":13.46,
        "players entered individual games (AGE)":887,
        "players entered per game (avg)" :10.82,
        
    },

    "Indiana Pacers": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":6,
        "total minutes played (season)": "19,854.8 minutes",
        "minutes per game (avg)":"242.13 minutes/game",
        "total players restored (season)":1098,
        "Players restored per game (avg)":13.39,
        "players entered individual games (AGE)":913,
        "players entered per game (avg)" :11.13,
        
    },


    "Atlanta Hawks": {
        "Regular season games": 84,
        "Standard game length":"240 minutes",
        "games that went to overtime":5,
        "total minutes played (season)": "20,285.0 minutes",
        "minutes per game (avg)":"241.49 minutes/game",
        "total players restored (season)":981,
        "Players restored per game (avg)":11.68,
        "players entered individual games (AGE)":827,
        "players entered per game (avg)" :9.85,
        
    },


    "Brooklyn Nets": {
            "Regular season games": 82,
            "Standard game length":"240 minutes",
            "games that went to overtime":4,
            "total minutes played (season)": "19,799.7 minutes",
            "minutes per game (avg)":"241.22 minutes/game",
            "total players restored (season)":927,
            "Players restored per game (avg)":11.30,
            "players entered individual games (AGE)":837,
            "players entered per game (avg)" :10.21,
            
    },


    "Charlotte Hornets": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":3,
        "total minutes played (season)": "19,754.8 minutes",
        "minutes per game (avg)":"240.91 minutes/game",
        "total players restored (season)":998,
        "Players restored per game (avg)":12.17,
        "players entered individual games (AGE)":870,
        "players entered per game (avg)" :10.61,
        
    },

    "Chicago Bulls": {
        "Regular season games": 83,
        "Standard game length":"240 minutes",
        "games that went to overtime":3,
        "total minutes played (season)": "19,995.0 minutes",
        "minutes per game (avg)":"240.90 minutes/game",
        "total players restored (season)":1084,
        "Players restored per game (avg)":13.06,
        "players entered individual games (AGE)":930,
        "players entered per game (avg)" :11.20,
        
    },

    "Detroit Pistons": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":5,
        "total minutes played (season)": "19,804.9 minutes",
        "minutes per game (avg)":"241.52 minutes/game",
        "total players restored (season)":1062,
        "Players restored per game (avg)":12.95,
        "players entered individual games (AGE)":881,
        "players entered per game (avg)" :10.74,
        
    },

    "Orlando Magic": {
        "Regular season games": 83,
        "Standard game length":"240 minutes",
        "games that went to overtime":1,
        "total minutes played (season)": "19,969.9 minutes",
        "minutes per game (avg)":"240.60 minutes/game",
        "total players restored (season)":1067,
        "Players restored per game (avg)":12.86,
        "players entered individual games (AGE)":938,
        "players entered per game (avg)" :11.30,
        
    },


    "Toronto Raptors": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":5,
        "total minutes played (season)": "19,805.0 minutes",
        "minutes per game (avg)":"241.50 minutes/game",
        "total players restored (season)":992,
        "Players restored per game (avg)":12.10,
        "players entered individual games (AGE)":862,
        "players entered per game (avg)" :10.51,
        
    },

   "Washington Wizards": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":2,
        "total minutes played (season)": "19,729.9 minutes",
        "minutes per game (avg)":"240.61 minutes/game",
        "total players restored (season)":1038,
        "Players restored per game (avg)":12.66,
        "players entered individual games (AGE)":889,
        "players entered per game (avg)" :10.84,
        
    },

   "Memphis Grizzlies": {
        "Regular season games": 84,
        "Standard game length":"240 minutes",
        "games that went to overtime":1,
        "total minutes played (season)": "20,184.6 minutes",
        "minutes per game (avg)":"240.29 minutes/game",
        "total players restored (season)":1082,
        "Players restored per game (avg)":12.88,
        "players entered individual games (AGE)":953,
        "players entered per game (avg)" :11.35,
        
    },

   "New Orleans Pelicans": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":3,
        "total minutes played (season)": "19,755.0 minutes",
        "minutes per game (avg)":"240.91 minutes/game",
        "total players restored (season)":925,
        "Players restored per game (avg)":11.28,
        "players entered individual games (AGE)":827,
        "players entered per game (avg)" :10.09,
        
    },

   "San Antonio Spurs": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":2,
        "total minutes played (season)": "19,729.8 minutes",
        "minutes per game (avg)":"240.61 minutes/game",
        "total players restored (season)":1084,
        "Players restored per game (avg)":13.22,
        "players entered individual games (AGE)":926,
        "players entered per game (avg)" :11.29,
        
    },

   "Utah Jazz": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":5,
        "total minutes played (season)": "19,805.0 minutes",
        "minutes per game (avg)":"241.52 minutes/game",
        "total players restored (season)":969,
        "Players restored per game (avg)":11.82,
        "players entered individual games (AGE)":833,
        "players entered per game (avg)" :10.16,
        
    },


   "Portland Trail Blazers": {
        "Regular season games": 82,
        "Standard game length":"240 minutes",
        "games that went to overtime":4,
        "total minutes played (season)": "19,779.9 minutes",
        "minutes per game (avg)":"241.22 minutes/game",
        "total players restored (season)":1047,
        "Players restored per game (avg)":12.77,
        "players entered individual games (AGE)":880,
        "players entered per game (avg)" :10.73,
        
    },


   "Sacramento Kings": {
        "Regular season games": 83,
        "Standard game length":"240 minutes",
        "games that went to overtime":7,
        "total minutes played (season)": "20,120.0 minutes",
        "minutes per game (avg)":"242.41 minutes/game",
        "total players restored (season)":1129,
        "Players restored per game (avg)":13.60,
        "players entered individual games (AGE)":896,
        "players entered per game (avg)" :10.80,
        
    },
    
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
    "Boston Celtics"
    "New York Knicks"
    "Philadelphia 76ers"
    "Los Angeles Lakers"
    "Minnesota Timberwolves"
    "Miami Heat"
    "Denver Nuggets"
    "Oklahoma City Thunder"
    "Cleveland Cavaliers"
    "Houston Rockets"
    "Milwaukee Bucks"
    "Phoenix Suns"
    "Indiana Pacers"
    "Atlanta Hawks"
    "Brooklyn Nets"
    "Charlotte Hornets"
    "Chicago Bulls"
    "Detroit Pistons"
    "Orlando Magic"
    "Toronto Raptors"
    "Washington Wizards"
    "Memphis Grizzlies"
    "New Orleans Pelicans"
    "San Antonio Spurs"
    "Utah Jazz"
    "Portland Trail Blazers"
    "Sacramento Kings"


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