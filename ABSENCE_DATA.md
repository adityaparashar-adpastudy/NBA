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
- The season dropdown defaults to the current NBA season, lists every season back to 1946–47, and automatically includes the next two upcoming seasons. It advances with the calendar, like the WNBA selector. The API also accepts four-digit future years. Empty future seasons display a no-completed-games message; a source fallback to another year is rejected.
- Non-object JSON and invalid game limits return client errors. Summary caching retains only fields used by the app.

Verification: the full 2024–25 replay now collects all 82 regular-season games for each of 30 teams (2,460 team-game records) from retained source responses. It retains 67 participation-unknown player-game records and reports their uncertainty without inferring absence. Historical injury incidence has not been medically or independently adjudicated.

CSV exports:
- After loading season or single-game results, Export injuries CSV downloads only loaded records with confirmed nonparticipation and source category injury. Export all absence records CSV also includes illness, other/unknown reasons, and participation-unknown records with their separate status.
- Columns preserve team name/code, season, source-reported player full name and ID, game date/timezone/ID, opponent, result, category, exact reason, source participation fields, URL, sample size, coverage note, and export time. Actual game season metadata takes priority over the selected year in single-game mode.
- Every row states the incomplete ESPN source coverage. The export does not fill missing inactive injuries or classify every DNP as injury. Changing query filters disables exports until the next query. Files use UTF-8 BOM, quoted CSV fields, and spreadsheet formula protection.
- Run CSV serialization checks with `node tests/test_csv_export.cjs` when Node.js is available. Browser download verified with the Lakers' first ten games of 2024–25; downloaded rows reconciled to the loaded injury count. This is export verification, not medical validation.

Local source inspection:
Only two saved data files were found under the supplied Downloads/NBA folder: ATL_game_metrics_2025.csv and PHO_game_metrics_2025.csv. Their injury-labeled counts derive from generic Did Not Play records, without injury-specific reasons. The supplied warriors_injury_scraper.py targets Pro Sports Transactions, but no saved output from that scraper was present and its source returned 403 during this check. These files cannot establish a complete player-level injury dataset. A trusted saved injury log must be identified before using it as the dashboard's authoritative injury source.
