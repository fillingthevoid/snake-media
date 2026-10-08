const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const file=path.join(__dirname,'../n8n/telegram-commands/policy.js');
const snapshot=path.join(__dirname,'../../snake-media-public/config-templates/n8n-current-media-workflows.json');
const legacy=()=>{const rows=JSON.parse(fs.readFileSync(snapshot));const w=rows.find(w=>w.name==='Media Request - Telegram');return new Function('$json',w.nodes.find(n=>n.name==='Prepare Request').parameters.jsCode);};
const prepare=fs.existsSync(file)?require(file).prepare:(u)=>legacy()(u);
const update=text=>({message:{text,message_id:123,date:1700000000,chat:{id:-123},from:{id:111}}});
test('slash request normalizes title and preserves immutable actor and request identity',()=>{const p=prepare(update('/request The Matrix from 1999'),'SnakeBot')[0].json;assert.equal(p.text,'add The Matrix from 1999');assert.equal(p.userId,111);assert.equal(p.chatId,-123);assert.equal(p.messageId,'123');assert.equal(p.requestedAt,'2023-11-14T22:13:20.000Z');});
test('help start and empty request return guidance instead of media requests',()=>{for(const input of ['/help','/start','/request','/request   ']){const p=prepare(update(input),'SnakeBot')[0].json;assert.equal(typeof p.commandReply,'string');assert.match(p.commandReply,/request/);}});
test('own bot suffix works and other bot commands are ignored',()=>{assert.equal(prepare(update('/request@SnakeBot Severance'),'SnakeBot')[0].json.text,'add Severance');assert.deepEqual(prepare(update('/request@AnotherBot Severance'),'SnakeBot'),[]);});
test('plain requests status retention and callbacks retain their prior behavior',()=>{for(const text of ['add Severance','/status Severance','/extend Severance 7 days','/keep Severance permanently'])assert.equal(prepare(update(text),'SnakeBot')[0].json.text,text);const u={callback_query:{id:'callback',data:'snake:123:latest',from:{id:222},message:update('').message}};const p=prepare(u,'SnakeBot')[0].json;assert.equal(p.text,'confirmation');assert.equal(p.userId,222);assert.equal(p.action,'latest');assert.equal(p.pendingId,'123');assert.equal(p.callbackId,'callback');assert.equal(p.commandReply,undefined);});
test('unknown and oversized commands give concise guidance',()=>{for(const text of ['/what','/request '+ 'x'.repeat(1601)])assert.equal(typeof prepare(update(text),'SnakeBot')[0].json.commandReply,'string');});

test('recommend reaches the shared menu rather than unknown-command guidance',()=>{
 const p=prepare(update('/recommend@SnakeBot'),'SnakeBot')[0].json;
 assert.equal(p.commandReply,undefined);assert.equal(p.userId,111);
 assert.match(prepare(update('/help'),'SnakeBot')[0].json.commandReply,/recommend/);
});

test('serverstatus uses its dedicated read-only route and is listed in help',()=>{const p=prepare(update('/serverstatus@SnakeBot'),'SnakeBot')[0].json;assert.equal(p.text,'/serverstatus');assert.equal(p.commandReply,undefined);assert.match(prepare(update('/help'),'SnakeBot')[0].json.commandReply,/serverstatus/);assert.match(prepare(update('/serverstatus Example'),'SnakeBot')[0].json.commandReply,/serverstatus/);});
