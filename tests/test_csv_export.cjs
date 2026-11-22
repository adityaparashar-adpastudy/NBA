const assert=require('node:assert/strict');
const {rows,csv,columns,playingTime}=require('../static/injury_export.js');
const context={team:'LAL',teamName:'Los Angeles Lakers',season:2027,requestedGames:10,exportedAt:'2026-11-22T00:00:00Z'};
const game={team_code:'LAL',team_name:'Los Angeles Lakers',season_end_year:2025,game_id:'401704628',date:'2024-10-22',date_timezone:'America/Los_Angeles',opp:'MIN',wl:'W',source_url:'https://www.espn.com/nba/boxscore/_/gameId/401704628',players:[
 {player:'Played Player',player_id:'1',played:true,minutes:'38',participation_status:'played'},
 {player:'Ill Player',player_id:'2',played:false,absence_category:'illness',reported_absence_reason:'Illness',participation_status:'absent'},
 {player:'Unknown Reason',player_id:'3',played:false,absence_category:'unknown'},
 {player:'Uncertain Player',player_id:'4',played:null,absence_category:null,reported_minutes:'--',source_did_not_play:false}
],official_report:{status:'available',report_at:'2024-10-22T17:30:00-04:00',records:[
 {player_full_name:'José "Example", Jr.',player_id:null,reported_status:'Out',category:'injury',reported_reason:'Injury/Illness - Left knee, soreness\nFollow-up',actual_participation:'not_listed_in_box_score',source_url:'https://ak-static.cms.nba.com/example.pdf',report_at:'2024-10-22T17:30:00-04:00',join_method:'unmatched'},
 {player_full_name:'Played Player',player_id:'1',reported_status:'Questionable',category:'injury',reported_reason:'Injury/Illness - Left ankle sprain',actual_participation:'played',reported_minutes:'38',source_url:'https://ak-static.cms.nba.com/example.pdf',report_at:'2024-10-22T17:30:00-04:00',join_method:'exact_normalized_name'},
 {player_full_name:'Other Player',reported_status:'Out',category:'other',reported_reason:'G League - Two-Way',actual_participation:'not_listed_in_box_score'}
]}};
let checks=0;
const injuries=rows([game],context,'injury');assert.equal(injuries.length,2);checks++;
assert.equal(injuries[0].player_full_name,'José "Example", Jr.');assert.equal(injuries[0].team,'Los Angeles Lakers');checks++;
assert.equal(injuries[0].season_end_year,2025);assert.equal(injuries[0].season,'2024-25');checks++;
assert.equal(injuries[0].requested_games,10);assert.equal(injuries[0].source,'Official NBA pregame injury report');assert.match(injuries[0].coverage_note,/not unique injury events/);checks++;
assert.equal(injuries[1].participation_status,'played');assert.equal(injuries[1].playing_time_minutes,38);assert.equal(injuries[1].minutes_precision,'rounded_whole_minutes');checks++;
assert.equal(injuries[0].playing_time_minutes,'');assert.equal(injuries[0].minutes_precision,'unavailable');checks++;
assert.equal(rows([game],context,'reports').length,3);checks++;
assert.equal(rows([{...game,official_report:{status:'unavailable',records:[]}}],context,'injury').length,0);checks++;
const all=rows([game],context,'all');assert.equal(all.length,3);assert.equal(all[2].record_type,'participation_unknown');checks++;
const playing=rows([game],context,'playing');assert.equal(playing.length,4);assert.equal(playing[1].playing_time_minutes,0);assert.equal(playing[3].playing_time_minutes,'');checks++;
assert.deepEqual(playingTime('37:35',true),{minutes:37+35/60,precision:'seconds_reported'});assert.equal(playingTime('37:99',true).precision,'unavailable');checks++;
const text=csv(injuries);assert.ok(text.startsWith('\ufeff'));assert.match(text,/José ""Example"", Jr\./);assert.match(text,/soreness\nFollow-up/);checks++;
const formula=csv([{player_full_name:'=1+1',reported_absence_reason:'@SUM(1)'}]);assert.ok(formula.includes('"\'=1+1"'));assert.ok(formula.includes('"\'@SUM(1)"'));checks++;
assert.ok(columns.includes('report_at'));assert.ok(columns.includes('minutes_precision'));assert.ok(columns.includes('official_report_games_available'));checks++;
console.log(checks+' CSV checks passed');
