const menus=typeof SNAKE_COMMAND_MENU!=='undefined'?SNAKE_COMMAND_MENU:require('../../src/snake_media/command_menu.json');
function help(){return menus.help.text;}
function prepare(u,botUsername){
 const q=u.callback_query,m=q?.message||u.message;if(!m)return [];
 const d=q?.data?.match(/^snake:([1-9][0-9]{0,15}):([a-z_0-9]+)$/);
 const p={text:q?'confirmation':m.text||'',chatId:m.chat.id,userId:(q?.from||m.from).id,messageId:String(m.message_id),requestedAt:new Date(m.date*1000).toISOString(),action:d?.[2],pendingId:d?.[1],callbackId:q?.id};
 if(q){
  const nav=q.data?.match(/^snake_menu:(help|request|expiry|recommend|status|serverstatus|extend|keep)$/);
  if(nav){const name=nav[1];p.text='/'+name;p.messageId=/^[0-9]+$/.test(String(q.id))?String(q.id):p.messageId;p.requestedAt=new Date().toISOString();if(menus[name]){p.commandReply=menus[name].text;p.menuChoices=menus[name].choices;}}
  return [{json:p}];
 }
 const c=p.text.trim().match(/^\/([a-z][a-z0-9_]*)(?:@([a-z0-9_]+))?(?:\s+([\s\S]*))?$/i);
 if(!c)return [{json:p}];
 if(c[2]&&c[2].toLowerCase()!==String(botUsername).toLowerCase())return [];
 const name=c[1].toLowerCase(),title=(c[3]||'').trim();
 if(name==='request'){
  if(!title||title.length>1600)p.commandReply='Use /request <movie or series title>, up to 1600 characters. Example: /request The Matrix from 1999';
  else p.text='add '+title;
 }else if(name==='serverstatus'){if(title)p.commandReply='Use /serverstatus without a title.';else p.text='/serverstatus';}else if(['help','start'].includes(name)){p.commandReply=help();p.menuChoices=menus.help.choices;}
 else if(!['status','extend','keep','recommend'].includes(name))p.commandReply='Unknown command. Use /request <title>, /status or /help.';
 return [{json:p}];
}
if(typeof module!=='undefined')module.exports={prepare,help};
