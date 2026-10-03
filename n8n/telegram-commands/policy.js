function help(){return '/request <movie or series title> — request media. Include the year if needed.\nYou can also send a plain-text request.\n\nTV: choose Latest season, All seasons or a specific season, then Confirm the poster and selection. New episodes in selected seasons and future seasons download automatically.\n\n/status [title] — your downloads, availability and expiry.\nMovies expire 7 days after import; TV episodes expire 30 days after each import. Watching can shorten expiry to 7 days, but never extends it.\nInclude "keep for 14 days" or "keep permanently" in your request to change the default. Download cards have expiry buttons.\n\n/extend <title> 7 days — extend an existing request.\n/keep <title> permanently — keep an existing request.';}
function prepare(u,botUsername){
 const q=u.callback_query,m=q?.message||u.message;if(!m)return [];
 const d=q?.data?.match(/^snake:([1-9][0-9]{0,15}):([a-z_0-9]+)$/);
 const p={text:q?'confirmation':m.text||'',chatId:m.chat.id,userId:(q?.from||m.from).id,messageId:String(m.message_id),requestedAt:new Date(m.date*1000).toISOString(),action:d?.[2],pendingId:d?.[1],callbackId:q?.id};
 if(q)return [{json:p}];
 const c=p.text.trim().match(/^\/([a-z][a-z0-9_]*)(?:@([a-z0-9_]+))?(?:\s+([\s\S]*))?$/i);
 if(!c)return [{json:p}];
 if(c[2]&&c[2].toLowerCase()!==String(botUsername).toLowerCase())return [];
 const name=c[1].toLowerCase(),title=(c[3]||'').trim();
 if(name==='request'){
  if(!title||title.length>1600)p.commandReply='Use /request <movie or series title>, up to 1600 characters. Example: /request The Matrix from 1999';
  else p.text='add '+title;
 }else if(['help','start'].includes(name))p.commandReply=help();
 else if(!['status','extend','keep'].includes(name))p.commandReply='Unknown command. Use /request <title>, /status or /help.';
 return [{json:p}];
}
if(typeof module!=='undefined')module.exports={prepare,help};
