# NBA injury reports and playing time

Install with `python3 -m pip install -r requirements.txt`, then run `python3 nba_dashboard.py` and open http://127.0.0.1:5000.

For Render, the build command is `pip install -r requirements.txt`. The start command is `gunicorn nba_dashboard:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`. Use one worker: background query jobs and bounded five-minute source caches are held in that process. Queries run in background threads; the UI polls their status so collection does not depend on one long browser request. Two queries may run concurrently. Jobs disappear on restart, and completed jobs expire after one hour. No durable research database is created.

## Separate evidence sources

`nba_official_reports.py` retrieves official NBA pregame injury-report PDFs. The parser preserves source player names, game date, matchup, team, report timestamp (Eastern time), status, reason and PDF URL. It supports the older and current layouts checked during development. Reason baselines are grouped into physical blocks and matched to the unique player/status row by page position, including wrapped blocks that start above a name. A leading continuation can attach to the final row on the previous page only under strict page-edge checks. Prefix wording is validated after association and never determines player order. Ambiguous blocks and unrecognized layouts fail closed. A report marked NOT YET SUBMITTED is unavailable for that team. Reports after tipoff, stale reports and wrong matchups are rejected.

The collector tries a bounded set of observed PDF filename formats and pregame times, with a per-game retrieval time budget. It selects an available submitted pregame snapshot, which is not necessarily the last report before tipoff. Later changes and sources outside these snapshots are not collected. The UI displays available snapshots / loaded games, and unavailable games never contribute an invented zero injury count. Even a complete game schedule is not proof of complete injury coverage. Historical season selection does not guarantee historical report availability.

`nba_espn_collector.py` retrieves ESPN completed regular-season schedules and player box scores. It preserves each listed player's source name/ID, participation evidence, reported minutes and nonparticipation reason. ESPN may omit inactive injured players entirely. Official-report players are retained independently, even when omitted from the box score. Exact normalized full-name matches link the sources; unmatched names remain explicit with no inferred player ID, absence or zero minutes.

## Interpretation

Official report records are categorized conservatively as injury, illness, other or unknown using the wording after the source's Injury/Illness umbrella heading. A body-site injury reason is not classified as illness just because that heading contains the word. Missing, mixed or unrecognized reasons remain unknown. Original reason wording is retained with PDF whitespace normalized; categories are text classifications, not clinical adjudications.

All reported statuses are retained, including Available, Probable and Questionable. A player can be injury-listed and still play. Counts are player-game designations in selected snapshots, not injury-related missed games, unique injury episodes, incidence or diagnoses. Repeated designations across games are not deduplicated into medical events. No claim is made that every publicly recorded injury, news item, practice injury or report revision is included.

Actual participation is separate: played, absent, unknown, or not_listed_in_box_score for unmatched report players. Missing or contradictory ESPN participation evidence stays unknown, excluded from entered-player and confirmed-absence counts. Generic DNP/inactive does not establish injury. Default ESPN reasons attached to played players are ignored as absence evidence.

ESPN usually supplies rounded whole minutes. The exports preserve raw minutes and identify rounded_whole_minutes, seconds_reported, reported_decimal_minutes, did_not_play or unavailable. They do not manufacture second-level exposure. Team minutes are five players multiplied by completed period lengths, not the sum of rounded player minutes. Exact exposure analysis requires a verified minute:second source that is not integrated here.

## UI and exports

Season selection defaults to the current season, lists seasons back to 1946–47 and includes the next two upcoming seasons. Source coverage varies. Empty future seasons show no completed games and cannot fall back silently to a different season. Only regular-season schedule games are collected; Cup championship games are excluded. Player List mode lists players observed in selected ESPN box scores, not the complete eligible roster.

After a query, four CSV downloads are available:

- Export injuries CSV: official snapshot records categorized as injury, including injured players who played and players missing from ESPN.
- Export all official report records CSV: all categories and statuses in available official snapshots.
- Export playing time CSV: every player listed in the loaded ESPN box scores, with participation and raw/numeric minutes plus precision.
- Export box-score absences CSV: ESPN nonparticipants and participation-unknown records, with source reasons kept separate.

