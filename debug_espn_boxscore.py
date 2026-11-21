"""
Debug helper - inspect ESPN's real box score JSON structure
--------------------------------------------------------------
Run this on its own. It fetches ONE Golden State Valkyries game and
prints the parts of the structure we need to fix OT detection:
  - box["header"] (should contain period/status info)
  - the first team block's keys under box["boxscore"]["teams"]
    (should contain linescores)

Paste the full printed output back into the chat - that tells us the
real field names so the fix can be made to match, instead of guessing.

Usage:
    python3 debug_espn_boxscore.py
"""

import requests
import json

SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/gs/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def main():
    print("Fetching Valkyries schedule...")
    resp = requests.get(SCHEDULE_URL, params={"season": 2025, "seasontype": 2}, timeout=15)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    completed = [e for e in events if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed")]

    if not completed:
        print("No completed games found - schedule call itself may be broken.")
        return

    game_id = completed[0]["id"]
    print(f"Using game_id={game_id}\n")

    resp = requests.get(SUMMARY_URL, params={"event": game_id}, timeout=15)
    resp.raise_for_status()
    box = resp.json()

    print("=" * 60)
    print("TOP-LEVEL KEYS in box:")
    print(list(box.keys()))

    print("\n" + "=" * 60)
    print("box['header'] (truncated to 3000 chars):")
    print(json.dumps(box.get("header", "<<MISSING>>"), indent=2)[:3000])

    print("\n" + "=" * 60)
    print("box['boxscore'] top-level keys:")
    print(list(box.get("boxscore", {}).keys()))

    teams = box.get("boxscore", {}).get("teams", [])
    print(f"\nbox['boxscore']['teams'] has {len(teams)} entries.")
    if teams:
        print("\nFirst team block keys:")
        print(list(teams[0].keys()))
        print("\nFirst team block (truncated to 2000 chars):")
        print(json.dumps(teams[0], indent=2)[:2000])
    else:
        print("boxscore['teams'] is EMPTY or missing - linescores fallback won't work either.")


if __name__ == "__main__":
    main()
