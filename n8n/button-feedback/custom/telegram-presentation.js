'use strict';
const poster=u=>typeof u==='string'&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(u);
function bounded(text,n){return Array.from(text).slice(0,n).join('').replace(/&[^;\s]*$/,'');}
function keyboard(r){
 const rows=[],terminal=r.retentionUpdated===true||['added','already_added','cancelled'].includes(r.status);
 const choices=terminal?[]:r.choices||[],menus=terminal?[]:r.menuChoices||[];
 if(!Array.isArray(choices)||choices.length>25||!Array.isArray(menus)||menus.length>8)throw Error('Invalid Telegram choices');
 for(const c of choices){
  if(typeof c.label!=='string'||!c.label||c.label.length>100||!/^([a-z_0-9]+)$/.test(c.action)||!(/^[1-9][0-9]{0,15}$/).test(String(r.pendingId)))throw Error('Invalid Telegram choice');
  const data='snake:'+r.pendingId+':'+c.action;if(Buffer.byteLength(data)>64)throw Error('Invalid Telegram choice');
  rows.push([{text:c.label,callback_data:data}]);
 }
 for(const c of menus){
  if(typeof c.label!=='string'||!c.label||c.label.length>100||!['help','more','request','expiry','recommend','status','serverstatus', 'serverdetails','extend','keep'].includes(c.action))throw Error('Invalid Telegram menu');
  rows.push([{text:c.label,callback_data:'snake_menu:'+c.action}]);
 }
 const links=[];
 for(const [label,u] of [[r.jellyfinUrl?'Open locally':'Open in Jellyfin',r.localJellyfinUrl],[r.localJellyfinUrl?'Open via Tailscale':'Open in Jellyfin',r.jellyfinUrl]]){
  if(u===undefined||u===null||u==='')continue;
  try{const url=new URL(u);if(!['http:','https:'].includes(url.protocol)||url.username||url.password||u.length>2048)throw Error();}catch{throw Error('Invalid Telegram link');}
  links.push({text:label,url:u});
 }
 if(links.length)rows.unshift(links);return {inline_keyboard:rows};
}
function errorInfo(e){return {status:Number(e?.statusCode||e?.response?.status||e?.httpCode||e?.status),description:e?.response?.data?.description||e?.response?.body?.description||e?.message||''};}
async function present(ctx,r,store,owner){
 if(!store||!/^\d+$/.test(owner)||!/^[-]?[1-9][0-9]{0,19}$/.test(String(r.chatId))||typeof r.replyText!=='string'||!r.replyText)throw Error('Invalid Telegram presentation');
 const credentials=await ctx.getCredentials('telegramApi');
 if((credentials.baseUrl||'https://api.telegram.org')!=='https://api.telegram.org'||!/^\d+:[A-Za-z0-9_-]+$/.test(credentials.accessToken||''))throw Error('Invalid Telegram credentials');
 const api=async(method,body)=>{const result=await ctx.helpers.httpRequest({method:'POST',url:'https://api.telegram.org/bot'+credentials.accessToken+'/'+method,body,json:true,timeout:10000});if(result?.ok!==true)throw Error('Unconfirmed Telegram response');return result;};
 const m=r.callbackMessage,callback=!!m,validTarget=Number.isSafeInteger(m?.message_id)&&m.message_id>0&&String(m?.chat?.id)===String(r.chatId)&&m?.from?.is_bot===true;
 const owned=validTarget&&store.ownedCard(String(r.chatId),m.message_id,owner);
 const menu=typeof r.callbackData==='string'&&r.callbackData.startsWith('snake_menu:');
 const accepted=r.busy!==true&&(r.actionAccepted===true||r.clearControls===true||(menu&&owned&&owned.expiresAt>Date.now()));
 if(callback&&(!validTarget||!owned||!accepted)){
  if(typeof r.callbackId==='string'&&/^[0-9]{1,30}$/.test(r.callbackId)){
   try{await api('answerCallbackQuery',{callback_query_id:r.callbackId,text:bounded(r.replyText.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>'),180),show_alert:true});}catch{}
  }
  return {telegramCardUnchanged:true};
 }
 const markup=keyboard(r),photo=poster(r.posterUrl),existingPhoto=Array.isArray(m?.photo)&&m.photo.length>0;
 let body={chat_id:r.chatId,reply_markup:markup,parse_mode:'HTML'},method;
 if(callback){
  body.message_id=m.message_id;
  if(photo){method='editMessageMedia';delete body.parse_mode;body.media={type:'photo',media:r.posterUrl,caption:bounded(r.replyText,1000),parse_mode:'HTML'};}
  else if(existingPhoto){method='editMessageCaption';body.caption=bounded(r.replyText,1000);}
  else{method='editMessageText';body.text=bounded(r.replyText,4000);body.link_preview_options={is_disabled:true};}
 }else if(photo){method='sendPhoto';body.photo=r.posterUrl;body.caption=bounded(r.replyText,1000);}
 else{method='sendMessage';body.text=bounded(r.replyText,4000);body.link_preview_options={is_disabled:true};}
 let response;
 try{response=await api(method,body);}catch(e){
  const info=errorInfo(e);
  if(callback&&info.status===400&&/message is not modified/i.test(info.description))response={ok:true,result:{...m,reply_markup:markup,...(existingPhoto||photo?{caption:bounded(r.replyText,1000)}:{text:bounded(r.replyText,4000)}),...(photo?{photo:[{file_id:'edited'}]}:{})}};
  else if(callback&&photo&&info.status===400&&/failed to get HTTP URL content|wrong type of the web page content|IMAGE_PROCESS_FAILED/i.test(info.description)){
   const fallback={chat_id:r.chatId,message_id:m.message_id,reply_markup:markup,parse_mode:'HTML'};
   if(existingPhoto)fallback.caption=bounded(r.replyText,1000);
   else{fallback.text=bounded(r.replyText,4000);fallback.link_preview_options={is_disabled:true};}
   try{response=await api(existingPhoto?'editMessageCaption':'editMessageText',fallback);}catch(error){
    const next=errorInfo(error);
    if(next.status===400&&/message is not modified/i.test(next.description))response={ok:true,result:{...m,reply_markup:markup,...(existingPhoto?{caption:fallback.caption}:{text:fallback.text})}};
    else throw Error('Telegram card update failed');
   }
  }
  else if(callback&&info.status===400&&/message to edit not found|message can't be edited|message cannot be edited/i.test(info.description)){
   const replacement={chat_id:r.chatId,reply_markup:markup,parse_mode:'HTML',text:bounded(r.replyText,4000),link_preview_options:{is_disabled:true}};
   if(photo){delete replacement.text;delete replacement.link_preview_options;replacement.photo=r.posterUrl;replacement.caption=bounded(r.replyText,1000);}
   try{response=await api(photo?'sendPhoto':'sendMessage',replacement);}catch{throw Error('Telegram card delivery failed');}
  }else if(!callback&&photo){
   try{response=await api('sendMessage',{chat_id:r.chatId,reply_markup:markup,parse_mode:'HTML',text:bounded(r.replyText,4000),link_preview_options:{is_disabled:true}});}catch{throw Error('Telegram card delivery failed');}
  }else throw Error(callback?'Telegram card update failed':'Telegram card delivery failed');
 }
 if(!Number.isSafeInteger(response.result?.message_id)||String(response.result?.chat?.id)!==String(r.chatId))throw Error('Invalid Telegram delivery identity');
 const message={...response.result,reply_markup:markup};
 store.replace(message,owner);
 if(r.requestMessageId)store.rememberActive(message,owner,String(r.requestMessageId));
 return response;
}
module.exports={present,keyboard};