Columns include team name/code, source-reported player full name/ID, season, game date/timezone/ID, opponent, result, record type, category, status, original reason, participation, minutes/precision, report timestamp, identity-join method, source URLs, sample size and coverage note. Unmatched report players have blank numeric playing time, not zero. Report timestamps use Eastern offsets; game dates use the displayed venue timezone. Filters disable old downloads until the next query. CSVs use UTF-8 BOM, quoted fields and spreadsheet formula protection.

## Verification and limits

Run `python3 -m unittest discover -s tests -v` and `node tests/test_csv_export.cjs`. Tests cover source failures, conservative classifications, missing inactive players, players who play despite injury designations, unavailable/not-submitted/after-tipoff reports, malformed layouts, wrapped PDF reasons, background jobs, season validation and CSV precision/escaping. Synthetic PDF visitor fixtures are used for regression tests; a retained ESPN response tests participation extraction.

Live official PDFs were checked for all 30 teams' first ten 2024–25 games: all 300 team-game checks had matching submitted pregame snapshots after the parser fixes. This sample check does not guarantee other dates or seasons. The 2024 opening-night report recovered Vanderbilt, Wood, Porzingis, Achiuwa and Robinson, who were absent from the corresponding ESPN injury counts. A current-format 2026 report parsed 65 player records, and an eight-page 2024 report with an Available / dash-reason record parsed 112. These are targeted source checks, not a full historical report audit.

A separate retained-source replay verified all 82 regular-season games for each of 30 teams in 2024–25 (2,460 team-game records), retaining 67 participation-unknown player-game records. That replay validates ESPN game coverage, not official report completeness or medical accuracy. Do not present this dashboard as a complete injury registry or a validated clinical research dataset.

## Supplied legacy folder

Only ATL_game_metrics_2025.csv and PHO_game_metrics_2025.csv were found as saved data in the supplied Downloads/NBA folder. Their injury-labeled counts derive from generic Did Not Play records without injury-specific reasons. The Pro Sports Transactions scraper had no saved output and its source returned 403 during inspection. Those totals are not used as authoritative injury evidence. Legacy dashboard scripts are retained unchanged; deploy `nba_dashboard:app`.


## Validation follow-up on 22 November 2026

Fixed all ten supplied reason mismatches using four retained official PDF fixtures.
The regression cases include repeated Concussion Protocol wording, Team Suspension,
wrapped reasons starting above a player name, and a reason continued onto the next page.
A broader replay downloaded all 68 distinct official report URLs retained from prior
workspace checks and the new samples, parsing 7,970 rows. A separate audit using
pdfplumber words and drawn table-cell borders matched all 7,970 reasons. This is a
bounded retained-source replay, not a review of the entire NBA historical archive.
The supplied validation folder did not contain its claimed 829 PDFs or raw 18-season
query results, so that larger corpus could not be reproduced directly.

The shared classifier now recognizes sciatic/nerve, patellofemoral, plantar, tendon,
retrocalcaneal, corneal and eye wording, plus virus/viral as illness. Source umbrella
prefixes and repeated whitespace are normalized consistently for both ESPN and official
reasons. Of 113 supplied suggestions, 112 are supported; Right Index Finger; Sprain /
Illness remains unknown because it explicitly mixes injury and illness. Raw reasons are
preserved. No injury diagnosis or unique event is inferred from these categories.

ESPN schedule/summary retrieval retries transient connection/timeouts, HTTP 429 and
server errors up to three total attempts with short backoff. Permanent errors such as
404 are not retried and exhausted failures are not cached as successes. Partial results
now expose collected_games, missing_games and missing_game_ids as well as requested_games
and scheduled_completed_games. Missing counts concern the requested sample, not completed
games outside a five/ten/twenty-game selection. Season Summary and Player List display the
missing count explicitly. Missing official snapshots remain a separate visible summary
count; unavailable coverage never contributes a false zero injury count.

Run the existing Python/CSV checks plus `node tests/test_summary_coverage.cjs` for the
new summary assertions. Fixtures and sources.json record the four original PDF URLs and
content hashes. Previously downloaded CSVs remain historical exports; rerun the query
and download new files after deployment to obtain corrected parsed reasons.
