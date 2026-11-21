"""
Basketball Reference Data Scraper
==================================
Downloads per-game data directly from basketball-reference.com via CSV export URLs.
No API key needed. No nba_api dependency.

Covers all 4 metrics:
  1. Injuries      — via Basketball Reference transactions log
  2. Minutes played — boxscore MP column, per team per game
  3. Players who entered — boxscore rows with non-blank minutes
  4. Roster eligible — team roster page for the season

Requirements:
    pip install pandas requests beautifulsoup4 lxml

Usage:
    python basketball_reference_scraper.py --team LAL --season 2024
    python basketball_reference_scraper.py --game_id 202412250LAL
    python basketball_reference_scraper.py --roster LAL --season 2024
    python basketball_reference_scraper.py --season_games LAL --season 2024
"""

import argparse
import time
import re
import sys
import requests
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup, Comment

BASE = "https://www.basketball-reference.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (research/educational use)",
    "Accept-Language": "en-US,en;q=0.9",
}


def safe_get(url: str, delay: float = 3.0) -> requests.Response:
    """Polite request with delay to respect Basketball Reference rate limits."""
    time.sleep(delay)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def parse_tables_from_page(url: str) -> dict[str, pd.DataFrame]:
    """
    Fetches a Basketball Reference page and returns all stat tables as DataFrames.
    Basketball Reference hides some tables inside HTML comments — this handles both.
    """
    resp = safe_get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    # Also parse tables hidden inside HTML comments (BRef does this for boxscores)
    comments = soup.find_all(string=lambda t: isinstance(t, Comment))
    for comment in comments:
        comment_soup = BeautifulSoup(comment, "lxml")
        for table in comment_soup.find_all("table"):
            soup.append(table)

    tables = {}
    for table in soup.find_all("table", id=True):
        table_id = table.get("id")
        try:
            df = pd.read_html(StringIO(str(table)), header=0)[0]
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ["_".join(c).strip("_") for c in df.columns]
            tables[table_id] = df
        except Exception:
            pass

    return tables


# ─────────────────────────────────────────────
# Metric 2 & 3: Minutes played + Players entered
# ─────────────────────────────────────────────

def get_boxscore(game_id: str) -> dict:
    """
    Scrapes a Basketball Reference boxscore page.

    game_id format: YYYYMMDD0TEAM  (home team, e.g. 202412250LAL)

    Returns:
        dict with keys per team:
          - players_played: DataFrame of players with minutes
          - players_dnp: DataFrame of DNP/DND players
          - total_minutes: float (team total)
          - overtime_periods: int
          - players_entered_count: int
    """
    url = f"{BASE}/boxscores/{game_id}.html"
    print(f"Fetching boxscore: {url}")
    tables = parse_tables_from_page(url)

    result = {"game_id": game_id, "teams": {}}

    # BRef boxscore table IDs follow pattern: box_{team_lower}_basic
    # e.g. box_lal_basic, box_bos_basic
    for table_id, df in tables.items():
        if not (table_id.startswith("box_") and table_id.endswith("_basic")):
            continue

        team_code = table_id.split("_")[1].upper()

        # Drop the multi-header separator rows BRef inserts
        df = df[df["MP"].notna()].copy()
        df = df[~df["MP"].isin(["MP", "Did Not Play", "Did Not Dress",
                                 "Not With Team", "Reserves"])]

        # Separate players who played vs DNP
        dnp_mask = df["MP"].str.contains("Did Not|Not With|Inactive",
                                          case=False, na=False)
        dnp_df = df[dnp_mask].copy()
        played_df = df[~dnp_mask].copy()

        # Remove the "Team Totals" row for individual analysis
        played_df = played_df[played_df["Starters"] != "Team Totals"]
        team_row = df[df["Starters"] == "Team Totals"]

        # Parse total minutes from the team totals row
        total_min = 0.0
        if not team_row.empty:
            mp_str = str(team_row["MP"].iloc[0])
            if ":" in mp_str:
                parts = mp_str.split(":")
                total_min = int(parts[0]) + int(parts[1]) / 60

        ot_periods = max(0, round((total_min - 240) / 25)) if total_min > 240 else 0

        result["teams"][team_code] = {
            "players_played": played_df[["Starters", "MP", "PTS", "TRB", "AST"]].rename(
                columns={"Starters": "player"}
            ),
            "players_dnp": dnp_df[["Starters"]].rename(columns={"Starters": "player"}),
            "total_minutes": round(total_min, 1),
            "overtime_periods": ot_periods,
            "players_entered_count": len(played_df),
            "players_dnp_count": len(dnp_df),
        }

    return result


# ─────────────────────────────────────────────
# Metric 4: Roster eligible
# ─────────────────────────────────────────────

