"""
NBA Data Explorer — Web UI
===========================
A simple Flask web server that wraps basketball_reference_scraper_v2.py
and serves a browser-based UI.

Requirements:
    pip3 install flask pandas requests beautifulsoup4 lxml

Usage:
    python3 app.py
    Then open your browser to: http://localhost:5000
"""

from flask import Flask, render_template_string, request, jsonify
import subprocess
import sys
import os

app = Flask(__name__)

SCRIPT = os.path.join(os.path.dirname(__file__), "basketball_reference_scraper_v2.py")

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NBA Data Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0d0f0e;
    --surface: #161918;
    --border: #2a2e2c;
    --accent: #c8f560;
    --accent-dim: #8aaa3a;
    --text: #e8ede9;
    --text-muted: #6b7870;
    --text-dim: #3d4442;
    --danger: #ff6b5b;
    --mono: 'DM Mono', monospace;
    --serif: 'Libre Baskerville', serif;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    padding: 2rem;
  }

  header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 2.5rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
  }

  header h1 {
    font-family: var(--serif);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.02em;
  }

  header span {
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 1.5rem;
    max-width: 1100px;
  }

  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.25rem;
  }

  .panel-label {
    font-size: 0.65rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 1.25rem;
  }

  .mode-btn {
    display: block;
    width: 100%;
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0.6rem 0.75rem;
    font-family: var(--mono);
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
    margin-bottom: 4px;
    transition: all 0.15s;
  }

  .mode-btn:hover { color: var(--text); border-color: var(--border); }

  .mode-btn.active {
    background: rgba(200, 245, 96, 0.08);
    border-color: var(--accent-dim);
    color: var(--accent);
  }

  .mode-btn .cmd { font-size: 0.65rem; color: var(--text-dim); display: block; margin-top: 2px; }
  .mode-btn.active .cmd { color: var(--accent-dim); }

  .divider { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }

  .field { margin-bottom: 1rem; }
  .field label { font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 6px; }

  .field select, .field input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
    font-family: var(--mono);
    font-size: 0.8rem;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s;
  }

  .field select:focus, .field input:focus { border-color: var(--accent-dim); }
  .field select option { background: var(--bg); }

  .run-btn {
    width: 100%;
    background: var(--accent);
    color: #0d0f0e;
    border: none;
    border-radius: 4px;
    padding: 0.65rem;
    font-family: var(--mono);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
    margin-top: 0.5rem;
  }

  .run-btn:hover { opacity: 0.88; }
  .run-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .output-panel { display: flex; flex-direction: column; }

  .output-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .status {
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--text-muted);
  }

  .status.running { border-color: var(--accent-dim); color: var(--accent); animation: pulse 1.2s infinite; }
  .status.done { border-color: #3a7a3a; color: #7acc7a; }
  .status.error { border-color: var(--danger); color: var(--danger); }

  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

  .output-box {
    flex: 1;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem;
    font-size: 0.74rem;
    line-height: 1.7;
    color: var(--text-muted);
    white-space: pre-wrap;
    overflow-y: auto;
    min-height: 420px;
    max-height: 600px;
  }

  .output-box .line-accent { color: var(--accent); }
  .output-box .line-header { color: var(--text); font-weight: 500; }
  .output-box .line-error { color: var(--danger); }
  .output-box .line-muted { color: var(--text-dim); }

  .placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 380px;
    color: var(--text-dim);
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    flex-direction: column;
    gap: 8px;
  }

  .placeholder-icon {
    width: 32px;
    height: 32px;
    border: 1px solid var(--border);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    margin-bottom: 4px;
  }

  @media (max-width: 700px) {
    .grid { grid-template-columns: 1fr; }
    body { padding: 1rem; }
  }
</style>
</head>
<body>

<header>
  <h1>NBA Data Explorer</h1>
  <span>basketball-reference.com</span>
</header>

