"""
ESPN WNBA Injury Report Scraper
--------------------------------
Pulls the current WNBA injury report from ESPN's unofficial public API.

This complements wnba_official_api_scraper.py (stats.wnba.com), which can only
derive "Entered" / "Minutes" from box scores because Basketball-Reference and
stats.wnba.com box scores don't reliably expose DNP/inactive reasons for WNBA.
ESPN's injuries endpoint gives an actual Out/Questionable/Probable/Day-To-Day
status + reason, independent of whether the player's team even played that day.

No API key required. Endpoint is undocumented, so:
  - fields may change without notice
  - be a good citizen: cache results, don't hammer it (every few hours is plenty)
"""

import requests
import pandas as pd
from datetime import datetime, timezone

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries"

# WNBA team abbreviations (ESPN slugs) - used only if you want per-team calls
TEAM_ABBREVS = [
    "ATL", "CHI", "CON", "DAL", "IND", "LA", "LV", "MIN",
    "NY", "PHX", "SEA", "WSH", "GS", "POR",  # GS/POR = expansion teams, drop if not yet live
]


def fetch_league_injuries() -> dict:
    """Single call, whole league. Preferred over per-team looping."""
    resp = requests.get(BASE_URL, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_team_injuries(team_abbrev: str) -> dict:
    """Fallback: fetch a single team's injury report."""
    resp = requests.get(BASE_URL, params={"team": team_abbrev}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_injuries(raw: dict) -> pd.DataFrame:
    """
    Flattens ESPN's nested injuries payload into one row per player.
    ESPN's shape (subject to change, since this is unofficial):
      raw["injuries"] -> list of team blocks
        each team block -> {"team": {...}, "injuries": [ {...player...} ]}
    """
    rows = []
    for team_block in raw.get("injuries", []):
        team_name = team_block.get("team", {}).get("displayName", "")
        team_abbr = team_block.get("team", {}).get("abbreviation", "")
        for inj in team_block.get("injuries", []):
            athlete = inj.get("athlete", {})
            rows.append({
                "team": team_name,
                "team_abbrev": team_abbr,
                "player": athlete.get("displayName"),
                "player_id": athlete.get("id"),
                "position": athlete.get("position", {}).get("abbreviation"),
                "status": inj.get("status"),
                "injury_type": inj.get("type", {}).get("description") or inj.get("details", {}).get("type"),
                "comment": inj.get("longComment") or inj.get("shortComment"),
                "date": inj.get("date"),
                "pulled_at": datetime.now(timezone.utc).isoformat(),
            })
    return pd.DataFrame(rows)


def main():
    raw = fetch_league_injuries()
    df = parse_injuries(raw)

    if df.empty:
        print("No injury data returned — check raw payload shape (ESPN may have changed it).")
        print(raw)
        return

    out_path = "wnba_injuries_espn.csv"
    df.to_csv(out_path, index=False)
    print(f"Pulled {len(df)} injury rows across {df['team'].nunique()} teams.")
    print(f"Saved to {out_path}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
