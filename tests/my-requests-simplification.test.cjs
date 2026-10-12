const {test}=require('node:test'),a=require('node:assert/strict');
const nav=require('../n8n/my-requests/policy.js'),ret=require('../n8n/retention-controls/policy.js'),status=require('../n8n/status/policy.js');
const now=Date.parse('2026-10-11T18:00:00Z');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:new Date(now).toISOString()};
const request={...actor,state:'registered',requestKey:'r',mediaType:'movie',mediaId:'10',title:'Example',retentionDays:7};
function row(){let r={...nav.create(actor,[request],now),id:7};return nav.advance(r,{...actor,action:'mr_title_0'},now,'a').record;}
const snapshot={text:'Example\nFull details and episode counts',summaryText:'Example\nAvailable\nExpiry: Oct 18',retentionActions:{canExtend:true,canKeep:true,permanent:false}};
test('title cards offer direct expiry choices and switch summary/details on the owned original',()=>{
 let r=row();let card=nav.card(r,now,snapshot);
 a.equal(card.text,snapshot.summaryText);a.ok(card.choices.some(c=>c.action==='mr_extend_7'));a.ok(card.choices.some(c=>c.action==='mr_extend_30'));
 r=nav.advance(r,{...actor,action:'mr_details'},now,'b').record;a.equal(nav.card(r,now,snapshot).text,snapshot.text);
 r=nav.advance(r,{...actor,action:'mr_summary'},now,'c').record;a.equal(nav.card(r,now,snapshot).text,snapshot.summaryText);
 for(const days of [7,30]){const result=nav.advance(r,{...actor,action:'mr_extend_'+days},now,'d');a.equal(result.changeActor.mediaId,'10');a.equal(result.changeActor.text,'extend '+days+' days');a.equal(result.record.state,'preview');const p=ret.prepareChange(result.changeActor,[request],[],now);a.equal(p.change.days,days);a.equal(p.change.mediaId,'10');}
 a.throws(()=>nav.advance(r,{...actor,userId:'222',action:'mr_extend_7'},now,'x'));
});
test('permanent titles hide retention actions and unavailable status cannot invent eligibility',()=>{
 const r=row();const c=nav.card(r,now,{...snapshot,retentionActions:{permanent:true,canExtend:false,canKeep:false}});
 a.ok(!c.choices.some(c=>/extend|keep/.test(c.action)));a.ok(c.choices.some(c=>c.action==='mr_details'));
 a.ok(!nav.card(r,now,{text:'Unavailable'}).choices.some(c=>/extend|keep/.test(c.action)));
});
test('live compact projection distinguishes own permanent requests from shared protected files',()=>{
 const file={id:5,path:'/library/movies/Example/a.mkv',dateAdded:new Date(now-86400000).toISOString()};
 const input={requests:[request],records:[{key:'file:movie:10:5',payloadJson:JSON.stringify({state:'tracked',path:file.path,importedAt:file.dateAdded,checkedAt:new Date(now).toISOString(),expiresAt:new Date(now+7*86400000).toISOString()})}],media:{id:10,movieFile:file},episodes:[],queue:[],library:[{Id:'abc',Path:'/data'+file.path}],now};
 let p=status.describe(input,true);a.match(p.summaryText,/Available/);a.match(p.summaryText,/Expiry/);a.equal(p.retentionActions.canExtend,true);a.equal(typeof status.describe(input),'string');
 p=status.describe({...input,requests:[{...request,retentionDays:null}]},true);a.equal(p.retentionActions.permanent,true);a.equal(p.retentionActions.canKeep,false);a.equal(p.retentionActions.canExtend,false);
 p=status.describe({...input,records:input.records.map(r=>({...r,payloadJson:JSON.stringify({...JSON.parse(r.payloadJson),identityProtected:true})}))},true);a.equal(p.retentionActions.permanent,false);a.equal(p.retentionActions.canExtend,false);a.equal(p.retentionActions.canKeep,true);
});
test('retention confirmation names the action and date with a safe unavailable-date fallback',()=>{
 const make=c=>({id:12,state:'preview',expiresAt:new Date(Date.now()+300000).toISOString(),contextJson:JSON.stringify({retentionChange:c})});
 const change={operation:'extend',days:7,title:'Example',mediaType:'movie',requestKeys:['r'],expiryFiles:[{checkedAt:new Date().toISOString(),expiresAt:new Date(Date.now()+86400000).toISOString()}]};
 a.match(ret.changeCard(make(change)).choices[0].label,/^Extend to /);
 a.equal(ret.changeCard(make({...change,expiryFiles:[]})).choices[0].label,'Extend 7 days');
 a.equal(ret.changeCard(make({...change,operation:'permanent'})).choices[0].label,'Keep permanently');
});

test('embedded native status nodes preserve summary metadata and safety warning',()=>{
 const rows=JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname,'../config-templates/n8n-current-media-workflows.json'),'utf8'));
 const node=(id,name)=>rows.find(w=>w.id===id).nodes.find(n=>n.name===name).parameters.jsCode;
 const file={id:5,path:'/library/a.mkv',dateAdded:new Date(Date.now()-86400000).toISOString()};
 const state={requests:[request],records:[{key:'file:movie:10:5',payloadJson:JSON.stringify({state:'tracked',path:file.path,importedAt:file.dateAdded,checkedAt:new Date().toISOString(),expiresAt:new Date(Date.now()+86400000).toISOString()})}]};
 const values={'Inspect Status Input':state,'Status Media Snapshot':{media:{id:10,movieFile:file}},'Status Target Snapshot':{jellyfinLibrary:[{Id:'abc',Path:'/data'+file.path}]}};
 const $=name=>({first:()=>({json:values[name]})});
 const full=new Function('$','$input',node('snakeStatusInspectV1','Describe Status'))($,{all:()=>[{json:{records:[],totalRecords:0}}]})[0].json;
 a.match(full.summaryText,/Available/);a.equal(full.retentionActions.canExtend,true);
 const formatter=node('snakeStatusV1','Format Status Result');
 const root=new Function('$','$input',formatter)(name=>name==='Inspect Status Groups'?{all:()=>[{json:full}]}:{first:()=>({json:{warning:'Cleanup paused.\n'}})},{all:()=>[]})[0].json;
 a.match(root.summaryText,/^Cleanup paused/);a.deepEqual(root.retentionActions,full.retentionActions);
 a.equal(nav.card(row(),now,root).text,root.summaryText);
});
