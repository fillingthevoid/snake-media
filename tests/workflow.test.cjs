const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const path = require('node:path');
const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/Media Request - Discord.json'), 'utf8'));
const nodes = Object.fromEntries(workflow.nodes.map(n => [n.name, n]));
function execute(name, data, references = {}) {
  const result = vm.runInNewContext(`(function(){${nodes[name].parameters.jsCode}\n})()`, {
    $input: {first: () => ({json: data})},
    $: name => ({first: () => ({json: references[name]})}),
  }, {timeout: 1000});
  return JSON.parse(JSON.stringify(result))[0].json;
}
const access = {allowedUserIds: '100000000000000001', allowedChannelIds: '100000000000000004'};
const body = {source: 'discord', text: 'add Matrix', userId: access.allowedUserIds,
  channelId: access.allowedChannelIds, username: 'person', guildId: '123456789012345678'};
test('valid request preserves large IDs as strings and normalizes text', () => {
  const out = execute('Validate Discord Request', {body: {...body, text: '  add Matrix  '}, ...access});
  assert.equal(out.authorized, true);
  assert.equal(out.text, 'add Matrix');
  assert.equal(out.userId, '100000000000000001');
});
test('invalid users, channels, numeric IDs and missing configuration fail closed', () => {
  for (const change of [{userId:'666'}, {channelId:'666'}, {userId:100000000000000001},
    {text:''}, {text:'x'.repeat(2001)}, {source:'telegram'}, {guildId:null}]) {
    assert.equal(execute('Validate Discord Request', {body:{...body,...change},...access}).authorized, false);
  }
  assert.equal(execute('Validate Discord Request', {body}).authorized, false);
});
test('interpretation allows only recognized types and valid title/year', () => {
  assert.deepEqual(execute('Validate Interpretation', {output:{type:'movie',title:'Matrix',year:1999}}),
    {route:'movie', title:'Matrix', year:1999});
  assert.equal(execute('Validate Interpretation', {output:{type:'tv',title:'Severance'}}).route, 'tv');
  for (const output of [{type:'other',title:'X'}, {type:'movie',title:''},
    {type:'movie',title:'X',year:1999.5}, {type:'movie',title:'X',year:'1999'}]) {
    assert.equal(execute('Validate Interpretation', {output}).route, 'clarification');
  }
  assert.equal(execute('Validate Interpretation', {error:'private error'}).route, 'error');
});
test('normalizes existing Sonarr movie field and explicit added records', () => {
  assert.deepEqual(execute('Normalize TV Result', {status:'already_added',movie:'Severance'}),
    {version:1,status:'already_added',mediaType:'tv',title:'Severance'});
  assert.deepEqual(execute('Normalize Movie Result', {id:12,tmdbId:603,title:'The Matrix'}),
    {version:1,status:'added',mediaType:'movie',title:'The Matrix',searchStarted:true});
});
test('empty results and errors cannot become media success', () => {
  for (const name of ['Normalize Movie Result','Normalize TV Result']) {
    assert.equal(execute(name, {}).status, 'not_found');
    for (const data of [{error:'private stack'}, {id:1}, {status:'unexpected'}, {id:0,title:'X'}]) {
      const result = execute(name, data);
      assert.equal(result.status,'error');
      assert.equal(JSON.stringify(result).includes('private'),false);
    }
  }
});
test('new inactive authenticated workflow references existing children and catches errors', () => {
  assert.equal(workflow.active, false);
  assert.equal(workflow.id, undefined);
  assert.equal(nodes['Discord Webhook'].parameters.authentication, 'headerAuth');
  assert.equal(nodes['Discord Webhook'].parameters.responseMode, 'responseNode');
  assert.equal(nodes['Add Movie - Radarr'].parameters.workflowId.value, 'gAzzbRdwQJNByVkd');
  assert.equal(nodes['Add TV Show - Sonarr'].parameters.workflowId.value, 'xWK1b9ugbjMKhGeC');
  for (const name of ['Add Movie - Radarr','Add TV Show - Sonarr','Interpret Media Request']) {
    assert.equal(nodes[name].alwaysOutputData, true);
    assert.equal(nodes[name].onError, 'continueRegularOutput');
  }
  assert.equal(workflow.nodes.some(n => n.type.includes('telegram')), false);
  for (const branches of Object.values(workflow.connections))
    for (const outputs of Object.values(branches))
      for (const edges of outputs)
        for (const edge of edges) assert.ok(nodes[edge.node], edge.node);
});