<div class="grid">
  <div>
    <div class="panel">
      <div class="panel-label">Query type</div>

      <button class="mode-btn active" onclick="setMode('roster',this)">
        Roster
        <span class="cmd">--roster TEAM</span>
      </button>
      <button class="mode-btn" onclick="setMode('game',this)">
        Game boxscore
        <span class="cmd">--game_id ID</span>
      </button>
      <button class="mode-btn" onclick="setMode('season',this)">
        Season summary
        <span class="cmd">--team TEAM</span>
      </button>
      <button class="mode-btn" onclick="setMode('injuries',this)">
        Injury transactions
        <span class="cmd">--injuries TEAM</span>
      </button>
      <button class="mode-btn" onclick="setMode('season_games',this)">
        All game IDs
        <span class="cmd">--season_games TEAM</span>
      </button>

      <hr class="divider">

      <div class="field" id="field-team">
        <label>Team</label>
        <select id="team">
          <option>LAL</option><option>BOS</option><option>GSW</option>
          <option>NYK</option><option>MIA</option><option>CHI</option>
          <option>DAL</option><option>DEN</option><option>PHO</option>
          <option>MIL</option><option>OKC</option><option>MIN</option>
          <option>CLE</option><option>IND</option><option>SAC</option>
          <option>HOU</option><option>MEM</option><option>ORL</option>
          <option>ATL</option><option>BKN</option><option>CHA</option>
          <option>DET</option><option>NOP</option><option>POR</option>
          <option>SAS</option><option>TOR</option><option>UTA</option>
          <option>WAS</option><option>LAC</option><option>PHI</option>
        </select>
      </div>

      <div class="field" id="field-game" style="display:none;">
        <label>Game ID</label>
        <input type="text" id="game_id" placeholder="e.g. 202412250LAL" />
        <div style="font-size:0.65rem;color:var(--text-dim);margin-top:5px;">Format: YYYYMMDD0HOMETEAM</div>
      </div>

      <div class="field" id="field-season">
        <label>Season (end year)</label>
        <select id="season">
          <option value="2025" selected>2024-25</option>
          <option value="2024">2023-24</option>
          <option value="2023">2022-23</option>
          <option value="2022">2021-22</option>
        </select>
      </div>

      <div class="field" id="field-maxgames" style="display:none;">
        <label>Max games to fetch</label>
        <select id="max_games">
          <option value="5">5 games</option>
          <option value="10" selected>10 games</option>
          <option value="20">20 games</option>
          <option value="82">Full season (slow)</option>
        </select>
      </div>

      <button class="run-btn" id="run-btn" onclick="runQuery()">Run query</button>
    </div>
  </div>

  <div class="panel output-panel">
    <div class="output-header">
      <div class="panel-label" style="margin:0;">Output</div>
      <div class="status" id="status">ready</div>
    </div>
    <div class="output-box" id="output">
      <div class="placeholder">
        <div class="placeholder-icon">▶</div>
        Select a query type and hit Run
      </div>
    </div>
  </div>
</div>

<script>
let currentMode = 'roster';

function setMode(mode, btn) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  document.getElementById('field-team').style.display = 'block';
  document.getElementById('field-game').style.display = 'none';
  document.getElementById('field-season').style.display = 'block';
  document.getElementById('field-maxgames').style.display = 'none';

  if (mode === 'game') {
    document.getElementById('field-team').style.display = 'none';
    document.getElementById('field-game').style.display = 'block';
    document.getElementById('field-season').style.display = 'none';
  }
  if (mode === 'season') {
    document.getElementById('field-maxgames').style.display = 'block';
  }
}

function setStatus(s, label) {
  const el = document.getElementById('status');
  el.className = 'status ' + s;
  el.textContent = label;
}

function colorize(text) {
  return text.split('\\n').map(line => {
    if (line.startsWith('──') || line.startsWith('Fetching')) return `<span class="line-accent">${line}</span>`;
    if (line.trim().startsWith('Traceback') || line.includes('Error') || line.includes('error')) return `<span class="line-error">${line}</span>`;
    if (line.trim() === '') return line;
    return `<span>${line}</span>`;
  }).join('\\n');
}

async function runQuery() {
  const btn = document.getElementById('run-btn');
  const out = document.getElementById('output');
  btn.disabled = true;
  setStatus('running', 'running...');
  out.innerHTML = '<span style="color:var(--text-dim)">Fetching data — Basketball Reference may take a few seconds...</span>';

  const body = {
    mode: currentMode,
    team: document.getElementById('team').value,
    game_id: document.getElementById('game_id').value,
    season: document.getElementById('season').value,
    max_games: document.getElementById('max_games').value,
  };

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.error) {
      out.innerHTML = colorize(data.output || data.error);
      setStatus('error', 'error');
    } else {
      out.innerHTML = colorize(data.output);
      setStatus('done', 'done');
    }
  } catch(e) {
    out.innerHTML = `<span class="line-error">Could not connect to server. Make sure app.py is running.</span>`;
    setStatus('error', 'error');
  }

  btn.disabled = false;
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
    data = request.json
    mode = data.get("mode")
    team = data.get("team", "LAL")
    game_id = data.get("game_id", "")
    season = data.get("season", "2025")
    max_games = data.get("max_games", "10")

    cmd = [sys.executable, SCRIPT]

    if mode == "roster":
        cmd += ["--roster", team, "--season", season]
    elif mode == "game":
        cmd += ["--game_id", game_id]
    elif mode == "season":
        cmd += ["--team", team, "--season", season, "--max_games", max_games]
    elif mode == "injuries":
        cmd += ["--injuries", team, "--season", season]
    elif mode == "season_games":
        cmd += ["--season_games", team, "--season", season]
    else:
        return jsonify({"error": "Unknown mode", "output": "Unknown query mode."})

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        return jsonify({"output": output, "error": None if result.returncode == 0 else "Script error"})
    except subprocess.TimeoutExpired:
        return jsonify({"output": "Timed out — try fewer games.", "error": "timeout"})
    except Exception as e:
        return jsonify({"output": str(e), "error": str(e)})

if __name__ == "__main__":
    print("\n NBA Data Explorer is running!")
    print(" Open your browser and go to: http://localhost:5000\n")
    app.run(debug=False, port=5000)
