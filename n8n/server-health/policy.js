const SERVICES=['Jellyfin','Radarr','Sonarr','Prowlarr','SABnzbd','qBittorrent','n8n'];
function command(text){return typeof text==='string'&&/^\/?serverstatus\s*$/i.test(text.trim());}
function report(r,now=Date.now()){
 if(!r||r.version!==1||!Number.isFinite(r.checkedAt)||!r.host||!r.storage||!r.services||!r.playback)return '⚠️ Server health is temporarily unavailable.';
 if(now-r.checkedAt>120000||now<r.checkedAt-5000)return '⚠️ Server health report is out of date. Please try again.';
 const num=n=>Number.isFinite(n)&&n>=0, h=r.host;
 const disks=r.storage.disks;
 if(![h.load1,h.cores,h.memoryUsed,h.memoryTotal,h.uptimeHours].every(num)||h.cores<1||h.memoryTotal<=0||!Array.isArray(disks)||disks.length!==3||!['Main','SSD','Pool'].every(label=>disks.some(d=>d&&d.label===label)))return '⚠️ Server health is temporarily unavailable.';
 const highLoad=h.load1>h.cores*1.5,highMemory=h.memoryUsed/h.memoryTotal>0.9;
 const activeKnown=Number.isInteger(r.playback.active)&&r.playback.active>=0;
 const problems=highLoad||highMemory||!activeKnown||SERVICES.some(s=>r.services[s]!==true)||r.storage.guard!==true||r.playback.sample!=='ok'||disks.some(d=>!num(d.freeGiB)||!num(d.totalGiB)||d.freeGiB<50);
 const lines=[(problems?'⚠️ Checks need attention':'✅ Server checks passed'),`CPU load: ${h.load1.toFixed(2)} / ${h.cores} cores · Memory: ${h.memoryUsed.toFixed(1)} / ${h.memoryTotal.toFixed(1)} GiB`,`Uptime: ${Math.floor(h.uptimeHours)} hours`,'',r.storage.guard===true?'💾 Storage mounts verified':'⚠️ Storage mount check failed'];
 if(highLoad)lines.splice(3,0,'⚠️ High CPU load');
 if(highMemory)lines.splice(3,0,'⚠️ Memory usage above 90%');
 for(const d of disks)lines.push(num(d.freeGiB)&&num(d.totalGiB)?`${d.freeGiB<50?'⚠️ ':''}${d.label}: ${Math.floor(d.freeGiB)} / ${Math.floor(d.totalGiB)} GiB free`:`${d.label}: capacity unavailable`);
 lines.push('',...SERVICES.map(s=>`${r.services[s]===true?'🟢':'🔴'} ${s}`),'');
 lines.push(Number.isInteger(r.playback.active)&&r.playback.active>=0?`▶️ ${r.playback.active} active playback session(s)`:'⚠️ Active playback check unavailable');
 lines.push(r.playback.sample==='ok'?'✅ Jellyfin sample stream passed':r.playback.sample==='no_media'?'⚠️ No suitable media available for a playback sample':'⚠️ Jellyfin sample stream failed or unavailable');
 lines.push('Client playback and transcoding were not tested.','Checked within the last minute.');
 return lines.join('\n').slice(0,1800);
}
if(typeof module!=='undefined')module.exports={command,report};
