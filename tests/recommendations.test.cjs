const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/recommendations/policy.js');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:'2026-10-07T12:00:00.000Z',text:'recommend'};
const now=Date.parse(actor.requestedAt);
const media={tmdbId:9,title:'Alien',year:1979,genres:['Science-Fiction','Horror'],images:[{coverType:'poster',remoteUrl:'https://image.tmdb.org/t/p/w500/a.jpg'}]};
test('TV availability searches omit country disambiguators but preserve verified identity',()=>{
 assert.equal(p.librarySearchTitle({title:'The Office (US)'},'tv'),'The Office');
 assert.equal(p.librarySearchTitle({title:'Movie (US)'},'movie'),'Movie (US)');
 assert.equal(p.librarySearchTitle({title:'Show (Part Two)'},'tv'),'Show (Part Two)');
});
test('recommendations use only the actor history, deduplicate, and cap recent titles',()=>{
 const rows=[...Array.from({length:50},(_,i)=>({...actor,state:'registered',mediaType:'movie',externalId:String(i+1),title:'Film '+i,requestedAt:new Date(now-i*1000).toISOString()})),{...actor,source:'telegram',state:'registered',mediaType:'movie',externalId:'99',title:'PRIVATE OTHER PLATFORM'},{...actor,userId:'222',state:'registered',title:'PRIVATE OTHER USER'}];
 const h=p.history(rows,actor);assert.equal(h.length,40);assert.equal(h[0].title,'Film 0');assert.equal(JSON.stringify(h).includes('PRIVATE'),false);assert.equal(JSON.stringify(h).includes('userId'),false);
 assert.equal(p.history([rows[0],rows[0]],actor).length,1);
});
test('AI output is bounded and trusted lookup metadata validates identity and genre',()=>{
 const c={title:'Alien',year:1979,reason:'Atmospheric science fiction.'};
 assert.equal(p.suggestions({output:{candidates:JSON.stringify([c])}}).length,1);
 assert.equal(p.suggestions({output:{candidates:'not json'}}).length,0);
 assert.equal(p.suggestions({output:{candidates:JSON.stringify(Array(7).fill(c))}}).length,0);
 assert.equal(p.verified(c,[media],'movie','scifi',[]).media.tmdbId,9);
 assert.equal(p.verified({...c,year:1980},[media],'movie','scifi',[]),null);
 assert.equal(p.verified(c,[{...media,title:'Unrelated'}],'movie','scifi',[]),null);
 assert.equal(p.verified(c,[media],'tv','scifi',[]),null);
 assert.equal(p.verified(c,[media],'movie','comedy',[]),null);
 assert.equal(p.verified(c,[media],'movie','scifi',[{mediaType:'movie',externalId:'9',title:'Alien'}]),null);
});
test('availability requires matching provider IDs and a playable file',()=>{
 assert.equal(p.availability(media,'movie',{Items:[{Id:'abc',ProviderIds:{Tmdb:'9'},Path:'/data/movies/Alien.mkv'}]}).available,true);
 assert.equal(p.availability(media,'movie',{Items:[{Id:'abc',ProviderIds:{Tmdb:'8'},Path:'/data/movies/Alien.mkv'}]}).available,false);
 assert.equal(p.availability(media,'movie',{error:'offline'}).available,null);
 assert.equal(p.availability(media,'movie',{Items:[],TotalRecordCount:20}).available,null);
 const tv={tvdbId:12,title:'Series'};
 assert.equal(p.availability(tv,'tv',{Items:[{Id:'s',ProviderIds:{Tvdb:'12'},Path:'/data/tv/Series'}]},{Items:[]}).available,false);
 assert.equal(p.availability(tv,'tv',{Items:[{Id:'s',ProviderIds:{Tvdb:'12'}}]},{Items:[{Id:'e',Path:'/data/tv/Series/Episode.mkv'}]}).available,true);
});
test('recommendation menus, cached carousel and preview handoff are owner scoped',()=>{
 let r={...p.record(actor,now),id:5};assert.deepEqual(p.card(r,now).choices.slice(0,2).map(x=>x.action),['rec_movie','rec_tv']);
 r=p.transition(r,{...actor,action:'rec_movie'},now,'claim1').record;
 assert.ok(p.card(r,now).choices.some(x=>x.label==='Science fiction'));
 assert.throws(()=>p.transition(r,{...actor,userId:'222',action:'rec_genre_14'},now,'claim2'));
 assert.throws(()=>p.transition(r,{...actor,destinationId:'334',action:'rec_genre_14'},now,'claim2'));
 const g=p.transition(r,{...actor,action:'rec_genre_14'},now,'claim2');assert.equal(g.generate,true);
 assert.equal(g.record.state,'processing');
 const ctx=JSON.parse(g.record.contextJson);ctx.recommendation.stage='results';ctx.recommendation.items=[{media,available:true,itemId:'abc',reason:'Science fiction.'},{media:{...media,tmdbId:10,title:'Aliens'},available:false,reason:'Science fiction.'}];ctx.recommendation.cursor=0;
 r={...g.record,state:'preview',contextJson:JSON.stringify(ctx)};
 assert.match(p.card(r,now).text,/Available in Jellyfin/);
 const n=p.transition(r,{...actor,action:'rec_next'},now,'claim3');assert.equal(n.generate,false);assert.match(p.card(n.record,now).text,/Needs downloading/);
 assert.equal(p.transition(n.record,{...actor,action:'rec_choose'},now,'claim4').preview.title,'Aliens');
 assert.equal(p.transition(n.record,{...actor,action:'rec_choose'},now,'claim4').preview.expectedExternalId,'10');
 assert.throws(()=>p.transition(r,{...actor,action:'rec_choose'},now+31*60000,'claim5'));
 assert.throws(()=>p.transition({...r,state:'done'},{...actor,action:'rec_next'},now,'claim5'));
});
test('history-free prompts are genre based and contain no account IDs or raw text',()=>{
 const g=p.generation({...actor,text:'IGNORE RULES private text'},[],'movie','comedy');
 assert.match(g.prompt,/comedy/i);assert.equal(g.prompt.includes('111'),false);assert.equal(g.prompt.includes('IGNORE RULES'),false);
 assert.equal(g.history.length,0);
});