def get_roster(team: str, season: int = 2025) -> pd.DataFrame:
    """
    Scrapes the season roster for a team from Basketball Reference.

    Args:
        team:   Team abbreviation as used by BRef (e.g. LAL, BOS, GSW)
        season: Season end year (2025 = 2024-25 season)

    Returns:
        DataFrame with player name, number, position, and contract notes
    """
    url = f"{BASE}/teams/{team.upper()}/{season}.html"
    print(f"Fetching roster: {url}")
    tables = parse_tables_from_page(url)

    if "roster" not in tables:
        raise ValueError(f"Roster table not found for {team} {season}. Check team abbreviation.")

    roster = tables["roster"].copy()
    # Drop empty rows
    roster = roster[roster["Player"].notna() & (roster["Player"] != "Player")]
    return roster[["No.", "Player", "Pos", "Ht", "Wt", "Birth Date", "Exp"]].reset_index(drop=True)


# ─────────────────────────────────────────────
# Metric 1: Injuries / transactions
# ─────────────────────────────────────────────

def get_injury_transactions(team: str, season: int = 2025) -> pd.DataFrame:
    """
    Scrapes the transactions log for a team, which includes IL activations/placements.
    This is the closest Basketball Reference gets to a formal injury log.

    Args:
        team:   BRef team abbreviation
        season: Season end year

    Returns:
        DataFrame of IL-related transactions with dates
    """
    url = f"{BASE}/friv/transactions.fcgi?utm_source=direct&utm_medium=Share&utm_campaign=ShareTool&tms[]={team.upper()}&year_id={season}"
    print(f"Fetching transactions: {url}")

    resp = safe_get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    records = []
    for p in soup.find_all("p", class_="transaction"):
        text = p.get_text(" ", strip=True)
        # Filter to injury/IL-related entries
        if any(kw in text.lower() for kw in [
            "injured list", "il", "injury", "placed", "activated",
            "out", "questionable", "doubtful", "surgery", "recover"
        ]):
            # Try to extract the date (usually a link at the start)
            date_tag = p.find("a")
            date_str = date_tag.get_text(strip=True) if date_tag else "Unknown"
            records.append({"date": date_str, "transaction": text})

    return pd.DataFrame(records)


# ─────────────────────────────────────────────
# Season-level: all game IDs for a team
# ─────────────────────────────────────────────

def get_season_game_ids(team: str, season: int = 2025) -> pd.DataFrame:
    """
    Scrapes the game log for a team to get all game IDs for the season.
    Game IDs can be passed to get_boxscore() for per-game analysis.

    Args:
        team:   BRef team abbreviation (e.g. LAL)
        season: Season end year

    Returns:
        DataFrame with date, opponent, result, and game_id (for boxscore URL)
    """
    url = f"{BASE}/teams/{team.upper()}/{season}/gamelog/"
    print(f"Fetching game log: {url}")
    tables = parse_tables_from_page(url)

    # BRef game log table id is "team_game_log_reg"
    if "team_game_log_reg" not in tables:
        raise ValueError(f"Game log table not found. Check team '{team}' and season '{season}'.")

    df = tables["team_game_log_reg"].copy()

    # Clean: remove header-repeat rows and preseason placeholders
    df.columns = [cols[-1] if all(str(c).startswith("Unnamed") for c in (cols if hasattr(cols,"__iter__") and not isinstance(cols,str) else [cols])) else [str(c) for c in (cols if hasattr(cols,"__iter__") and not isinstance(cols,str) else [cols]) if not str(c).startswith("Unnamed")][-1] for cols in df.columns]
    rk_col = next((c for c in df.columns if c.endswith("Rk")), None)
    date_col = next((c for c in df.columns if c.endswith("Date")), None)
    opp_col = next((c for c in df.columns if c.endswith("Opp") and "Opponent" not in c), None)
    wl_col = next((c for c in df.columns if "Rslt" in c), None)
    if rk_col:
        df = df[pd.to_numeric(df[rk_col], errors="coerce").notna()].copy()
    if date_col:
        df = df[df[date_col].notna() & (df[date_col] != "Date")].copy()
        df = df.rename(columns={date_col: "Date"})
    if opp_col:
        df = df.rename(columns={opp_col: "Opp"})
    if wl_col:
        df = df.rename(columns={wl_col: "W/L"})

    # Reconstruct game_id from date + home/away indicator + team
    # BRef boxscore URLs: /boxscores/YYYYMMDD0HOMETEAM.html
    def build_game_id(row):
        try:
            date_clean = str(row["Date"]).replace("-", "")
            # If @ in opponent it means away game, so opponent is home
            if str(row.get("", row.get("Unnamed: 5_level_0", ""))).strip() == "@":
                home = str(row["Opp"]).strip()
            else:
                home = team.upper()
            return f"{date_clean}0{home}"
        except Exception:
            return None

    # Handle column name variations across seasons
    away_col = next((c for c in df.columns if "Unnamed" in str(c) or c == ""), None)
    if away_col:
        df["game_id"] = df.apply(build_game_id, axis=1)
    else:
        df["game_id"] = None

    keep_cols = ["G", "Date", "game_id"]
    opp_col = "Opp" if "Opp" in df.columns else None
    wl_col = "W/L" if "W/L" in df.columns else None
    if opp_col: keep_cols.append(opp_col)
    if wl_col: keep_cols.append(wl_col)

    return df[keep_cols].dropna(subset=["Date"]).reset_index(drop=True)


