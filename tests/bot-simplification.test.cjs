const {test}=require('node:test'),a=require('node:assert/strict');
const health=require('../n8n/server-health/policy.js'),p=require('../n8n/polish/presentation/policy.js');
const f=()=>({version:1,checkedAt:100000,host:{load1:0.1,cores:12,memoryUsed:4,memoryTotal:30,uptimeHours:10},storage:{guard:true,disks:[{label:'Main',freeGiB:300,totalGiB:1800},{label:'SSD',freeGiB:450,totalGiB:465},{label:'Pool',freeGiB:750,totalGiB:2265}]},services:{Jellyfin:true,Radarr:true,Sonarr:true,Prowlarr:true,SABnzbd:true,qBittorrent:true,n8n:true},playback:{active:0,sample:'ok'}});
test('short health reply exposes details and actual failures without hiding stale data',()=>{
 const r=f();let out=health.reply(r,false,110000);a.match(out.text,/checks passed/);a.doesNotMatch(out.text,/Memory:|Uptime:/);a.equal(out.menuChoices[0].action,'serverdetails');
 out=health.reply(r,true,110000);a.match(out.text,/Memory:|Uptime:/);a.equal(out.menuChoices[0].action,'serverstatus');
 r.services.Radarr=false;out=health.reply(r,false,110000);a.match(out.text,/Radarr/);a.doesNotMatch(out.text,/checks passed/);
 a.match(health.reply(r,false,400000).text,/out of date/);
});
test('download progress never regresses to a no-release notice and identical title requests do not repeat stages',()=>{
 const r={requestKey:'discord:3:4',source:'discord',userId:'2',destinationId:'3',mediaType:'tv',mediaId:'8',messageId:'4',requestedAt:'2026-10-01T00:00:00Z'},now=Date.parse('2026-10-01T01:00:00Z');
 const notice=p.progressNotice(r,{text:'Example',progressState:'downloading'},[],now);
 a.equal(p.progressNotice(r,{text:'Example',progressState:'waiting'},[notice],now),null);
 a.equal(p.progressNotice({...r,requestKey:'discord:3:5',messageId:'5'},{text:'Example',progressState:'downloading'},[notice],now),null);
 a.notEqual(p.progressNotice({...r,userId:'9',requestKey:'discord:3:6'},{text:'Example',progressState:'downloading'},[notice],now),null);
});
