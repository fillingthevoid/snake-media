'use strict';
const {CardStore,groups,links}=require('./card-store.js');

// Telegram's native node lacks editMessageReplyMarkup. Reuse its encrypted
// credential; this node changes keyboards only and never changes media policy.
class SnakeTelegramControls {
 constructor(){
  this.description={displayName:'Snake Telegram Controls',name:'snakeTelegramControls',
   group:['transform'],version:1,description:'Remove handled callback controls while retaining URL buttons',
   defaults:{name:'Snake Telegram Controls'},inputs:['main'],outputs:['main'],
   credentials:[{name:'telegramApi',required:true}],properties:[
    {displayName:'Operation',name:'operation',type:'options',default:'clear',options:[{name:'Clear Handled Card',value:'clear'},{name:'Remember Sent Card',value:'remember'},{name:'Retry Related Cards',value:'retry'}]},
    {displayName:'Callback Message',name:'message',type:'json',default:'{}',required:true},
    {displayName:'Owner ID',name:'ownerId',type:'string',default:''},
    {displayName:'Callback Data',name:'callbackData',type:'string',default:''},
    {displayName:'State File',name:'stateFile',type:'string',default:'/home/node/.n8n/snake-controls.json'},
   ]};
 }
 async execute(){
  const output=[];
  for(const [index,item] of this.getInputData().entries()){
   const reply=item.json;
   const supplied=this.getNodeParameter('operation',index,'clear'),operation=typeof supplied==='string'?supplied:'clear';
   const owner=this.getNodeParameter('ownerId',index,''),file=this.getNodeParameter('stateFile',index,'/home/node/.n8n/snake-controls.json');
   const store=(typeof owner==='string'&&/^\d+$/.test(owner)||operation==='retry')&&typeof file==='string'?new CardStore(file):null;
   if(operation==='remember'){
    try{let m=this.getNodeParameter('message',index);if(typeof m==='string')m=JSON.parse(m);if(store)store.remember(m?.result||m,owner);}
    catch{output.push({...item,json:{...reply,telegramCardStored:false},pairedItem:{item:index}});continue;}
    output.push({...item,pairedItem:{item:index}});continue;
   }
   if(operation==='retry'){
    let completed=0;
    try{
     if(store){
      for(const job of store.pending(Date.now()/1000).slice(0,2)){
       try{
        const credentials=await this.getCredentials('telegramApi');
        const base=credentials.baseUrl||'https://api.telegram.org';
        if(base!=='https://api.telegram.org'||!/^\d+:[A-Za-z0-9_-]+$/.test(credentials.accessToken||''))throw Error('credentials');
        let ok=false;
        try{const r=await this.helpers.httpRequest({method:'POST',url:base+'/bot'+credentials.accessToken+'/editMessageReplyMarkup',body:{chat_id:job.chat,message_id:job.id,reply_markup:{inline_keyboard:links(job.message.reply_markup.inline_keyboard)}},json:true,timeout:10000});ok=r?.ok===true;}
        catch(error){const status=Number(error?.statusCode||error?.response?.status||error?.httpCode||error?.status),description=error?.response?.data?.description||error?.response?.body?.description||error?.message||'';ok=status===400&&/message is not modified|message to edit not found/i.test(description);}
        if(ok){store.finish(job.chat,job.id);completed++;}else store.defer(job.chat,job.id,Date.now()/1000);
       }catch{store.defer(job.chat,job.id,Date.now()/1000);}
      }
      store.compact(Date.now());
     }
    }catch{}
    output.push({json:{telegramRelatedCardsCleared:completed},pairedItem:{item:index}});continue;
   }
   if(reply.busy===true||!(reply.actionAccepted===true||reply.clearControls===true)){
    output.push({...item,pairedItem:{item:index}});continue;
   }
   let cleared=false,phase='invalid_message',errorCode=null,message=null;
   try{
    message=this.getNodeParameter('message',index);
    if(typeof message==='string')message=JSON.parse(message);
    if(!Number.isSafeInteger(message?.message_id)||message.message_id<=0||
       !/^-?[1-9][0-9]{0,19}$/.test(String(message?.chat?.id)))throw Error('invalid_message');
    phase='invalid_keyboard';const rows=message.reply_markup?.inline_keyboard;
    if(!Array.isArray(rows))throw Error('invalid_keyboard');
    if(store){
     try{
      store.remember(message,owner);
      const keys=groups(message),data=this.getNodeParameter('callbackData',index,''),m=typeof data==='string'&&data.match(/^snake:([1-9][0-9]{0,15}):([a-z_0-9]+)$/);
      const group=m?(m[2].startsWith('notice_')?'notice:':'pending:')+m[1]:keys[0];
      if(group){if(reply.pendingId&&Array.isArray(reply.choices))store.link(group,'pending:'+reply.pendingId,owner,String(message.chat.id));store.consume(group,owner,String(message.chat.id));}
     }catch{errorCode='card_storage';}
    }
    const links=rows.map(row=>Array.isArray(row)?row.filter(b=>{
     if(!b||typeof b.text!=='string'||typeof b.url!=='string'||b.callback_data||b.url.length>2048)return false;
     try{const u=new URL(b.url);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password;}catch{return false;}
    }).map(b=>({text:b.text,url:b.url})):[]).filter(row=>row.length);
    phase='invalid_credentials';const credentials=await this.getCredentials('telegramApi');
    const base=credentials.baseUrl||'https://api.telegram.org';
    if(base!=='https://api.telegram.org'||typeof credentials.accessToken!=='string'||
       !/^[0-9]+:[A-Za-z0-9_-]+$/.test(credentials.accessToken))throw Error('invalid_credentials');
    phase='telegram_api';const response=await this.helpers.httpRequest({method:'POST',url:base+'/bot'+credentials.accessToken+'/editMessageReplyMarkup',
     body:{chat_id:message.chat.id,message_id:message.message_id,reply_markup:{inline_keyboard:links}},json:true,timeout:10000});
    cleared=response?.ok===true;
   }catch(error){
    const status=Number(error?.statusCode||error?.response?.status||error?.httpCode||error?.status);
    const description=error?.response?.data?.description||error?.response?.body?.description||error?.message||'';
    cleared=phase==='telegram_api'&&status===400&&/message is not modified/i.test(description);
    if(!cleared)errorCode=phase;
    // Do not emit exception messages: Telegram URLs contain the bot token.
    // Cleanup is best effort; the original result must still reach the user.
   }
   if(cleared&&store&&message){try{store.finish(String(message.chat.id),message.message_id);}catch{errorCode='card_storage';}}
   output.push({...item,json:{...reply,telegramControlsCleared:cleared,...(errorCode?{telegramControlsError:errorCode}:{})},pairedItem:{item:index}});
  }
  return [output];
 }
}
module.exports={SnakeTelegramControls};