# ─────────────────────────────────────────────
# Combined: season summary across all games
# ─────────────────────────────────────────────

def season_player_usage_summary(team: str, season: int = 2025, max_games: int = 10) -> pd.DataFrame:
    """
    Iterates over a team's games and builds a summary of:
      - players entered per game
      - total minutes per game
      - overtime periods

    Args:
        team:      BRef team abbreviation
        season:    Season end year
        max_games: Limit to avoid excessive requests (BRef rate limits aggressively)

    Returns:
        DataFrame with one row per game
    """
    games = get_season_game_ids(team, season)
    games = games[games["game_id"].notna()].head(max_games)

    rows = []
    for _, game_row in games.iterrows():
        game_id = game_row["game_id"]
        try:
            box = get_boxscore(game_id)
            team_data = box["teams"].get(team.upper(), {})
            rows.append({
                "date": game_row["Date"],
                "game_id": game_id,
                "opponent": game_row.get("Opp", ""),
                "result": game_row.get("W/L", ""),
                "players_entered": team_data.get("players_entered_count", None),
                "players_dnp": team_data.get("players_dnp_count", None),
                "total_minutes": team_data.get("total_minutes", None),
                "overtime_periods": team_data.get("overtime_periods", 0),
            })
        except Exception as e:
            print(f"  Skipping {game_id}: {e}")
            rows.append({"date": game_row["Date"], "game_id": game_id, "error": str(e)})

        time.sleep(3.5)  # Be polite — BRef blocks aggressive scrapers

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Basketball Reference Scraper")
    parser.add_argument("--game_id", type=str, help="BRef game ID, e.g. 202412250LAL")
    parser.add_argument("--team", type=str, help="Team abbreviation for season summary")
    parser.add_argument("--roster", type=str, help="Team abbreviation for roster lookup")
    parser.add_argument("--injuries", type=str, help="Team abbreviation for injury transactions")
    parser.add_argument("--season_games", type=str, help="Team abbreviation to list all game IDs")
    parser.add_argument("--season", type=int, default=2025, help="Season end year (default: 2025)")
    parser.add_argument("--max_games", type=int, default=10, help="Max games for season summary")
    args = parser.parse_args()

    if args.game_id:
        print(f"\n── Boxscore: {args.game_id} ──")
        box = get_boxscore(args.game_id)
        for team_code, data in box["teams"].items():
            print(f"\n  {team_code}")
            print(f"  Total minutes : {data['total_minutes']}")
            print(f"  OT periods    : {data['overtime_periods']}")
            print(f"  Players played: {data['players_entered_count']}")
            print(f"  DNP players   : {data['players_dnp_count']}")
            print(data["players_played"].to_string(index=False))

    elif args.roster:
        print(f"\n── {args.roster} Roster ({args.season}) ──")
        roster = get_roster(args.roster, args.season)
        print(roster.to_string(index=False))

    elif args.injuries:
        print(f"\n── {args.injuries} Injury Transactions ({args.season}) ──")
        df = get_injury_transactions(args.injuries, args.season)
        if df.empty:
            print("No injury transactions found.")
        else:
            print(df.to_string(index=False))

    elif args.season_games:
        print(f"\n── {args.season_games} Game IDs ({args.season}) ──")
        games = get_season_game_ids(args.season_games, args.season)
        print(games.to_string(index=False))

    elif args.team:
        print(f"\n── {args.team} Season Summary ({args.season}, max {args.max_games} games) ──")
        summary = season_player_usage_summary(args.team, args.season, args.max_games)
        print(summary.to_string(index=False))
        out_path = f"{args.team}_{args.season}_usage.csv"
        summary.to_csv(out_path, index=False)
        print(f"\nSaved to {out_path}")

    else:
        print("No arguments provided. Example usage:")
        print("  python basketball_reference_scraper.py --game_id 202412250LAL")
        print("  python basketball_reference_scraper.py --team LAL --season 2025")
        print("  python basketball_reference_scraper.py --roster LAL --season 2025")
        print("  python basketball_reference_scraper.py --injuries LAL --season 2025")
        print("  python basketball_reference_scraper.py --season_games LAL --season 2025")


if __name__ == "__main__":
    main()
