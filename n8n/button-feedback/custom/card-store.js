'use strict';
const fs=require('node:fs'),path=require('node:path');
function links(rows){
 if(!Array.isArray(rows))return [];
 return rows.map(row=>Array.isArray(row)?row.filter(b=>{
  if(typeof b?.text!=='string'||typeof b.url!=='string'||b.callback_data||b.url.length>2048)return false;
  try{const u=new URL(b.url);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password;}catch{return false;}
 }).map(b=>({text:b.text,url:b.url})):[]).filter(r=>r.length);
}
function groups(message){
 const values=[];
 for(const row of message?.reply_markup?.inline_keyboard||[])for(const b of row||[]){
  const m=typeof b?.callback_data==='string'&&b.callback_data.match(/^snake:([1-9][0-9]{0,15}):([a-z_0-9]+)$/);
  if(m)values.push((m[2].startsWith('notice_')?'notice:':'pending:')+m[1]);
 }
 return [...new Set(values)];
}
class CardStore{
 constructor(file){this.file=file;}
 transaction(change){
  fs.mkdirSync(path.dirname(this.file),{recursive:true,mode:0o700});
  const lock=this.file+'.lock';let fd;
  try{fd=fs.openSync(lock,'wx',0o600);}catch(error){
   if(error.code!=='EEXIST')throw error;
   let stale=false;
   try{const pid=Number(fs.readFileSync(lock,'utf8'));if(Number.isSafeInteger(pid)&&pid>0){try{process.kill(pid,0);}catch(e){stale=e.code==='ESRCH';}}else stale=Date.now()-fs.statSync(lock).mtimeMs>60000;}catch{}
   if(!stale)throw Error('Card state is busy');
   fs.unlinkSync(lock);fd=fs.openSync(lock,'wx',0o600);
  }
  try{
   fs.writeFileSync(fd,String(process.pid));fs.fsyncSync(fd);
   const s=fs.existsSync(this.file)?JSON.parse(fs.readFileSync(this.file,'utf8')):{version:1,cards:[],links:[],jobs:[]};
   if(s.version!==1||!Array.isArray(s.cards)||!Array.isArray(s.links)||!Array.isArray(s.jobs))throw Error('Invalid card state');
   if(s.activeCards===undefined)s.activeCards=[];
   if(!Array.isArray(s.activeCards))throw Error('Invalid active card state');
   const result=change(s),tmp=this.file+'.'+process.pid+'.tmp';
   const out=fs.openSync(tmp,'w',0o600);try{fs.writeFileSync(out,JSON.stringify(s));fs.fsyncSync(out);}finally{fs.closeSync(out);}
   fs.renameSync(tmp,this.file);return result;
  }finally{fs.closeSync(fd);fs.unlinkSync(lock);}
 }
 remember(message,owner,now=Date.now()){
  if(!Number.isSafeInteger(message?.message_id)||message.message_id<=0||!/^[-]?[1-9][0-9]{0,19}$/.test(String(message?.chat?.id))||!/^\d+$/.test(owner))throw Error('Invalid card identity');
  const keys=groups(message);if(!keys.length&&!message?.reply_markup?.inline_keyboard?.flat().some(b=>typeof b.callback_data==='string'&&b.callback_data.startsWith('snake_menu:')))return;
  const chat=String(message.chat.id),id=message.message_id;
  this.transaction(s=>{
   const existing=s.cards.find(c=>c.chat===chat&&c.id===id);
   if(existing&&existing.owner!==owner)throw Error('Card owner conflict');
   if(!existing)s.cards.push({chat,id,owner,groups:keys,links:links(message.reply_markup.inline_keyboard),createdAt:now,expiresAt:now+300000});
   else{existing.groups=[...new Set([...existing.groups,...keys])];existing.links=links(message.reply_markup.inline_keyboard);existing.expiresAt=now+300000;}
   s.jobs=s.jobs.filter(j=>!(j.chat===chat&&j.id===id));
  });
 }
 touch(chat,id,owner,now=Date.now()){
  return this.transaction(s=>{const c=s.cards.find(c=>c.chat===chat&&c.id===id&&c.owner===owner);
   if(!c||(c.expiresAt??c.createdAt+300000)<=now)return false;
   c.expiresAt=now+300000;return true;
  });
 }
 expire(now=Date.now()){
  this.transaction(s=>{s.cards=s.cards.filter(c=>{
   if((c.expiresAt??c.createdAt+300000)>now)return true;
   if(!s.jobs.some(j=>j.chat===c.chat&&j.id===c.id))s.jobs.push({...c,retryAt:0,attempts:0});
   return false;
  });});
 }
 rememberActive(message,owner,original){
  if(!Number.isSafeInteger(message?.message_id)||message.message_id<=0||!/^[-]?[1-9][0-9]{0,19}$/.test(String(message?.chat?.id))||!/^\d+$/.test(owner)||!(/^[1-9][0-9]{0,19}$/).test(original))throw Error('Invalid active card identity');
  const chat=String(message.chat.id);
  this.transaction(s=>{if(!s.activeCards.some(c=>c.chat===chat&&c.original===original&&c.owner===owner))s.activeCards.push({chat,original,owner,id:message.message_id,photo:Array.isArray(message.photo)&&message.photo.length>0,createdAt:Date.now()});});
 }
 active(chat,original,owner){return this.transaction(s=>s.activeCards.find(c=>c.chat===chat&&c.original===original&&c.owner===owner)||null);}
 link(first,second,owner,chat){
  if(![first,second].every(x=>/^(notice|pending):[1-9][0-9]{0,15}$/.test(x)))throw Error('Invalid group');
  this.transaction(s=>{if(!s.links.some(l=>l.first===first&&l.second===second&&l.owner===owner&&l.chat===chat))s.links.push({first,second,owner,chat});});
 }
 consume(group,owner,chat){
  return this.transaction(s=>{
   const selected=new Set([group]);
   for(let i=0;i<=s.links.length;i++)for(const l of s.links)if(l.owner===owner&&l.chat===chat&&(selected.has(l.first)||selected.has(l.second))){selected.add(l.first);selected.add(l.second);}
   let count=0;
   s.cards=s.cards.filter(c=>{
    if(c.owner!==owner||c.chat!==chat||!c.groups.some(g=>selected.has(g)))return true;
    if(!s.jobs.some(j=>j.chat===chat&&j.id===c.id)){s.jobs.push({...c,retryAt:0,attempts:0});count++;}
    return false;
   });return count;
  });
 }
 pending(now){return this.transaction(s=>s.jobs.filter(j=>j.retryAt<=now&&j.attempts<12).slice(0,5).map(j=>({chat:j.chat,id:j.id,message:{message_id:j.id,chat:{id:j.chat},reply_markup:{inline_keyboard:j.links}}})));}
 finish(chat,id){this.transaction(s=>{s.jobs=s.jobs.filter(j=>!(j.chat===chat&&j.id===id));});}
 defer(chat,id,now){this.transaction(s=>{const j=s.jobs.find(j=>j.chat===chat&&j.id===id);if(j){j.attempts++;j.retryAt=now+300;}});}
 compact(now){this.transaction(s=>{
  s.activeCards=s.activeCards.filter(c=>Number.isFinite(c.createdAt)&&c.createdAt>=now-90*86400000);
  s.cards=s.cards.filter(c=>Number.isFinite(c.createdAt)&&c.createdAt>=now-90*86400000);
  const known=new Set(s.cards.flatMap(c=>c.groups));
  s.links=s.links.filter(l=>known.has(l.first)||known.has(l.second));
 });}
}
module.exports={CardStore,links,groups};
