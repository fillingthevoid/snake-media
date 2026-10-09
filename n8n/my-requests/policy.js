// Owned request navigation. Status reads and retention confirmations stay separate.
const usabilityEvidence=require('../request-usability/evidence.js');
const MY_ACTION=/^(?:mr_(?:title_[0-9]{1,3}|page_[0-9]{1,2}|filter_(?:all|downloading|ready|expiring)|refresh|extend|keep|back|close|watch)|wp_(?:local|tailscale|both))$/;
function validActor(a){return a&&['discord','telegram'].includes(a.source)&&/^[1-9][0-9]{0,19}$/.test(a.userId)&&/^-?[1-9][0-9]{0,19}$/.test(a.destinationId);}
function create(a,rows,now,evidence={}){
 if(!validActor(a)||!/^\d+$/.test(a.messageId)||!Number.isFinite(Date.parse(a.requestedAt)))throw Error('Invalid request browser actor');
 const found=new Map();
 for(const r of [...rows].sort((a,b)=>Date.parse(b.requestedAt)-Date.parse(a.requestedAt))){
  if(r.source!==a.source||r.userId!==a.userId||r.userId==='1'||r.state!=='registered'||!r.requestKey||!['movie','tv'].includes(r.mediaType)||!/^\d+$/.test(String(r.mediaId))||typeof r.title!=='string'||!r.title.trim())continue;
  const key=r.mediaType+':'+r.mediaId;if(!found.has(key))found.set(key,{mediaType:r.mediaType,mediaId:String(r.mediaId),title:r.title.slice(0,150)});
 }
 const titles=[...found.values()].slice(0,200);
 if(!titles.length)return {version:1,status:'notice',text:'No requests yet. What would you like to watch?',menuChoices:[{label:'Request something',action:'request'},{label:'Get recommendations',action:'recommend'}]};
 for(const title of titles)Object.assign(title,usabilityEvidence.category(rows.filter(r=>r.source===a.source&&r.userId===a.userId&&r.state==='registered'&&r.requestKey&&r.mediaType===title.mediaType&&String(r.mediaId)===title.mediaId),evidence,now));
 const rank={expiring:0,downloading:1,ready:2,other:3};titles.sort((a,b)=>rank[a.category]-rank[b.category]||(a.category==='expiring'?a.expiry-b.expiry:0));
 return {source:a.source,userId:a.userId,destinationId:a.destinationId,requestKey:['myrequests',a.source,a.destinationId,a.messageId].join(':'),contextJson:JSON.stringify({...a,myRequests:{titles,page:0,selected:null,filter:'all'}}),mediaType:'movie',mediaJson:'{}',state:'preview',claimId:'',choice:'',expiresAt:new Date(now+300000).toISOString()};
}
function advance(row,a,now,claimId){
 if(!validActor(a)||!row||['source','userId','destinationId'].some(k=>row[k]!==a[k])||row.state!=='preview'||!MY_ACTION.test(a.action)||!(Date.parse(row.expiresAt)>now))throw Error('Expired, closed or unowned request browser');
 const ctx=JSON.parse(row.contextJson),b=ctx.myRequests;if(!Array.isArray(b?.titles)||!Number.isInteger(b.page))throw Error('Not a request browser');
 const next={...row,claimId,expiresAt:new Date(now+300000).toISOString()};let statusActor=null,changeActor=null,preference=null;
 const selected=b.titles[b.selected],title=a.action.match(/^mr_title_(\d+)$/),page=a.action.match(/^mr_page_(\d+)$/);
 const visible=b.titles.map((t,i)=>({...t,index:i})).filter(t=>!b.filter||b.filter==='all'||t.category===b.filter||(b.filter==='ready'&&t.ready===true));
 if(a.action==='mr_close')next.state='cancelled';
 else if(a.action==='mr_back'&&selected){if(b.settings)b.settings=false;else b.selected=null;}
 else if(/^mr_filter_(all|downloading|ready|expiring)$/.test(a.action)&&b.selected===null){b.filter=a.action.slice(10);b.page=0;}
 else if(page&&b.selected===null&&Number(page[1])*8<visible.length)b.page=Number(page[1]);
 else if(title&&b.selected===null&&visible.slice(b.page*8,b.page*8+8).some(t=>t.index===Number(title[1])))b.selected=Number(title[1]);
 else if(a.action==='mr_watch'&&selected&&!b.settings)b.settings=true;
 else if(/^wp_(local|tailscale|both)$/.test(a.action)&&b.settings&&selected){
  const choice=a.action.slice(3);b.settings=false;
  preference={source:row.source,userId:row.userId,destinationId:row.destinationId,requestKey:'watchpref:'+row.source+':'+row.userId,contextJson:JSON.stringify({watchPreference:choice}),mediaType:'movie',mediaJson:'{}',state:'settings',claimId,choice:'',expiresAt:'2100-01-01T00:00:00.000Z'};
 }else if(a.action==='mr_refresh'&&selected&&!b.settings){}
 else if(['mr_extend','mr_keep'].includes(a.action)&&selected&&!b.settings){
  changeActor={source:row.source,userId:row.userId,destinationId:row.destinationId,messageId:'myrequests-'+row.id+'-'+claimId,requestedAt:new Date(now).toISOString(),text:a.action==='mr_keep'?'keep':'extend',...selected};
 }else throw Error('Stale request browser action');
 if(next.state==='preview'&&b.selected!==null&&!b.settings)statusActor={source:row.source,userId:row.userId,query:'',...b.titles[b.selected]};
 next.contextJson=JSON.stringify(ctx);return {record:next,statusActor,changeActor,preference};
}
function card(row,now,status=null){
 if(row.version)return row;
 if(!row?.id||row.state!=='preview'||!(Date.parse(row.expiresAt)>now))return {version:1,status:'notice',text:row?.state==='cancelled'?'My requests closed.':'This request menu was already handled. Use /status again.'};
 const b=JSON.parse(row.contextJson).myRequests,selected=b.titles[b.selected];
 const out={version:1,status:'confirmation',pendingId:String(row.id),text:'My requests — choose a title.',choices:[]};
 if(selected&&b.settings){
  out.text='Which Watch address should Snake Media use for you on this platform?\nLocal is for your home network. Tailscale is for devices on your Tailscale network.';
  out.choices=[{label:'Local',action:'wp_local'},{label:'Tailscale',action:'wp_tailscale'},{label:'Show both',action:'wp_both'},{label:'Back',action:'mr_back'}];
 }else if(selected){
  out.text=typeof status?.text==='string'?status.text.slice(0,1700):selected.title+'\nStatus is temporarily unavailable. Use Refresh to try again.';
  for(const field of ['posterUrl','jellyfinUrl','localJellyfinUrl'])if(typeof status?.[field]==='string')out[field]=status[field];
  out.choices=[{label:'Refresh',action:'mr_refresh'},{label:'Extend',action:'mr_extend'},{label:'Keep permanently',action:'mr_keep'},{label:'Watch address',action:'mr_watch'},{label:'Back',action:'mr_back'}];
 }else{
  const visible=b.titles.map((t,i)=>({...t,index:i})).filter(t=>!b.filter||b.filter==='all'||t.category===b.filter||(b.filter==='ready'&&t.ready===true));
  out.text+='\nSaved tracking snapshot; open a title for live status. Ready may mean some episodes are available.\nPage '+(b.page+1)+' of '+Math.max(1,Math.ceil(visible.length/8))+'.';
  if(!visible.length){out.text+='\nNo titles in this category. Choose All, request something or get recommendations.';out.menuChoices=[{label:'Request something',action:'request'},{label:'Get recommendations',action:'recommend'}];}
  out.choices=visible.slice(b.page*8,b.page*8+8).map(t=>({label:((t.mediaType==='tv'?'TV: ':'Movie: ')+t.title+(b.titles.some(other=>other.title===t.title&&other.mediaType===t.mediaType&&other.mediaId!==t.mediaId)?' #'+t.mediaId:'')).slice(0,80),action:'mr_title_'+t.index}));
  out.choices.push(...[['all','All'],['downloading','Downloading'],['ready','Ready to watch'],['expiring','Expiring soon']].map(([action,label])=>({label,action:'mr_filter_'+action})));
  if(b.page>0)out.choices.push({label:'Previous',action:'mr_page_'+(b.page-1)});
  if((b.page+1)*8<visible.length)out.choices.push({label:'Next',action:'mr_page_'+(b.page+1)});
 }
 out.choices.push({label:'Close',action:'mr_close'});return out;
}
if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};
