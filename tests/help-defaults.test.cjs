const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const p=require('../n8n/recommendations/policy.js'),menus=require('../src/snake_media/command_menu.json'),prepare=require('../n8n/telegram-commands/policy.js').prepare;
const a={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:'2026-10-12T12:00:00Z'},now=Date.parse(a.requestedAt);
const pref=(extra={})=>({id:10,source:'discord',userId:'111',state:'recommendation-settings',requestKey:'recommend-settings:discord:111',contextJson:JSON.stringify({recommendationPreference:{type:'tv',genre:'comedy'}}),...extra});
test('Help exposes main tasks and More retains expiry navigation',()=>{
 assert.deepEqual(menus.help.choices.map(c=>c.action),['request','recommend','status','serverstatus','more']);
 assert.ok(menus.more.choices.some(c=>c.action==='expiry'));assert.ok(menus.more.choices.some(c=>c.action==='help'));assert.ok(menus.more.choices.some(c=>c.action==='extend'));
 const r=prepare({callback_query:{id:'777',data:'snake_menu:more',from:{id:111},message:{message_id:8,date:1700000000,chat:{id:333}}}},'SnakeBot')[0].json;
 assert.equal(r.commandReply,menus.more.text);assert.deepEqual(r.menuChoices,menus.more.choices);assert.equal(r.action,undefined);
});
test('saved defaults are scoped, validated and do not generate merely on opening',()=>{
 let row={...p.record(a,now,[pref()]),id:12};let card=p.card(row,now);
 assert.match(card.text,/TV shows.*Comedy/);assert.deepEqual(card.choices.map(c=>c.action),['rec_more','rec_change','rec_cancel']);assert.equal(row.state,'preview');
 const use=p.transition(row,{...a,action:'rec_more'},now,'claim');assert.equal(use.generate,true);assert.equal(JSON.parse(use.record.contextJson).recommendation.genre,'comedy');
 const change=p.transition(row,{...a,action:'rec_change'},now,'claim');assert.equal(change.generate,false);assert.equal(JSON.parse(change.record.contextJson).recommendation.stage,'type');
 assert.throws(()=>p.transition(row,{...a,userId:'222',action:'rec_more'},now,'claim'));
 assert.throws(()=>p.transition(row,{...a,action:'rec_more'},now+300001,'claim'));
 for(const bad of [pref({source:'telegram'}),pref({userId:'222'}),pref({state:'settings'}),pref({requestKey:'watch:discord:111'}),pref({contextJson:'broken'}),pref({contextJson:JSON.stringify({recommendationPreference:{type:'movie',genre:'invented'}})})]){
  assert.equal(JSON.parse(p.record(a,now,[bad]).contextJson).recommendation.stage,'type');
 }
 const newer=pref({id:11,contextJson:JSON.stringify({recommendationPreference:{type:'movie',genre:'action'}})});
 assert.match(p.card({...p.record(a,now,[pref(),newer]),id:12},now).text,/Movies.*Action/);
 assert.equal(JSON.parse(p.record({...a,source:'telegram'},now,[pref()]).contextJson).recommendation.stage,'type');
});
test('preference storage has a dedicated settings state and excludes request data',()=>{
 const policy=fs.readFileSync('n8n/recommendations/policy.js','utf8');const remember=new Function(policy+'\nreturn preferenceRecord;')();
 let row={...p.record(a,now),id:12};row=p.transition(row,{...a,action:'rec_tv'},now,'1').record;
 row=p.transition(row,{...a,action:'rec_genre_4'},now,'2').record;
 const s=remember(row);assert.equal(s.state,'recommendation-settings');assert.equal(s.requestKey,'recommend-settings:discord:111');
 assert.deepEqual(JSON.parse(s.contextJson),{recommendationPreference:{type:'tv',genre:'comedy'}});
 assert.equal(s.mediaJson,'{}');assert.equal(s.claimId,'');assert.ok(!s.contextJson.includes('333'));
 assert.throws(()=>remember({...row,state:'preview'}));
});

test('Telegram presentation accepts More but rejects administrative menu actions',()=>{
 const keyboard=require('../n8n/button-feedback/custom/telegram-presentation.js').keyboard;
 const k=keyboard({menuChoices:menus.help.choices});assert.ok(k.inline_keyboard.flat().some(b=>b.callback_data==='snake_menu:more'));
 assert.throws(()=>keyboard({menuChoices:[{label:'Admin',action:'authorize'}]}));
});

test('recommendation defaults do not replace Watch link preferences',()=>{
 const apply=require('../n8n/watch-preferences/policy.js').apply;
 const result={jellyfinUrl:'https://remote.example/web',localJellyfinUrl:'http://192.168.0.200/web'};
 const settings=[pref({id:999}),{id:1,source:'discord',userId:'111',state:'settings',contextJson:JSON.stringify({watchPreference:'local'})}];
 assert.equal(apply(result,settings,a).jellyfinUrl,result.localJellyfinUrl);
});
