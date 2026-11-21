"""
Debug helper v2 - print ONLY the status/period field, no truncation noise
----------------------------------------------------------------------------
Usage:
    python3 debug_espn_status.py
"""

import requests
import json

SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/gs/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def main():
    resp = requests.get(SCHEDULE_URL, params={"season": 2025, "seasontype": 2}, timeout=15)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    completed = [e for e in events if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed")]
    game_id = completed[0]["id"]
    print(f"game_id={game_id}\n")

    resp = requests.get(SUMMARY_URL, params={"event": game_id}, timeout=15)
    resp.raise_for_status()
    box = resp.json()

    comp = box.get("header", {}).get("competitions", [{}])[0]

    print("competition['status']:")
    print(json.dumps(comp.get("status", "<<MISSING>>"), indent=2))

    print("\ncompetition top-level keys (to see what else is available):")
    print(list(comp.keys()))

    print("\nteams[0] linescores:")
    teams = box.get("boxscore", {}).get("teams", [])
    if teams:
        print(json.dumps(teams[0].get("linescores", "<<NO linescores KEY>>"), indent=2))

    print("\nAlso checking header top-level for anything OT-related:")
    print(list(box.get("header", {}).keys()))


if __name__ == "__main__":
    main()
