const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/retention-controls/policy.js');
const now=Date.parse('2026-10-01T12:00:00Z');
const request={requestKey:'discord:3:4',source:'discord',userId:'2',state:'registered',mediaType:'movie',mediaId:'8',title:'Example'};
const actor={source:'discord',userId:'2',destinationId:'3',messageId:'5',text:'extend Example 7 days'};
const file={fileId:4,path:'/movies/x.mkv',importedAt:'2026-09-30T12:00:00Z',expiresAt:'2026-10-03T12:00:00Z',state:'tracked',reason:'retained',due:false};
test('retention commands require explicit syntax and bounded whole days',()=>{
 a.deepEqual(p.parseChange('/extend@snake_bot Example 7 days'),{operation:'extend',query:'Example',days:7});
 a.equal(p.parseChange('add Example keep permanently'),null);
 a.equal(p.parseChange('status Example'),null);
 a.equal(p.parseChange('keep Example permanently').operation,'permanent');
 for(const s of ['extend Example -1 days','extend Example 0 days','extend Example 3651 days','extend Example 1.5 days','keep Example'])a.ok(p.parseChange(s).error);
});
test('preview binds only caller requests and refuses ambiguous titles',()=>{
 const out=p.prepareChange(actor,[request,{...request,userId:'9',requestKey:'other'}]);
 a.deepEqual(out.change.requestKeys,[request.requestKey]);
 a.ok(p.prepareChange({...actor,userId:'9'},[request]).notice);
 a.equal(p.prepareChange({...actor,text:'extend Exam 7 days'},[request,{...request,mediaId:'9',title:'Example II'}]).guide.candidates.length,2);
});
test('extension uses later of now and effective expiry and replay returns existing event',()=>{
 const c={source:'discord',userId:'2',operation:'extend',days:7,requestKeys:[request.requestKey],mediaType:'movie',mediaId:'8',title:'Example'};
 const event=p.planChange(c,[request],[file],[],{pendingId:'12',now});
 a.equal(event.files[0].minimumExpiry,'2026-10-10T12:00:00.000Z');
 a.equal(p.planChange(c,[request],[{...file,expiresAt:'2026-09-01'}],[],{pendingId:'13',now}).files[0].minimumExpiry,'2026-10-08T12:00:00.000Z');
 a.deepEqual(p.planChange(c,[request],[file],[{key:'change:12',payloadJson:JSON.stringify(event)}],{pendingId:'12',now:now+86400000}),event);
});
test('protected and missing files cannot be made temporary; permanent covers future request scope',()=>{
 const c={source:'discord',userId:'2',operation:'extend',days:7,requestKeys:[request.requestKey],mediaType:'movie',mediaId:'8',title:'Example'};
 a.ok(p.planChange(c,[request],[{...file,expiresAt:null,reason:'protected claim'}],[],{pendingId:'12',now}).notice);
 a.ok(p.planChange(c,[request],[],[],{pendingId:'12',now}).notice);
 const event=p.planChange({...c,operation:'permanent'},[request],[],[],{pendingId:'12',now});a.equal(event.operation,'permanent');
});


test('control workflow graph routes amendments under lock and cannot invoke a media write',()=>{
 const fs=require('node:fs'),dir=__dirname+'/../n8n/retention-controls/workflows/';
 const ws=fs.readdirSync(dir).map(f=>JSON.parse(fs.readFileSync(dir+f)));
 for(const w of ws){const names=new Set(w.nodes.map(n=>n.name));for(const n of w.nodes)if(n.type.endsWith('.code'))new Function(n.parameters.jsCode);for(const c of Object.values(w.connections))for(const ports of Object.values(c))for(const es of ports)for(const e of es)a.ok(names.has(e.node),e.node);}
 const byId=Object.fromEntries(ws.map(w=>[w.id,w]));
 const snapshot=byId.snakeRetentionChangeSnapshotV1;
 a.match(snapshot.nodes.find(n=>n.name==='Validate Scan Mode').parameters.jsCode,/mode:'preview'/);
 a.match(snapshot.nodes.find(n=>n.name==='Group Retention Requests').parameters.jsCode,/Scan Input.*mediaId/);
 const apply=byId.snakeRetentionChangeApplyV1;
 a.equal(apply.nodes.filter(n=>n.type.endsWith('.httpRequest')).length,0);
 for(const n of apply.nodes.filter(n=>n.type.endsWith('.executeWorkflow')))a.equal(n.onError,undefined);
 const confirm=byId.snakeConfirmMediaV1;
 a.equal(confirm.connections['Retention Choice?'].main[0][0].node,'Prepare Retention Job');
 a.equal(confirm.connections['Retention Choice?'].main[1][0].node,'Commit Confirmed Media');
});

test('change card uses existing confirm/cancel buttons and cancellation cannot imply a download',()=>{
 const row={id:12,state:'preview',expiresAt:'2099-01-01',contextJson:JSON.stringify({retentionChange:{operation:'extend',days:7,title:'Example',mediaType:'tv'}})};
 const out=p.changeCard(row);a.equal(out.status,'confirmation');a.deepEqual(out.choices.map(c=>c.action),['confirm','cancel']);a.match(out.text,/Upcoming episodes keep/);
 a.equal(p.changeCard({...row,state:'cancelled'}).text,'Cancelled. Retention was not changed.');
});
