const SERVICES=['Jellyfin','Radarr','Sonarr','Prowlarr','SABnzbd','qBittorrent','n8n'];
function command(text){return typeof text==='string'&&/^\/?serverstatus\s*$/i.test(text.trim());}
function report(r,now=Date.now()){
 if(!r||r.version!==1||!Number.isFinite(r.checkedAt)||!r.host||!r.storage||!r.services||!r.playback)return '⚠️ Server health is temporarily unavailable.';
 if(now-r.checkedAt>120000||now<r.checkedAt-5000)return '⚠️ Server health report is out of date. Please try again.';
 const num=n=>Number.isFinite(n)&&n>=0, h=r.host;
 const disks=r.storage.disks;
 if(![h.load1,h.cores,h.memoryUsed,h.memoryTotal,h.uptimeHours].every(num)||h.cores<1||h.memoryTotal<=0||!Array.isArray(disks)||disks.length!==3||!['Main','SSD','Pool'].every(label=>disks.some(d=>d&&d.label===label)))return '⚠️ Server health is temporarily unavailable.';
 const cpu=h.cpu,cpuOk=cpu?.available===true&&num(cpu.usagePercent)&&cpu.usagePercent<=100&&num(cpu.sampleSeconds)&&cpu.sampleSeconds>0&&cpu.sampleSeconds<=10;
 const highCpu=cpuOk&&cpu.usagePercent>90,highLoad=h.load1>h.cores*1.5,highMemory=h.memoryUsed/h.memoryTotal>0.9;
 const activeKnown=Number.isInteger(r.playback.active)&&r.playback.active>=0;
 const problems=highCpu||highLoad||highMemory||!activeKnown||SERVICES.some(s=>r.services[s]!==true)||r.storage.guard!==true||r.playback.sample!=='ok'||disks.some(d=>!num(d.freeGiB)||!num(d.totalGiB)||d.freeGiB<50);
 const lines=[(problems?'⚠️ Checks need attention':'✅ Server checks passed'),cpuOk?`CPU: ${cpu.usagePercent.toFixed(1)}% across ${h.cores} cores (${cpu.sampleSeconds.toFixed(0)}s sample)`:'CPU: usage unavailable',`Load average (1 minute): ${h.load1.toFixed(2)}`,`Memory: ${h.memoryUsed.toFixed(1)} / ${h.memoryTotal.toFixed(1)} GiB (${(100*h.memoryUsed/h.memoryTotal).toFixed(0)}%)`,`Uptime: ${Math.floor(h.uptimeHours)} hours`];
 const g=r.gpu,n=r.network;
 const gpuOk=g?.available===true&&typeof g.name==='string'&&/^[A-Za-z0-9 ()._-]{1,100}$/.test(g.name)&&[g.utilizationPercent,g.memoryUsedMiB,g.memoryTotalMiB].every(num)&&g.utilizationPercent<=100&&g.memoryTotalMiB>0&&g.memoryUsedMiB<=g.memoryTotalMiB;
 const networkOk=n?.available===true&&num(n.uploadMbps)&&num(n.sampleSeconds)&&n.sampleSeconds>0&&n.sampleSeconds<=10;
 lines.push(gpuOk?`GPU: ${g.name} · ${g.utilizationPercent.toFixed(0)}% · VRAM: ${(g.memoryUsedMiB/1024).toFixed(1)} / ${(g.memoryTotalMiB/1024).toFixed(1)} GiB`:'GPU: usage unavailable');
 const percent=value=>num(value)&&value<=100?`${value.toFixed(0)}%`:'unavailable';
 if(gpuOk)lines.push(`Temperature: ${num(g.temperatureC)&&g.temperatureC<=150?`${g.temperatureC.toFixed(0)}°C`:'unavailable'} · Encode: ${percent(g.encoderPercent)} · Decode: ${percent(g.decoderPercent)}`);
 lines.push(networkOk?`Server upload: ${n.uploadMbps.toFixed(2)} Mbps (${n.sampleSeconds.toFixed(0)}s sample; includes LAN traffic)`:'Server upload: usage unavailable');
 const averageOk=n?.available===true&&num(n.uploadAverageMbps)&&num(n.averageSeconds)&&n.averageSeconds>=60&&n.averageSeconds<=70;
 lines.push(averageOk?`1-minute average: ${n.uploadAverageMbps.toFixed(2)} Mbps`:networkOk&&n.uploadAverageMbps===null&&n.averageSeconds===0?'1-minute average: warming up':'1-minute average: unavailable');
 if(highCpu)lines.push('⚠️ CPU usage above 90%');
 if(highLoad)lines.push('⚠️ High CPU load average');
 if(highMemory)lines.push('⚠️ Memory usage above 90%');
 lines.push('',r.storage.guard===true?'💾 Storage mounts verified':'⚠️ Storage mount check failed');
 for(const d of disks)lines.push(num(d.freeGiB)&&num(d.totalGiB)?`${d.freeGiB<50?'⚠️ ':''}${d.label}: ${Math.floor(d.freeGiB)} / ${Math.floor(d.totalGiB)} GiB free`:`${d.label}: capacity unavailable`);
 lines.push('',...SERVICES.map(s=>`${r.services[s]===true?'🟢':'🔴'} ${s}`),'');
 lines.push(Number.isInteger(r.playback.active)&&r.playback.active>=0?`▶️ ${r.playback.active} active playback session(s)`:'⚠️ Active playback check unavailable');
 lines.push(r.playback.sample==='ok'?'✅ Jellyfin sample stream passed':r.playback.sample==='no_media'?'⚠️ No suitable media available for a playback sample':'⚠️ Jellyfin sample stream failed or unavailable');
 lines.push('Client playback and transcoding were not tested.',`Health and GPU checked ${Math.max(0,Math.floor((now-r.checkedAt)/1000))} seconds ago.`);
 return lines.join('\n').slice(0,1800);
}
if(typeof module!=='undefined')module.exports={command,report};
