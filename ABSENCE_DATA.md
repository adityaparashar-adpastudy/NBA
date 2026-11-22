# NBA reported absence categories

Run `python3 -m pip install -r requirements.txt`, then `python3 nba_dashboard.py` and open http://127.0.0.1:5000.
The dashboard uses nba_espn_collector.py for all selected teams, with the conservative classifier shared from lakers_test.py. Other legacy dashboard files have not been changed.

Each listed nonparticipant retains the extracted source wording in reported_absence_reason and the box-score source URL. Categories are injury, illness, other, or unknown. Explicit injury/body-site wording, illness wording, and known nonmedical wording are classified separately. Conflicting categories, generic DNP, inactive status, missing reasons, and unrecognized wording remain unknown. This is a conservative text classifier, not clinical adjudication. Played players have no absence category.

ESPN game box scores may provide only generic DNP status. In that case the app reports unknown; it does not invent a medical reason. Players absent from the source table are not inferred. Source coverage is therefore not a complete roster-wide injury registry. Repeated absences are player-game records, not new injury events or injury incidence. No longitudinal injury-event deduplication is performed.

The interface includes all four counts, source links, and expandable player reasons. Failed games produce warnings and are excluded from collected totals. All-game failure returns an error rather than zero. Roster mode lists unique players observed across the selected games, not season-wide eligibility.

Run regression checks with `python3 -m unittest discover -s tests -v`. Tests use synthetic HTML, a retained ESPN game response, and mocked requests, including missing/ambiguous reasons and source failures. They do not verify historical injury totals or current source availability.

For Render, use `pip install -r requirements.txt` and `gunicorn nba_dashboard:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 330`. Collection is synchronous and can be slow; start with five games. A long Gunicorn timeout does not override hosting request limits. This change does not deploy or push code automatically.

The dashboard now uses ESPN JSON rather than Basketball Reference HTML, which returned HTTP 403 during deployment troubleshooting. Single-game mode accepts a numeric ESPN event ID (example: 401704628). Only completed regular-season schedule entries are queried. The source may omit inactive players entirely; these missing players are not represented as zero injuries. Played players can carry default reason text in ESPN responses; those strings are ignored. Team minutes are five players multiplied by completed period lengths, not a sum of rounded individual minutes.


Audit fixes:
- A player with missing minutes or contradictory participation fields is retained with played=null and participation_status=unknown. These records have no absence category and are counted in participation_unknown. They are excluded from both confirmed entered-player and absence totals. This differs from a confirmed absence whose reason is unknown. Source minutes and DNP flag are visible in details.
- All games with sufficient box-score data remain visible even when individual participation is uncertain. Missing entire box scores still produce collection warnings. The source can omit inactive players entirely, so full game coverage is not complete injury coverage.
- NBA Cup and NBA In-Season Tournament championship games are excluded from regular-season schedule totals. Group, quarterfinal, and semifinal games remain eligible. Each event's season year is checked because ESPN's top-level season metadata may describe the current year even for a historical request.
- The season end-year field defaults to the current NBA season and accepts any four-digit future year. Empty future seasons display a no-completed-games message; a source fallback to another year is rejected.
- Non-object JSON and invalid game limits return client errors. Summary caching retains only fields used by the app.

Verification: the full 2024–25 replay now collects all 82 regular-season games for each of 30 teams (2,460 team-game records) from retained source responses. It retains 67 participation-unknown player-game records and reports their uncertainty without inferring absence. Historical injury incidence has not been medically or independently adjudicated.
