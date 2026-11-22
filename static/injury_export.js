/* CSV rows describe the loaded source records, not a complete injury registry. */
(function (root) {
  'use strict';
  const columns = ['season','season_end_year','team','team_code','player_full_name','player_id','game_date','date_timezone','game_id','opponent','game_result','record_type','absence_category','reported_absence_reason','participation_status','reported_minutes','source_did_not_play','source','source_url','loaded_games','requested_games','coverage_note','exported_at_utc'];
  const coverage = 'Partial ESPN box-score records; some injured inactive players are omitted by the source. Counts are player-game absences, not new injury events. This is not a complete injury registry.';
  function cell(value) {
    let text = String(value ?? '');
    // Keep source strings from being interpreted as spreadsheet formulas.
    if (/^[\s]*[=+\-@]/.test(text) || /^[\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function rows(games, context, scope) {
    const result = [];
    for (const game of games) {
      for (const player of game.players || []) {
        if (scope === 'injury' ? !(player.played === false && player.absence_category === 'injury') : player.played === true) continue;
        const year = Number(game.season_end_year || context.season);
        result.push({season:year ? `${year-1}-${String(year).slice(-2)}` : '', season_end_year:year || '',
          team:game.team_name || context.teamName, team_code:game.team_code || context.team,
          player_full_name:player.player, player_id:player.player_id, game_date:game.date,
          date_timezone:game.date_timezone, game_id:game.game_id, opponent:game.opponent_name || game.opp,
          game_result:game.wl, record_type:player.played === null ? 'participation_unknown' : 'reported_absence',
          absence_category:player.absence_category, reported_absence_reason:player.reported_absence_reason,
          participation_status:player.participation_status || (player.played === null ? 'unknown' : 'absent'),
          reported_minutes:player.reported_minutes ?? player.minutes, source_did_not_play:player.source_did_not_play,
          source:'ESPN game box score', source_url:game.source_url, loaded_games:games.length,
          requested_games:context.requestedGames || games.length, coverage_note:coverage,
          exported_at_utc:context.exportedAt || new Date().toISOString()});
      }
    }
    return result;
  }
  function csv(records) {
    return '\ufeff' + [columns, ...records.map(record => columns.map(key => record[key]))].map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
  }
  const api = {columns,coverage,rows,csv};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.NBAInjuryExport = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