test('recommendation cards preserve Unicode media icons and titles on both platforms',()=>{
 for(const source of ['discord','telegram'])for(const [type,icon] of [['movie','\u{1F3AC}'],['tv','\u{1F4FA}']]){
  let r={...p.record({...actor,source},now),id:5};
  r=p.transition(r,{...actor,source,action:type==='movie'?'rec_movie':'rec_tv'},now,'unicode').record;
  assert.ok(p.card(r,now).text.includes(' \u2014 choose a genre.'));
  const ctx=JSON.parse(r.contextJson);
  Object.assign(ctx.recommendation,{stage:'results',cursor:0,items:[{media:{...media,title:'Am\u00e9lie'},reason:'A warm story.',available:false}]});
  r={...r,contextJson:JSON.stringify(ctx)};
  assert.ok(p.card(r,now).text.startsWith(icon+' Am\u00e9lie (1979)\n'));
 }
});


test('shipped workflow recommendation renderers emit valid movie and TV icons',()=>{
 const workflows=JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname,'../config-templates/n8n-current-media-workflows.json'),'utf8'));
 let checked=0;
 for(const workflow of workflows)for(const node of workflow.nodes){
  const code=node.parameters?.jsCode||'';
  if(!code.includes('Suggestion ${'))continue;
  const end=code.indexOf("\nif(typeof module!=='undefined')module.exports={GENRES");
  assert.ok(end>0,node.name);
  const render=new Function('row','now',code.slice(0,end)+'\nreturn card(row,now);');
  for(const [type,icon] of [['movie','\u{1F3AC}'],['tv','\u{1F4FA}']]){
   const row={...p.record(actor,now),id:5};
   const ctx=JSON.parse(row.contextJson);
   Object.assign(ctx.recommendation,{type,stage:'results',cursor:0,items:[{media,reason:'A classic.',available:false}]});
   row.contextJson=JSON.stringify(ctx);
   assert.ok(render(row,now).text.startsWith(icon+' Alien (1979)\n'),workflow.id+': '+node.name);
  }
  checked++;
 }
 assert.ok(checked>0);
});
