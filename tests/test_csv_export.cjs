const assert = require('node:assert/strict');
const {rows,csv,columns} = require('../static/injury_export.js');
const context={team:'LAL',teamName:'Los Angeles Lakers',season:2027,requestedGames:10,exportedAt:'2026-11-22T00:00:00Z'};
const game={team_code:'LAL',team_name:'Los Angeles Lakers',season_end_year:2025,game_id:'401704628',date:'2024-10-22',date_timezone:'America/Los_Angeles',opp:'MIN',wl:'W',source_url:'https://www.espn.com/nba/boxscore/_/gameId/401704628',players:[
 {player:'José "Example", Jr.',player_id:'1',played:false,absence_category:'injury',reported_absence_reason:'Left knee, soreness\nFollow-up',source_did_not_play:true,participation_status:'absent'},
 {player:'Ill Player',player_id:'2',played:false,absence_category:'illness',reported_absence_reason:'Illness'},
 {player:'Unknown Reason',player_id:'3',played:false,absence_category:'unknown'},
 {player:'Uncertain Player',player_id:'4',played:null,absence_category:null,reported_minutes:'--',source_did_not_play:false},
 {player:'Played Player',player_id:'5',played:true,absence_category:null}
]};
let checks=0;
const injuries=rows([game],context,'injury');
assert.equal(injuries.length,1);checks++;
assert.equal(injuries[0].player_full_name,'José "Example", Jr.');assert.equal(injuries[0].team,'Los Angeles Lakers');checks++;
assert.equal(injuries[0].season_end_year,2025);assert.equal(injuries[0].season,'2024-25');checks++;
assert.equal(injuries[0].requested_games,10);assert.match(injuries[0].coverage_note,/Partial/);checks++;
const all=rows([game],context,'all');assert.equal(all.length,4);assert.equal(all[3].record_type,'participation_unknown');assert.equal(all[3].absence_category,null);checks++;
const text=csv(injuries);assert.ok(text.startsWith('\ufeff'));assert.match(text, /José ""Example"", Jr\./);assert.match(text,/soreness\nFollow-up/);checks++;
const formula=csv([{player_full_name:'=1+1',reported_absence_reason:'@SUM(1)'}]);assert.ok(formula.includes('"\'=1+1"'));assert.ok(formula.includes('"\'@SUM(1)"'));checks++;
assert.ok(columns.includes('source_url'));assert.ok(columns.includes('exported_at_utc'));assert.ok(columns.includes('reported_absence_reason'));checks++;
console.log(checks+' CSV checks passed');
