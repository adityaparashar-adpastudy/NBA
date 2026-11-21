"""
NBA Per-Game Roster Availability Scraper -- Windows Compatible

Source:
    Basketball-Reference.com (Free, No API Required)

Output:
    One CSV containing:

        (A) Available Players
        (B) Players Who Entered the Game
        (C) In-Game Injuries (blank for manual entry)

Requirements:

    pip install requests pandas beautifulsoup4 lxml

Run:

    python clippersscraper_windows.py
"""

import argparse
import os
import time
from io import StringIO
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

TEAM_CODE = "LAC"
TEAM_NAME = "LA Clippers"

# Save CSV in current working directory.
# Change this if you want another location.
OUTPUT_DIR = os.getcwd()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.basketball-reference.com/",
}

# Be polite to Basketball Reference.
# Wait 8 seconds between requests (bumped up from 4 to reduce
# the chance of getting rate-limited / blocked).
DELAY = 8


# ---------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------

def get_soup(url: str) -> BeautifulSoup:
    """
    Download a webpage and return a BeautifulSoup object.
    """

    time.sleep(DELAY)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "lxml"
    )


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Basketball Reference sometimes uses multi-level
    column headers.

    Example:

        ("Basic", "MP")

    becomes

        MP
    """

    if isinstance(df.columns, pd.MultiIndex):

        new_columns = []

        for column in df.columns:

            parts = [
                str(item)
                for item in column
                if not str(item).startswith("Unnamed")
            ]

            if parts:
                new_columns.append(parts[-1])
            else:
                new_columns.append(str(column[-1]))

        df.columns = new_columns

    return df


def find_table(
    soup: BeautifulSoup,
    table_id: str
) -> Optional[BeautifulSoup]:
    """
    Locate a table by ID.

    Basketball Reference hides many tables
    inside HTML comments.

    This function searches:

        1. Visible HTML
        2. HTML comments
    """

    table = soup.find(
        "table",
        id=table_id
    )

    if table:
        return table

    for comment in soup.find_all(
        string=lambda text: isinstance(text, Comment)
    ):

        if table_id not in comment:
            continue

        inner_soup = BeautifulSoup(
            comment,
            "lxml"
        )

        table = inner_soup.find(
            "table",
            id=table_id
        )

        if table:
            return table

    return None


def parse_minutes(mp_value) -> float:
    """
    Convert a minutes string like

        34:27

    into

        34.45
    """

    try:

        minutes, seconds = str(mp_value).split(":")

        return (
            int(minutes)
            + int(seconds) / 60
        )

    except Exception:

        return 0.0


# ---------------------------------------------------------------------
# GAME LOG
# ---------------------------------------------------------------------

def get_game_log(
    team: str,
    season: int
) -> pd.DataFrame:
    """
    Download the regular season game log.

    Also creates the Basketball Reference game_id
    needed to access each box score.
    """

    url = (
        f"https://www.basketball-reference.com/"
        f"teams/{team}/{season}/gamelog/"
    )

    print(f"\nFetching game log...\n{url}")

    soup = get_soup(url)

    # Basketball Reference has changed
    # this table ID over time.
    table = (
        find_table(soup, "team_game_log_reg")
        or
        find_table(soup, "tgl_basic")
    )

    if table is None:

        print("\nERROR: Game log table not found.")

        print("\nTables found on page:")

        for tbl in soup.find_all("table"):
            print("   ", tbl.get("id"))

        return pd.DataFrame()

    df = pd.read_html(
        StringIO(str(table))
    )[0]

    # ------------------------------------------------------------------
    # Basketball Reference repeats the header row as a literal data row
    # every ~20 rows (for readability when scrolling the real webpage).
    # These repeat-header rows contain text like "Rk", "G", "Date" mixed
    # into the data, which breaks the column content-detection below
    # (e.g. a literal "Opp" text value isn't a valid team code, and
    # confuses the "all values match this pattern" checks). This didn't
    # show up in the 3-game test because there weren't enough rows to
    # trigger a repeat -- but it does with a full 82+ game season.
    #
    # Fix: drop any row where the "G" column isn't a plain integer,
    # BEFORE doing column detection, so junk rows never factor in.
    # ------------------------------------------------------------------

    if "G" in df.columns:

        df = df[
            df["G"].apply(lambda value: str(value).strip().isdigit())
        ].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Capture the home/away marker AND the opponent team code BEFORE
    # flattening, using column POSITION and VALUE PATTERNS rather than
    # column names.
    #
    # Basketball Reference's exact table layout has shifted over time,
    # so this checks for it in two possible forms:
    #
    #   Form A (combined): one column holds BOTH pieces of info in one
    #                       cell, e.g. "PHO" for a home game or "@PHO"
    #                       for an away game.
    #   Form B (split):    two separate columns -- one with only ""
    #                       or "@" (location), one with only the plain
    #                       team code (e.g. "PHO").
    #
    # It also has a duplicate-named "Opp" column holding the opponent's
    # point total (not the team code) -- numeric, so it never matches
    # either pattern below and is safely ignored.
    # ------------------------------------------------------------------

    import re

    combined_pattern = re.compile(r"^(@?)([A-Z]{2,4})$")

    loc_marker_values = None
    opponent_values = None

    for i in range(len(df.columns)):

        series = df.iloc[:, i]

        values = set(
            str(value).strip()
            for value in series.dropna().unique()
        )

        non_empty = values - {"", "nan"}

        if not non_empty:
            continue

        # --- Form A: combined "@PHO" / "PHO" style column ---
        if opponent_values is None:

            matches = [
                bool(combined_pattern.match(value))
                for value in non_empty
            ]

            if matches and (sum(matches) / len(matches)) >= 0.9:

                stripped = series.astype(str).str.strip()

                loc_marker_values = stripped.apply(
                    lambda v: "@" if v.startswith("@") else ""
                )

                opponent_values = stripped.str.replace(
                    "@", "", regex=False
                ).str.upper()

                continue

        # --- Form B: separate home/away marker column ("" / "@" only) ---
        if values.issubset({"", "@", "nan"}) and loc_marker_values is None:

            loc_marker_values = series.astype(str).str.strip()

            continue

        # --- Form B: separate opponent team code column ---
        if opponent_values is None:

            matches = [
                2 <= len(value) <= 4 and value.isalpha() and value.isupper()
                for value in non_empty
            ]

            if matches and (sum(matches) / len(matches)) >= 0.9:

                opponent_values = series.astype(str).str.strip().str.upper()

    df["_loc_marker"] = (
        loc_marker_values.values
        if loc_marker_values is not None
        else ""
    )

    df["_opponent"] = (
        opponent_values.values
        if opponent_values is not None
        else ""
    )

    df = flatten_columns(df)

    # Remove playoff summary rows
    if "G" in df.columns:

        df = df[
            df["G"].apply(
                lambda value: str(value).isdigit()
            )
        ].copy()

    game_ids = []

    for _, row in df.iterrows():

        try:

            date_raw = str(
                row.get("Date", "")
            )

            date_fmt = date_raw.replace("-", "")

            home_away = str(
                row.get("_loc_marker", "")
            ).strip()

            opponent = str(
                row.get("_opponent", "")
            ).upper().strip()

            if home_away == "@":

                game_id = (
                    f"{date_fmt}0{opponent}"
                )

            else:

                game_id = (
                    f"{date_fmt}0{team}"
                )

            game_ids.append(game_id)

        except Exception:

            game_ids.append(None)

    df["game_id"] = game_ids

    return df
# ---------------------------------------------------------------------
# BOXSCORE METRICS
# ---------------------------------------------------------------------

def get_game_metrics(
    game_id: str,
    team: str
) -> Optional[dict]:
    """
    Download one game's box score and calculate:

        (A) Available Players
        (B) Players Who Entered the Game
        (C) In-Game Injuries (left blank)

    Returns a dictionary containing these metrics.
    """

    url = (
        f"https://www.basketball-reference.com/"
        f"boxscores/{game_id}.html"
    )

    soup = get_soup(url)

    table_id = f"box-{team}-game-basic"

    table = find_table(
        soup,
        table_id
    )

    if table is None:

        print(
            f"[ERROR] Box score table not found "
            f"for {game_id}"
        )

        return None

    df = pd.read_html(
        StringIO(str(table))
    )[0]

    df = flatten_columns(df)

    # ----------------------------------------------------------
    # Counters
    # ----------------------------------------------------------

    available = 0
    entered = 0
    minutes_played_total = 0.0

    # ----------------------------------------------------------
    # Examine every player
    # ----------------------------------------------------------

    for _, row in df.iterrows():

        mp_raw = str(
            row.get("MP", "")
        ).strip().lower()

        # ------------------------------------------------------
        # Player dressed but never entered
        #
        # Example:
        # Did Not Play
        # ------------------------------------------------------

        if mp_raw == "did not play":

            available += 1

            continue

        # ------------------------------------------------------
        # Player unavailable
        #
        # Do NOT count these players.
        # ------------------------------------------------------

        if mp_raw in (

            "did not dress",

            "inactive",

            "not with team",

            "player suspended",

        ):

            continue

        # ------------------------------------------------------
        # Player entered the game
        #
        # Minutes always appear as:
        #
        #     35:12
        #     08:44
        # ------------------------------------------------------

        if ":" in mp_raw:

            available += 1

            entered += 1

            minutes_played_total += parse_minutes(
                mp_raw
            )

    # ----------------------------------------------------------
    # Return metrics
    # ----------------------------------------------------------

    return {

        "(A) Available": available,

        "(B) Entered Game": entered,

        "(C) In-Game Injuries": "",

        "minutes_played": round(
            minutes_played_total,
            1
        ),
    }
# ---------------------------------------------------------------------
# MAIN PROGRAM
# ---------------------------------------------------------------------

def run_season(
    team: str,
    season: int,
    max_games: int
):
    """
    Download every regular season game,
    calculate the metrics,
    and save everything into one CSV file.
    """

    game_log = get_game_log(
        team,
        season
    )

    if game_log.empty:

        print("\nNo games found.")

        return

    total_games = len(game_log)

    games_to_run = min(
        max_games,
        total_games
    )

    print(
        f"\nFound {total_games} games."
    )

    print(
        f"Running first {games_to_run} games...\n"
    )

    rows = []

    for i, (_, row) in enumerate(game_log.iterrows()):

        if i >= games_to_run:
            break

        game_id = row.get("game_id")

        opponent = row.get("_opponent", "?")

        date = row.get("Date", "?")

        if not game_id:

            print(
                f"Skipping game on {date} "
                "(missing game ID)"
            )

            continue

        print(
            f"[{i + 1}/{games_to_run}] "
            f"{date} vs {opponent}"
        )

        metrics = get_game_metrics(
            game_id,
            team
        )

        if metrics is None:

            print(
                "Unable to retrieve box score."
            )

            continue

        rows.append({

            "Date": date,

            "Opponent": opponent,

            "game_id": game_id,

            **metrics

        })

    output_df = pd.DataFrame(rows)

    output_file = os.path.join(

        OUTPUT_DIR,

        f"{team}_season_metrics_{season}.csv"

    )

    output_df.to_csv(

        output_file,

        index=False

    )

    print("\n--------------------------------------")

    print(
        f"Saved {len(output_df)} games."
    )

    print(
        f"CSV Location:\n{output_file}"
    )

    print("--------------------------------------")


# ---------------------------------------------------------------------
# PROGRAM ENTRY POINT
# ---------------------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(

        description=(
            "NBA Roster Availability Scraper"
        )

    )

    parser.add_argument(

        "--team",

        default=TEAM_CODE,

        help="NBA team abbreviation"

    )

    parser.add_argument(

        "--season",

        type=int,

        default=2025,

        help="Season ending year"

    )

    parser.add_argument(

        "--max_games",

        type=int,

        default=82,

        help="Maximum games to scrape"

    )

    args = parser.parse_args()

    run_season(

        args.team.upper(),

        args.season,

        args.max_games

    )