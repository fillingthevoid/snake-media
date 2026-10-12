// Post-commit presentation from an owned, read-only status snapshot.
function accepted(r,snapshot){
 if(r?.busy===true||r?.status!=='notice'||!['movie','tv'].includes(r.mediaType)||!r.requestKey)return r;
 const a=snapshot?.availability,valid=a&&Number.isSafeInteger(a.total)&&a.total>0&&['available','imported','downloading','queued'].every(k=>Number.isSafeInteger(a[k]??0)&&(a[k]??0)>=0&&(a[k]??0)<=a.total);
 const header=(r.mediaType==='tv'?'📺 ':'🎬 ')+String(r.title||'Your request').slice(0,150);let state;
 if(valid&&a.available===a.total)state='✅ Ready to watch in Jellyfin.';
 else if(valid&&a.available>0)state='✅ Some requested episodes are ready to watch.'+((a.downloading||a.queued)?' More requested episodes are downloading or queued.':' Remaining episodes are monitored for a release.');
 else if(valid&&a.downloading>0)state=r.repeatRequest?'⬇️ Already downloading. No action needed.':'⬇️ Downloading. No action needed.';
 else if(valid&&a.queued>0)state='⏳ Already queued; waiting for download or import to finish.';
 else if(valid&&a.imported>0)state='📥 Imported; waiting for Jellyfin. Use My requests to check again.';
 else if(r.searchStarted===true)state=r.repeatRequest?'🔎 Searching again for the requested media.':'🔎 Finding an acceptable release.';
 else state='Your request is tracked. Use My requests to check availability.';
 if(!valid)state+=' Live availability is temporarily unavailable.';
 const out={version:1,status:'notice',text:header+'\n\n'+state,menuChoices:[{label:'My requests',action:'status'}]};
 if(r.mediaType==='tv')out.text+='\nNew episodes and future seasons remain monitored.';
 for(const field of ['posterUrl','jellyfinUrl','localJellyfinUrl'])if(typeof snapshot?.[field]==='string')out[field]=snapshot[field];
 return out;
}
if(typeof module!=='undefined')module.exports={accepted};
