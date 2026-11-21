"""
NBA Team → Basketball-Reference Code Lookup
Use this to loop scrapers (game logs, rosters, etc.) across all 30 teams.

Basketball-Reference team page pattern:
    https://www.basketball-reference.com/teams/{CODE}/{YEAR}.html

    YEAR = the year the season ENDS (e.g. 2024-25 season -> 2025)
"""

NBA_TEAM_CODES = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BRK",          # not BKN
    "Charlotte Hornets": "CHO",      # not CHA
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "LA Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHO",           # not PHX
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


def team_url(team_name: str, season_end_year: int) -> str:
    """
    Build the Basketball-Reference team-season URL.
    e.g. team_url("Golden State Warriors", 2025)
         -> https://www.basketball-reference.com/teams/GSW/2025.html
    """
    code = NBA_TEAM_CODES[team_name]
    return f"https://www.basketball-reference.com/teams/{code}/{season_end_year}.html"


if __name__ == "__main__":
    # quick sanity check / example loop
    for name, code in NBA_TEAM_CODES.items():
        print(f"{name:28s} {code:5s} -> {team_url(name, 2025)}")
