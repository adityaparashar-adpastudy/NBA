"""
NBA Game Data - 4 Metrics
─────────────────────────
1. Injuries per game
2. Minutes played per game
3. Number of players who entered each game
4. Number of roster players eligible to enter each game

Usage:
  python3 basketball_reference_scraper_v2.py --team LAL --season 2025
  python3 basketball_reference_scraper_v2.py --game_id 202412250LAL --team LAL
  python3 basketball_reference_scraper_v2.py --roster LAL --season 2025
"""

import argparse
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup, Comment
from io import StringIO

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
DELAY = 3  # seconds between requests


# ── helpers ───────────────────────────────────────────────────────────────────

def get_soup(url):
    time.sleep(DELAY)
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def flatten_columns(df):
    """Flatten multi-level column headers from Basketball Reference tables."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            parts = [str(c) for c in col if not str(c).startswith("Unnamed")]
            new_cols.append(parts[-1] if parts else str(col[-1]))
        df.columns = new_cols
    return df


def find_table(soup, table_id):
    """Find table by ID, including inside HTML comments (BRef hides some tables)."""
    table = soup.find("table", id=table_id)
    if table:
        return table
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if table_id in comment:
            inner = BeautifulSoup(comment, "lxml")
            table = inner.find("table", id=table_id)
            if table:
                return table
    return None


def parse_minutes(mp_str):
    """Convert 'MM:SS' string to float minutes."""
    try:
        parts = str(mp_str).split(":")
        return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        return 0.0


# ── METRIC 4: ROSTER SIZE ─────────────────────────────────────────────────────

def get_roster(team, season):
    """Returns DataFrame of all players on the roster."""
    url = f"https://www.basketball-reference.com/teams/{team}/{season}.html"
    soup = get_soup(url)
    table = find_table(soup, "roster")
    if not table:
        return pd.DataFrame()
    df = pd.read_html(StringIO(str(table)))[0]
    df = flatten_columns(df)
    player_col = next((c for c in df.columns if "Player" in c), None)
    if player_col:
        df = df[df[player_col].notna() & (df[player_col] != "Player")]
    return df


# ── METRICS 1, 2, 3: BOXSCORE ─────────────────────────────────────────────────

def get_game_metrics(game_id, team):
    """
    Returns dict with all 4 metrics for a single game:
      - injured_out       : players listed as DNP (likely injury)
      - minutes_played    : total team minutes (240 regulation + 25 per OT)
      - players_entered   : players who logged any minutes
      - players_dnp       : players who did not play at all
      - overtime_periods  : number of OT periods (0 if none)
    """
    url = f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    soup = get_soup(url)

    table = find_table(soup, f"box-{team}-game-basic")
    if not table:
        return None

    df = pd.read_html(StringIO(str(table)))[0]
    df = flatten_columns(df)

    # Drop repeated header rows
    if "MP" in df.columns:
        df = df[df["MP"] != "MP"].copy()

    dnp_flags = ["Did Not Play", "Did Not Dress", "Not With Team"]
    played = df[df["MP"].notna() & ~df["MP"].isin(dnp_flags)].copy()
    dnp    = df[df["MP"].isin(dnp_flags)].copy()
    injured = dnp[dnp["MP"] == "Did Not Play"]  # most likely injury-related

    total_min = played["MP"].apply(parse_minutes).sum()
    ot_periods = max(0, round((total_min - 240) / 25)) if total_min > 241 else 0

    return {
        "minutes_played":   round(total_min, 1),
        "overtime_periods": ot_periods,
        "players_entered":  len(played),
        "players_dnp":      len(dnp),
        "injured_out":      len(injured),
    }


# ── GAME LOG (list of games for a team) ───────────────────────────────────────

def get_game_log(team, season):
    """Returns DataFrame with Date, Opp, W/L, and constructed game_id per game."""
    url = f"https://www.basketball-reference.com/teams/{team}/{season}/gamelog/"
    soup = get_soup(url)

    table = find_table(soup, "team_game_log_reg") or find_table(soup, "tgl_basic")
    if not table:
        print("ERROR: game log table not found.")
        return pd.DataFrame()

    df = pd.read_html(StringIO(str(table)))[0]
    df = flatten_columns(df)

    # Remove repeated header rows
    rk_col = next((c for c in df.columns if c in ("Rk", "G", "Gtm")), None)
    if rk_col:
        df = df[pd.to_numeric(df[rk_col], errors="coerce").notna()].copy()

    # Standardise Date column name
    if "Date" not in df.columns:
        date_col = next((c for c in df.columns if "Date" in str(c)), None)
        if date_col:
            df = df.rename(columns={date_col: "Date"})

    if "Date" in df.columns:
        df = df[df["Date"].notna() & (df["Date"] != "Date")].copy()

    opp_col = next((c for c in df.columns if c == "Opp"), None)
    wl_col  = next((c for c in df.columns if c in ("W/L", "Rslt")), None)

    # Home/away: BRef puts "@" in an unnamed column
    loc_col = None
    for c in df.columns:
        if "Unnamed" in str(c):
            vals = df[c].astype(str).str.strip().unique()
            if set(vals).issubset({"@", "", "nan"}):
                loc_col = c
                break

    # Build game IDs
    game_ids = []
    for _, row in df.iterrows():
        date_str = str(row.get("Date", "")).replace("-", "")
        if len(date_str) != 8:
            game_ids.append(None)
            continue
        opp = str(row.get(opp_col, "UNK")).strip() if opp_col else "UNK"
        is_away = loc_col and str(row.get(loc_col, "")).strip() == "@"
        home_team = opp if is_away else team
        game_ids.append(f"{date_str}0{home_team}")

    df["game_id"] = game_ids
    keep = [c for c in ["Date", opp_col, wl_col, "game_id"] if c and c in df.columns]
    return df[keep].copy()


# ── MAIN COMMANDS ─────────────────────────────────────────────────────────────

def cmd_game(game_id, team):
    """Print all 4 metrics for a single game."""
    team = team.upper()
    print(f"\nFetching metrics for game {game_id} ({team})...")

    metrics = get_game_metrics(game_id, team)
    if not metrics:
        print(f"ERROR: Could not find boxscore. Check game ID and team code.")
        return

    ot_note = f"  (+{metrics['overtime_periods']} OT)" if metrics["overtime_periods"] else ""

    print(f"\n── {team}  |  Game: {game_id} ──")
    print(f"  1. Injuries (DNP)               : {metrics['injured_out']} player(s)")
    print(f"  2. Total minutes played         : {metrics['minutes_played']} min{ot_note}")
    print(f"     (regulation = 240.0 min, each OT adds 25 min)")
    print(f"  3. Players who entered the game : {metrics['players_entered']}")
    print(f"  4. Players who did NOT play     : {metrics['players_dnp']}")


def cmd_team(team, season, max_games):
    """Print all 4 metrics across multiple games, saves CSV."""
    team = team.upper()

    print(f"\nFetching {team} roster ({season})...")
    roster_df = get_roster(team, season)
    roster_size = len(roster_df)
    print(f"Roster size: {roster_size} players (metric 4 baseline)")

    print(f"\nFetching {team} game log ({season})...")
    game_log = get_game_log(team, season)
    if game_log.empty:
        return

    rows = []
    for i, (_, row) in enumerate(game_log.iterrows()):
        if i >= max_games:
            break
        gid  = row.get("game_id")
        opp  = row.get("Opp", "?")
        wl   = row.get("W/L", row.get("Rslt", "?"))
        date = row.get("Date", "?")

        if not gid:
            continue

        print(f"\n  [{i+1}/{max_games}] {date} vs {opp} ({wl})  →  {gid}")
        metrics = get_game_metrics(gid, team)
        if not metrics:
            print("    Could not fetch boxscore, skipping.")
            continue

        rows.append({
            "Date":            date,
            "Opp":             opp,
            "W/L":             wl,
            "1. Injuries DNP": metrics["injured_out"],
            "2. Mins Played":  metrics["minutes_played"],
            "OT Periods":      metrics["overtime_periods"],
            "3. Entered Game": metrics["players_entered"],
            "Players DNP":     metrics["players_dnp"],
            "4. Roster Size":  roster_size,
        })

    if not rows:
        print("No data collected.")
        return

    summary = pd.DataFrame(rows)
    sep = "=" * 80
    print(f"\n\n{sep}")
    print(f"  {team} — {season} Season  ({len(summary)} games)")
    print(sep)
    print(summary.to_string(index=False))

    out = f"{team}_game_metrics_{season}.csv"
    summary.to_csv(out, index=False)
    print(f"\nSaved to: {out}")


def cmd_roster(team, season):
    """Print the full roster."""
    team = team.upper()
    print(f"\nFetching {team} roster ({season})...")
    df = get_roster(team, season)
    if df.empty:
        print("No roster data found.")
        return
    print(df.to_string(index=False))
    print(f"\nTotal: {len(df)} players  ← this is metric 4 for the season")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NBA 4-Metric Scraper",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  All 4 metrics for multiple games (saves CSV):
    python3 basketball_reference_scraper_v2.py --team LAL --season 2025

  All 4 metrics for one specific game:
    python3 basketball_reference_scraper_v2.py --game_id 202412250LAL --team LAL

  Roster only (metric 4 baseline):
    python3 basketball_reference_scraper_v2.py --roster LAL --season 2025
        """
    )
    parser.add_argument("--game_id",   help="Specific game ID  e.g. 202412250LAL")
    parser.add_argument("--team",      help="Team code         e.g. LAL, BOS, GSW")
    parser.add_argument("--roster",    help="Roster only       e.g. LAL")
    parser.add_argument("--season",    default="2025", help="Season end year (default 2025)")
    parser.add_argument("--max_games", type=int, default=10,
                        help="Max games for --team mode (default 10)")
    args = parser.parse_args()

    if args.game_id and args.team:
        cmd_game(args.game_id, args.team)
    elif args.team:
        cmd_team(args.team, args.season, args.max_games)
    elif args.roster:
        cmd_roster(args.roster, args.season)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
