// Presentation preference only. Never accepts a user-supplied URL.
function apply(result,rows,actor){
 const out={...result};
 const saved=rows.filter(r=>r.source===actor.source&&r.userId===actor.userId&&r.state==='settings').sort((a,b)=>Number(b.id)-Number(a.id));
 let choice='both';try{choice=JSON.parse(saved[0]?.contextJson||'{}').watchPreference||'both';}catch{}
 if(choice==='local'&&out.localJellyfinUrl){out.jellyfinUrl=out.localJellyfinUrl;delete out.localJellyfinUrl;}
 else if(choice==='tailscale'&&out.jellyfinUrl)delete out.localJellyfinUrl;
 return out;
}
if(typeof module!=='undefined')module.exports={apply};
