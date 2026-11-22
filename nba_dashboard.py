"""
NBA Data Explorer — Flask UI
Run: python3 app.py
Then open: http://127.0.0.1:5000
"""

from datetime import datetime
from threading import Lock, Thread
from uuid import uuid4
from time import monotonic
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
_jobs = {}
_jobs_lock = Lock()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NBA Data Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0a0a0f;
    --surface:  #13131a;
    --border:   #1e1e2e;
    --accent:   #f0522a;
    --accent2:  #f5a623;
    --text:     #e8e8f0;
    --muted:    #6b6b80;
    --mono:     'DM Mono', monospace;
    --sans:     'DM Sans', sans-serif;
    --display:  'Bebas Neue', sans-serif;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── header ── */
  header {
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    background: var(--surface);
  }
  .logo {
    font-family: var(--display);
    font-size: 2rem;
    letter-spacing: 2px;
    color: var(--text);
  }
  .logo span { color: var(--accent); }
  .subtitle {
    font-size: 0.75rem;
    color: var(--muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 2px;
  }

  /* ── main layout ── */
  main {
    display: grid;
    grid-template-columns: 300px 1fr;
    flex: 1;
  }

  /* ── sidebar ── */
  aside {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 2rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .section-label {
    font-size: 0.65rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }

  /* mode tabs */
  .mode-tabs {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .mode-tab {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 0.7rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-family: var(--sans);
    font-size: 0.85rem;
    text-align: left;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .mode-tab:hover { border-color: var(--accent); color: var(--text); }
  .mode-tab.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    font-weight: 500;
  }
  .mode-tab .icon { font-size: 1rem; }

  /* inputs */
  .field { display: flex; flex-direction: column; gap: 0.4rem; }
  label { font-size: 0.75rem; color: var(--muted); letter-spacing: 1px; text-transform: uppercase; }

  select, input[type=text], input[type=number] {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.65rem 0.85rem;
    border-radius: 6px;
    font-family: var(--mono);
    font-size: 0.85rem;
    width: 100%;
    outline: none;
    transition: border-color 0.15s;
    appearance: none;
  }
  select:focus, input:focus { border-color: var(--accent); }

  /* run button */
  .run-btn {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 0.85rem 1rem;
    border-radius: 6px;
    font-family: var(--display);
    font-size: 1.1rem;
    letter-spacing: 2px;
    cursor: pointer;
    width: 100%;
    transition: opacity 0.15s, transform 0.1s;
    margin-top: 0.5rem;
  }
  .run-btn:hover { opacity: 0.9; transform: translateY(-1px); }
  .run-btn:active { transform: translateY(0); }
  .run-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  .export-actions { display:flex; flex-wrap:wrap; gap:0.75rem; }
  .export-actions button { padding:0.7rem 1rem; border:1px solid var(--accent); border-radius:6px; background:var(--surface); color:var(--text); cursor:pointer; }
  .export-actions button:disabled { opacity:0.5; cursor:not-allowed; }
  .coverage-warning { padding:1rem; border:1px solid var(--accent); border-radius:6px; }
  /* metric legend */
  .legend {
    border-top: 1px solid var(--border);
    padding-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .legend-item {
    font-size: 0.75rem;
    color: var(--muted);
    display: flex;
    gap: 0.5rem;
  }
  .legend-num {
    color: var(--accent2);
    font-family: var(--mono);
    font-weight: 500;
    min-width: 1.2rem;
  }

  /* ── output area ── */
  .output-area {
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    overflow-y: auto;
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.8rem;
    color: var(--muted);
    font-family: var(--mono);
  }
  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--muted);
    transition: background 0.3s;
  }
  .dot.running { background: var(--accent2); animation: pulse 1s infinite; }
  .dot.done    { background: #4ade80; }
  .dot.error   { background: #f87171; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

  /* results */
  .results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    position: relative;
    overflow: hidden;
    animation: slideUp 0.3s ease both;
  }
  @keyframes slideUp {
    from { opacity:0; transform: translateY(12px); }
    to   { opacity:1; transform: translateY(0); }
  }
  .metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
  }
  .metric-card.m2::before { background: var(--accent2); }
  .metric-card.m3::before { background: #60a5fa; }
  .metric-card.m4::before { background: #a78bfa; }

  .metric-num {
    font-family: var(--display);
    font-size: 0.75rem;
    letter-spacing: 2px;
    color: var(--accent);
    margin-bottom: 0.3rem;
  }
  .metric-card.m2 .metric-num { color: var(--accent2); }
  .metric-card.m3 .metric-num { color: #60a5fa; }
  .metric-card.m4 .metric-num { color: #a78bfa; }

  .metric-label {
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.5rem;
  }
  .metric-value {
    font-family: var(--display);
    font-size: 2.8rem;
    letter-spacing: 1px;
    line-height: 1;
  }
  .metric-sub {
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 0.3rem;
    font-family: var(--mono);
  }

  /* raw output */
  .raw-output {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.5rem;
    font-family: var(--mono);
    font-size: 0.78rem;
    line-height: 1.8;
    color: #b0b0c8;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 500px;
    overflow-y: auto;
  }

  /* game table */
  .game-table-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
    font-family: var(--mono);
  }
  th {
    background: #0d0d14;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 0.65rem;
    padding: 0.8rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  td {
    padding: 0.7rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    white-space: nowrap;
  }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.02); }
  td.num { color: var(--accent); font-weight: 500; }
  td.min { color: var(--accent2); }
  td.ent { color: #60a5fa; }
  td.ros { color: #a78bfa; }
  td.win { color: #4ade80; }
  td.loss { color: #f87171; }

  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--muted);
  }
  .empty-state .big { font-family: var(--display); font-size: 5rem; opacity: 0.15; }
  .empty-state p { font-size: 0.85rem; margin-top: 1rem; }

  /* game_id hint */
  .hint { font-size: 0.7rem; color: var(--muted); font-family: var(--mono); margin-top: 0.25rem; }

  /* hidden fields */
  .field-gameid { display: none; }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">NBA <span>Data</span> Explorer</div>
    <div class="subtitle">Official NBA injury reports · ESPN playing time</div>
  </div>
</header>

<main>
  <aside>
    <div>
      <div class="section-label">Query Type</div>
      <div class="mode-tabs">
        <button class="mode-tab active" data-mode="team" onclick="setMode('team',this)">
          <span class="icon">📊</span> Season Summary
        </button>
        <button class="mode-tab" data-mode="game" onclick="setMode('game',this)">
          <span class="icon">🏀</span> Single Game
        </button>
        <button class="mode-tab" data-mode="roster" onclick="setMode('roster',this)">
          <span class="icon">👥</span> Player List
        </button>
      </div>
    </div>

    <div class="field">
      <label>Team</label>
      <select id="team">
        <option value="ATL">Atlanta Hawks (ATL)</option>
        <option value="BOS">Boston Celtics (BOS)</option>
        <option value="BRK">Brooklyn Nets (BRK)</option>
        <option value="CHO">Charlotte Hornets (CHO)</option>
        <option value="CHI">Chicago Bulls (CHI)</option>
        <option value="CLE">Cleveland Cavaliers (CLE)</option>
        <option value="DAL">Dallas Mavericks (DAL)</option>
        <option value="DEN">Denver Nuggets (DEN)</option>
        <option value="DET">Detroit Pistons (DET)</option>
        <option value="GSW">Golden State Warriors (GSW)</option>
        <option value="HOU">Houston Rockets (HOU)</option>
        <option value="IND">Indiana Pacers (IND)</option>
        <option value="LAC">LA Clippers (LAC)</option>
        <option value="LAL">LA Lakers (LAL)</option>
        <option value="MEM">Memphis Grizzlies (MEM)</option>
        <option value="MIA">Miami Heat (MIA)</option>
        <option value="MIL">Milwaukee Bucks (MIL)</option>
        <option value="MIN">Minnesota Timberwolves (MIN)</option>
        <option value="NOP">New Orleans Pelicans (NOP)</option>
        <option value="NYK">New York Knicks (NYK)</option>
        <option value="OKC">OKC Thunder (OKC)</option>
        <option value="ORL">Orlando Magic (ORL)</option>
        <option value="PHI">Philadelphia 76ers (PHI)</option>
        <option value="PHO">Phoenix Suns (PHO)</option>
        <option value="POR">Portland Trail Blazers (POR)</option>
        <option value="SAC">Sacramento Kings (SAC)</option>
        <option value="SAS">San Antonio Spurs (SAS)</option>
        <option value="TOR">Toronto Raptors (TOR)</option>
        <option value="UTA">Utah Jazz (UTA)</option>
        <option value="WAS">Washington Wizards (WAS)</option>
      </select>
    </div>

    <div class="field">
      <label>Season</label>
      <select id="season" aria-label="Season">
        {% for year in seasons %}<option value="{{ year }}"{% if year == default_season %} selected{% endif %}>{{ year-1 }}–{{ '%02d'|format(year % 100) }}{% if year > default_season %} (upcoming){% endif %}</option>{% endfor %}
      </select>
      <div class="hint">Past seasons are listed below the current season. Upcoming seasons fill in after games are completed; historical coverage varies by source.</div>
    </div>

    <div class="field" id="field-maxgames">
      <label>Max Games</label>
      <select id="max_games">
        <option value="5">5 games</option>
        <option value="10" selected>10 games</option>
        <option value="20">20 games</option>
        <option value="100">All completed games</option>
      </select>
    </div>

    <div class="field field-gameid" id="field-gameid">
      <label>Game ID</label>
      <input type="text" id="game_id" placeholder="e.g. 401704628">
      <div class="hint">Numeric ESPN game ID from its box-score URL</div>
    </div>

    <button class="run-btn" id="runBtn" onclick="runQuery()">RUN QUERY</button>

    <div class="legend">
      <div class="section-label">Metrics</div>
      <div class="legend-item"><span class="legend-num">1</span> Official report categories and coverage</div>
      <div class="legend-item"><span class="legend-num">2</span> Player participation and reported minutes</div>
      <div class="legend-item"><span class="legend-num">3</span> Players who entered game</div>
      <div class="legend-item"><span class="legend-num">4</span> Players listed in selected games</div>
    </div>
  </aside>

  <div class="output-area" id="outputArea">
    <div class="empty-state">
      <div class="big">🏀</div>
      <p>Select a team and click <strong>Run Query</strong> to pull game data.</p>
    </div>
  </div>
</main>

<script src="{{ url_for('static', filename='injury_export.js') }}"></script>
<script>
let currentMode = 'team';
let loadedExport = null;
function invalidateExport() {
  loadedExport = null;
  document.querySelectorAll('[data-export]').forEach(button => button.disabled = true);
}
['team','season','max_games','game_id'].forEach(id => document.getElementById(id).addEventListener('change', invalidateExport));
function exportAbsences(scope) {
  if (!loadedExport) return;
  const context = {...loadedExport.context, exportedAt:new Date().toISOString()};
  const records = NBAInjuryExport.rows(loadedExport.games, context, scope);
  if (!records.length) return;
  const blob = new Blob([NBAInjuryExport.csv(records)], {type:'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  const year = loadedExport.games[0]?.season_end_year || context.season;
  anchor.download = `nba_${context.team}_${year}_${scope === 'injury' ? 'official_injury_records' : scope === 'reports' ? 'official_report_records' : scope === 'playing' ? 'player_playing_time' : 'boxscore_absences'}.csv`;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}


function setMode(mode, el) {
  invalidateExport();
  currentMode = mode;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('field-maxgames').style.display = mode !== 'game' ? 'flex' : 'none';
  document.getElementById('field-gameid').style.display   = mode === 'game'   ? 'flex' : 'none';
}

async function runQuery() {
  const team      = document.getElementById('team').value;
  const season    = document.getElementById('season').value;
  const teamName  = document.getElementById('team').selectedOptions[0].textContent.replace(/ \([A-Z]+\)$/, '');
  const maxGames  = document.getElementById('max_games').value;
  const gameId    = document.getElementById('game_id').value.trim();
  const btn       = document.getElementById('runBtn');
  const out       = document.getElementById('outputArea');

  if (currentMode === 'game' && !gameId) {
    alert('Please enter a Game ID.');
    return;
  }

  invalidateExport();
  btn.disabled = true;
  btn.textContent = 'FETCHING...';
  out.innerHTML = `
    <div class="status-bar">
      <div class="dot running" id="statusDot"></div>
      <span id="statusText">Connecting to ESPN...</span>
    </div>
    <div class="raw-output" id="liveLog">Starting...</div>`;

  const payload = { mode: currentMode, team, season, max_games: maxGames, game_id: gameId };

  try {
    const resp = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const started = await resp.json();
    if (!resp.ok) throw new Error(started.output || 'Unable to start query');
    let state;
    do {
      await new Promise(resolve => setTimeout(resolve,1000));
      const poll = await fetch('/api/jobs/' + started.job_id);
      state = await poll.json();
      if (!poll.ok) throw new Error(state.output || 'Query expired; please run it again.');
      document.getElementById('statusText').textContent = 'Loading game data and official NBA injury reports…';
    } while (state.status === 'running');
    const data = state.data;


    document.getElementById('statusDot').className = data.ok ? 'dot done' : 'dot error';
    document.getElementById('statusText').textContent = data.ok ? 'Done' : 'Error';

    if (data.ok) {
      renderResults(data, team, season, teamName);
    } else {
      document.getElementById('liveLog').textContent = data.output;
    }
  } catch (e) {
    document.getElementById('statusDot').className = 'dot error';
    document.getElementById('statusText').textContent = 'Request failed';
    document.getElementById('liveLog').textContent = String(e);
  }

  btn.disabled = false;
  btn.textContent = 'RUN QUERY';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function renderResults(data, team, season, teamName) {
  const out = document.getElementById('outputArea');
  if (data.mode === 'roster') {
    out.innerHTML = `<h3>Players listed in ${data.collected_games} collected game(s): ${data.roster_count}</h3><p>Players listed in source box scores for the selected games; not a complete season roster or game-day eligibility list.</p><p><strong>${data.missing_games || 0} missing game(s) in the requested sample.</strong> Missing games are unavailable data, not zero absences.</p>${(data.warnings || []).map(w=>`<p role="alert">${escapeHtml(w)}</p>`).join('')}<pre>${escapeHtml(data.output)}</pre>`;
    return;
  }
  const games = data.mode === 'game' ? [{...data.metrics, game_id:data.game_id}] : data.games;
  loadedExport = {games, context:{team, teamName, season, requestedGames:data.requested_games || games.length}};
  const injuryRows = NBAInjuryExport.rows(games,loadedExport.context,'injury');
  const reportRows = NBAInjuryExport.rows(games,loadedExport.context,'reports');
  const absenceRows = NBAInjuryExport.rows(games,loadedExport.context,'all');
  const playingRows = NBAInjuryExport.rows(games,loadedExport.context,'playing');
  const exportButtons = `<div class="export-actions"><button data-export onclick="exportAbsences('injury')" ${injuryRows.length ? '' : 'disabled'}>Export injuries CSV (${injuryRows.length})</button><button data-export onclick="exportAbsences('reports')" ${reportRows.length ? '' : 'disabled'}>Export all official report records CSV (${reportRows.length})</button><button data-export onclick="exportAbsences('playing')" ${playingRows.length ? '' : 'disabled'}>Export playing time CSV (${playingRows.length})</button><button data-export onclick="exportAbsences('all')" ${absenceRows.length ? '' : 'disabled'}>Export box-score absences CSV (${absenceRows.length})</button></div>`;
  const covered = games.filter(g=>g.official_report?.status === 'available');
  const categories = ['injury','illness','other','unknown'];
  const cards = categories.map(c=>`<div class="metric-card"><div class="metric-label">OFFICIAL REPORT · ${c.toUpperCase()}</div><div class="metric-value">${covered.length ? covered.reduce((sum,g)=>sum+g.official_report_counts[c],0) : 'Unavailable'}</div><div class="metric-sub">player-game designations in ${covered.length}/${games.length} available snapshots</div></div>`).join('');
  const rows = games.map(g=>`<tr><td>${escapeHtml(g.date || g.game_id)}</td><td>${escapeHtml(g.opp || team)}</td><td>${g.official_report_counts?.injury ?? 'Unavailable'}</td><td>${g.official_report_counts?.illness ?? 'Unavailable'}</td><td>${g.official_report?.status === 'available' ? 'Snapshot available' : 'Unavailable'}</td><td>${g.players_dnp}</td><td>${g.players_entered}</td><td>${g.participation_unknown || 0}</td><td>${g.minutes_played}</td><td>${g.overtime_periods}</td></tr>`).join('');
  const details = games.map(g=> {
    const report=g.official_report;
    const official=report?.status === 'available' ? `<p>Report as of ${escapeHtml(report.report_at)} · <a href="${escapeHtml(report.source_url)}" target="_blank" rel="noopener">Official NBA PDF</a></p><p>${escapeHtml(report.note)}</p><table><thead><tr><th>Player full name</th><th>Report status</th><th>Category</th><th>Original reason</th><th>Box-score participation</th></tr></thead><tbody>${report.records.map(r=>`<tr><td>${escapeHtml(r.player_full_name)}</td><td>${escapeHtml(r.reported_status)}</td><td>${escapeHtml(r.category)}</td><td>${escapeHtml(r.reported_reason)}</td><td>${escapeHtml(r.actual_participation)}</td></tr>`).join('') || '<tr><td colspan="5">No players listed for this team in the selected snapshot.</td></tr>'}</tbody></table>` : '<p>Official report unavailable. This does not establish zero injuries.</p>';
    const players=`<p>Playing time is reported by ESPN, usually rounded to whole minutes. It is not verified minute:second exposure. <a href="${escapeHtml(g.source_url)}" target="_blank" rel="noopener">Box-score source</a></p><table><thead><tr><th>Player full name</th><th>Participation</th><th>Reported minutes</th><th>DNP category</th><th>Reported reason</th></tr></thead><tbody>${g.players.map(p=>`<tr><td>${escapeHtml(p.player)}</td><td>${escapeHtml(p.participation_status)}</td><td>${escapeHtml(p.minutes ?? (p.played === false ? 'DNP' : 'Unknown'))}</td><td>${escapeHtml(p.absence_category || '')}</td><td>${escapeHtml(p.reported_absence_reason || '')}</td></tr>`).join('')}</tbody></table>`;
    return `<details><summary>${escapeHtml(g.date || g.game_id)} — injury report and player playing time</summary><h4>Official pregame designations</h4>${official}<h4>Player participation and reported minutes</h4>${players}</details>`;
  }).join('');
  out.innerHTML = `<h3>${escapeHtml(games[0]?.team_name || teamName || team)} · Season ending ${escapeHtml(games[0]?.season_end_year || season)}</h3><p role="note" class="coverage-warning">Official pregame injury reports available for ${covered.length} of ${games.length} loaded games. Reports are selected pregame snapshots, not every public report or unique injury event. ${games.length-covered.length} loaded game(s) have no available official report. Missing coverage is unavailable, not zero. A reported injury does not establish that a player missed the game.</p>${exportButtons}<p>${games.length} completed game(s) collected${data.requested_games ? ' of '+data.requested_games+' requested' : ''}. <strong>${data.missing_games ?? Math.max(0,(data.requested_games || games.length)-games.length)} missing game(s) in the requested sample.</strong>${data.scheduled_completed_games ? ' '+data.scheduled_completed_games+' completed regular-season games returned by the schedule.' : ''}</p><div class="results-grid">${cards}</div><p>Report status, actual participation, and playing time are separate. Full names from official reports are preserved, including players omitted from ESPN box scores. Exact name matches link records; unmatched identities remain explicit. Injury totals include report designations for players who may still play. ESPN minutes may be rounded. Team minutes are five players × completed period lengths. Regular season only.</p>${(data.warnings || []).map(w=>`<p role="alert">${escapeHtml(w)}</p>`).join('')}<div class="game-table-wrap"><table><thead><tr><th>Date / Game</th><th>Opponent</th><th>Official injury records</th><th>Official illness records</th><th>Report coverage</th><th>Box-score DNP</th><th>Entered</th><th>Participation unknown</th><th>Team minutes</th><th>OT</th></tr></thead><tbody>${rows}</tbody></table></div>${details}`;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    today = datetime.now()
    current_season = today.year + (today.month >= 7)
    return render_template_string(HTML, default_season=current_season, seasons=range(current_season+2, 1946, -1))

@app.post('/api/query')
def start_query():
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict):return jsonify(output='Send a JSON object.'),400
    with _jobs_lock:
        expired=[key for key,value in _jobs.items() if value['status']!='running' and monotonic()-value['created']>3600]
        for key in expired:del _jobs[key]
        if sum(v['status']=='running' for v in _jobs.values())>=2:
            return jsonify(output='Two queries are already running. Please try again shortly.'),429
        if len(_jobs)>=64:
            oldest=next((key for key,value in _jobs.items() if value['status']!='running'),None)
            if oldest:del _jobs[oldest]
        job_id=uuid4().hex
        _jobs[job_id]=dict(status='running',created=monotonic())
    def worker():
        try:
            with app.test_request_context('/run',method='POST',json=payload):
                response=app.make_response(run())
                data=response.get_json()
        except Exception:
            app.logger.exception('Background query failed')
            data=dict(ok=False,output='Query failed; please retry.')
        with _jobs_lock:_jobs[job_id].update(status='complete',data=data)
    Thread(target=worker,daemon=True).start()
    return jsonify(job_id=job_id),202

@app.get('/api/jobs/<job_id>')
def query_job(job_id):
    with _jobs_lock:
        job=_jobs.get(job_id)
        if job is None:return jsonify(output='Query expired or the service restarted; please run it again.'),404
        return jsonify({key:value for key,value in job.items() if key!='created'})

@app.route("/run", methods=["POST"])
def run():
    from nba_espn_collector import collect_dashboard
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, output='Send a JSON object with a query mode, team, and season.'), 400
    try:
        result = collect_dashboard(payload.get('mode', 'team'),
                                   str(payload.get('team', 'LAL')).upper(),
                                   str(payload.get('season', datetime.now().year + (datetime.now().month >= 7))),
                                   payload.get('max_games', 10),
                                   str(payload.get('game_id', '')).strip())
        return jsonify(ok=True, **result)
    except (ValueError, TypeError) as exc:
        return jsonify(ok=False, output=str(exc)), 400
    except Exception:
        app.logger.exception('NBA collection failed')
        return jsonify(ok=False, output='Source collection failed. Try again later; unavailable data is not zero absences.'), 502


if __name__ == "__main__":
    print("\n  NBA Data Explorer is running!")
    print("  Open your browser and go to: http://127.0.0.1:5000\n")
    app.run(debug=False, port=5000)
