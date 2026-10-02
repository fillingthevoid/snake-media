// Run inside n8n's container: checks the real node loader and keyboard serializer.
const fs=require('fs'),assert=require('assert');
const root='/usr/local/lib/node_modules/n8n/node_modules/.pnpm/';
const pkg=name=>root+fs.readdirSync(root).find(x=>x.startsWith(name+'@'))+'/node_modules/'+name;
const {Workflow}=require(pkg('n8n-workflow'));
const {Telegram}=require(pkg('n8n-nodes-base')+'/dist/nodes/Telegram/Telegram.node.js');
const {addReplyMarkup}=require(pkg('n8n-nodes-base')+'/dist/nodes/Telegram/GenericFunctions.js');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const t=new Telegram();let checked=0;
for(const node of fixture.nodes.filter(n=>n.type==='n8n-nodes-base.telegram'&&n.parameters.replyMarkup==='inlineKeyboard')){
 const original=JSON.parse(JSON.stringify(node.parameters.inlineKeyboard));
 const w=new Workflow({id:'test',nodes:[structuredClone(node)],connections:{},active:false,nodeTypes:{getByNameAndVersion:()=>t}});
 const loaded=w.nodes[node.name].parameters;
 assert.deepStrictEqual(loaded.inlineKeyboard,original,'n8n stripped keyboard from '+node.name);
 assert.ok(Array.isArray(loaded.inlineKeyboard.rows),'native rows required');
 const body={};addReplyMarkup.call({getNodeParameter:k=>loaded[k]},body,0);
 assert.ok(body.reply_markup.inline_keyboard.flat().length>0,'buttons must reach Telegram');checked++;
}
assert.ok(checked>0);console.log('Real n8n loader preserved',checked,'keyboards');
