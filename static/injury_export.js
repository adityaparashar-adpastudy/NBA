(function (root) {
  'use strict';
  const columns=['season','season_end_year','team','team_code','player_full_name','player_id','game_date','date_timezone','game_id','opponent','game_result','record_type','absence_category','reported_status','reported_absence_reason','participation_status','reported_minutes','playing_time_minutes','minutes_precision','source_did_not_play','report_at','identity_join_method','source','source_url','playing_time_source_url','loaded_games','requested_games','official_report_games_available','coverage_note','exported_at_utc'];
  const coverage='Selected available official pregame snapshots only; later updates and unreported injuries may exist. Records are player-game designations, not unique injury events. Missing reports are not zero injuries.';
  const boxCoverage='Partial ESPN box-score data; inactive injured players may be omitted. Minutes may be rounded, and are not verified exact second-level exposure.';
  function cell(value){let text=String(value??'');if(/^[\s]*[=+\-@]/.test(text)||/^[\t\r]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';}
  function playingTime(raw,played){
    if(played===false)return {minutes:0,precision:'did_not_play'};
    if(played===null||raw===null||raw===undefined)return {minutes:'',precision:'unavailable'};
    const text=String(raw);
    if(/^\d+:\d{2}$/.test(text)){const [m,s]=text.split(':').map(Number);return s<60?{minutes:m+s/60,precision:'seconds_reported'}:{minutes:'',precision:'unavailable'};}
    if(/^\d+$/.test(text))return {minutes:Number(text),precision:'rounded_whole_minutes'};
    if(/^\d+\.\d+$/.test(text))return {minutes:Number(text),precision:'reported_decimal_minutes'};
    return {minutes:'',precision:'unavailable'};
  }
  function rows(games,context,scope){
    const result=[];
    const covered=games.filter(g=>g.official_report?.status==='available').length;
    for(const game of games){
      const official=scope==='injury'||scope==='reports';
      const candidates=official?(game.official_report?.status==='available'?game.official_report.records:[]):game.players||[];
      for(const player of candidates){
        if(scope==='injury'&&player.category!=='injury')continue;
        if(scope==='all'&&player.played===true)continue;
        const year=Number(game.season_end_year||context.season);
        const played=official?(player.actual_participation==='played'?true:player.actual_participation==='absent'?false:null):player.played;
        const raw=official?player.reported_minutes:player.reported_minutes??player.minutes;
        const time=playingTime(raw,played);
        result.push({season:year?`${year-1}-${String(year).slice(-2)}`:'',season_end_year:year||'',team:game.team_name||context.teamName,team_code:game.team_code||context.team,
          player_full_name:official?player.player_full_name:player.player,player_id:player.player_id,game_date:game.date,date_timezone:game.date_timezone,game_id:game.game_id,opponent:game.opponent_name||game.opp,game_result:game.wl,
          record_type:official?'official_pregame_designation':scope==='playing'?'player_game_participation':player.played===null?'participation_unknown':'boxscore_reported_absence',
          absence_category:official?player.category:player.absence_category,reported_status:official?player.reported_status:'',reported_absence_reason:official?player.reported_reason:player.reported_absence_reason,
          participation_status:official?player.actual_participation:player.participation_status||(played===true?'played':played===false?'absent':'unknown'),reported_minutes:raw,playing_time_minutes:time.minutes,minutes_precision:time.precision,
          source_did_not_play:official?'':player.source_did_not_play,report_at:official?player.report_at:'',identity_join_method:official?player.join_method:'source_player_id',
          source:official?'Official NBA pregame injury report':'ESPN game box score',source_url:official?player.source_url:game.source_url,playing_time_source_url:game.source_url,loaded_games:games.length,requested_games:context.requestedGames||games.length,official_report_games_available:covered,
          coverage_note:official?coverage:boxCoverage,exported_at_utc:context.exportedAt||new Date().toISOString()});
      }
    }
    return result;
  }
  function csv(records){return '\ufeff'+[columns,...records.map(record=>columns.map(key=>record[key]))].map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';}
  const api={columns,coverage,rows,csv,playingTime};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.NBAInjuryExport=api;
})(typeof globalThis!=='undefined'?globalThis:this);
