'use strict';

// Telegram's native node lacks editMessageReplyMarkup. Reuse its encrypted
// credential; this node changes keyboards only and never changes media policy.
class SnakeTelegramControls {
 constructor(){
  this.description={displayName:'Snake Telegram Controls',name:'snakeTelegramControls',
   group:['transform'],version:1,description:'Remove handled callback controls while retaining URL buttons',
   defaults:{name:'Snake Telegram Controls'},inputs:['main'],outputs:['main'],
   credentials:[{name:'telegramApi',required:true}],properties:[
    {displayName:'Callback Message',name:'message',type:'json',default:'{}',required:true},
   ]};
 }
 async execute(){
  const output=[];
  for(const [index,item] of this.getInputData().entries()){
   const reply=item.json;
   if(reply.busy===true||!(reply.actionAccepted===true||reply.clearControls===true)){
    output.push({...item,pairedItem:{item:index}});continue;
   }
   let cleared=false,phase='invalid_message',errorCode=null;
   try{
    let message=this.getNodeParameter('message',index);
    if(typeof message==='string')message=JSON.parse(message);
    if(!Number.isSafeInteger(message?.message_id)||message.message_id<=0||
       !/^-?[1-9][0-9]{0,19}$/.test(String(message?.chat?.id)))throw Error('invalid_message');
    phase='invalid_keyboard';const rows=message.reply_markup?.inline_keyboard;
    if(!Array.isArray(rows))throw Error('invalid_keyboard');
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
   output.push({...item,json:{...reply,telegramControlsCleared:cleared,...(errorCode?{telegramControlsError:errorCode}:{})},pairedItem:{item:index}});
  }
  return [output];
 }
}
module.exports={SnakeTelegramControls};
