"""
NBA Data Explorer — Flask UI
Run: python3 app.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

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
    <div class="subtitle">ESPN game box scores · Reported absences</div>
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
          <span class="icon">👥</span> Roster Only
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
      <select id="season">
        <option value="2025">2024–25</option>
        <option value="2024">2023–24</option>
        <option value="2023">2022–23</option>
        <option value="2022">2021–22</option>
        <option value="2021">2020–21</option>
      </select>
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
      <div class="legend-item"><span class="legend-num">1</span> Reported absence categories</div>
      <div class="legend-item"><span class="legend-num">2</span> Minutes played per game</div>
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

<script>
let currentMode = 'team';

function setMode(mode, el) {
  currentMode = mode;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('field-maxgames').style.display = mode === 'team' ? 'flex' : 'none';
  document.getElementById('field-gameid').style.display   = mode === 'game'   ? 'flex' : 'none';
}

async function runQuery() {
  const team      = document.getElementById('team').value;
  const season    = document.getElementById('season').value;
  const maxGames  = document.getElementById('max_games').value;
  const gameId    = document.getElementById('game_id').value.trim();
  const btn       = document.getElementById('runBtn');
  const out       = document.getElementById('outputArea');

  if (currentMode === 'game' && !gameId) {
    alert('Please enter a Game ID.');
    return;
  }

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
    const resp = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();

    document.getElementById('statusDot').className = data.ok ? 'dot done' : 'dot error';
    document.getElementById('statusText').textContent = data.ok ? 'Done' : 'Error';

    if (data.ok) {
      renderResults(data, team, season);
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
function renderResults(data, team, season) {
  const out = document.getElementById('outputArea');
  if (data.mode === 'roster') {
    out.innerHTML = `<h3>Players listed in ${data.collected_games} collected game(s): ${data.roster_count}</h3><p>Players listed in source box scores for the selected games; not a complete season roster or game-day eligibility list.</p>${(data.warnings || []).map(w=>`<p role="alert">${escapeHtml(w)}</p>`).join('')}<pre>${escapeHtml(data.output)}</pre>`;
    return;
  }
  const games = data.mode === 'game' ? [{...data.metrics, game_id:data.game_id}] : data.games;
  const categories = ['injury','illness','other','unknown'];
  const totals = Object.fromEntries(categories.map(c => [c, games.reduce((sum,g) => sum + g.absence_counts[c],0)]));
  const cards = categories.map(c => `<div class="metric-card"><div class="metric-label">${c.toUpperCase()}</div><div class="metric-value">${totals[c]}</div><div class="metric-sub">reported player-game absences</div></div>`).join('');
  const rows = games.map(g => `<tr><td>${escapeHtml(g.date || g.game_id)}</td><td>${escapeHtml(g.opp || team)}</td>${categories.map(c=>`<td>${g.absence_counts[c]}</td>`).join('')}<td>${g.players_dnp}</td><td>${g.players_entered}</td><td>${g.minutes_played}</td><td>${g.overtime_periods}</td></tr>`).join('');
  const details = games.map(g => `<details><summary>${escapeHtml(g.date || g.game_id)} — player absence reasons</summary><p><a href="${escapeHtml(g.source_url)}" target="_blank" rel="noopener">Source box score</a></p><table><thead><tr><th>Player</th><th>Category</th><th>Reported reason</th></tr></thead><tbody>${g.players.filter(p=>!p.played).map(p=>`<tr><td>${escapeHtml(p.player)}</td><td>${escapeHtml(p.absence_category)}</td><td>${escapeHtml(p.reported_absence_reason || 'Not reported')}</td></tr>`).join('') || '<tr><td colspan="3">No nonparticipants listed in source.</td></tr>'}</tbody></table></details>`).join('');
  out.innerHTML = `<p>${games.length} completed game(s) collected${data.requested_games ? ' of '+data.requested_games+' requested' : ''}.</p><div class="results-grid">${cards}</div><p>Categories describe source-reported absences, not new injury events or diagnoses. Generic DNP, missing reasons, and ambiguous reasons remain unknown. Unlisted players are not inferred. Repeated absences count once per player per game. Dates use the venue time zone where known. Team minutes use five players × period lengths, avoiding rounded player-minute totals.</p>${(data.warnings || []).map(w=>`<p role="alert">Collection warning: ${escapeHtml(w)}</p>`).join('')}<div class="game-table-wrap"><table><thead><tr><th>Date / Game</th><th>Team / Opp</th><th>Injury</th><th>Illness</th><th>Other</th><th>Unknown</th><th>Total absent</th><th>Entered</th><th>Team minutes*</th><th>OT</th></tr></thead><tbody>${rows}</tbody></table></div>${details}`;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/run", methods=["POST"])
def run():
    from nba_espn_collector import collect_dashboard
    payload = request.get_json(silent=True) or {}
    try:
        result = collect_dashboard(payload.get('mode', 'team'),
                                   str(payload.get('team', 'LAL')).upper(),
                                   str(payload.get('season', '2025')),
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
