const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
const card=id=>({message_id:id,chat:{id:333},reply_markup:{inline_keyboard:[[{text:'Confirm',callback_data:'snake:13:confirm'}],[{text:'Open',url:'https://jellyfin.example.com'}]]}});
test('Telegram related keyboards survive restart and ownership scopes cleanup',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-cards-'));try{
  let store=new CardStore(path.join(dir,'state.json'));
  store.remember(card(100),'111');store.remember(card(101),'111');
  assert.equal(store.consume('pending:13','222','333'),0);
  assert.equal(store.consume('pending:13','111','444'),0);
  assert.equal(store.consume('pending:13','111','333'),2);
  store=new CardStore(path.join(dir,'state.json'));
  assert.deepEqual(store.pending(0).map(x=>x.message.message_id),[100,101]);
  store.finish('333',100);store.defer('333',101,100);
  assert.equal(store.pending(100).length,0);assert.equal(store.pending(1000).length,1);
  assert.deepEqual(store.pending(1000)[0].message.reply_markup.inline_keyboard,[[{text:'Open',url:'https://jellyfin.example.com'}]]);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('Telegram registry strips message text and refuses conflicting owners',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-cards-'));try{
  const file=path.join(dir,'state.json'),store=new CardStore(file);
  store.remember({...card(100),text:'PRIVATE REQUEST CONTENT'},'111');
  assert.equal(fs.readFileSync(file,'utf8').includes('PRIVATE REQUEST CONTENT'),false);
  assert.throws(()=>store.remember(card(100),'222'));
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
