"""Rebuild the import artifact from the supplied Telegram export, without secrets."""
import copy
import json
from pathlib import Path
import sys
import uuid

source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
original = {node['name']: node for node in source['nodes']}
nodes = []
connections = {}


def node(name, kind, version, parameters, x, y, **extra):
    result = dict(id=str(uuid.uuid4()), name=name, type=kind,
                  typeVersion=version, position=[x, y], parameters=parameters, **extra)
    nodes.append(result)
    return result


def code(name, script, x, y):
    return node(name, 'n8n-nodes-base.code', 2, {'jsCode': script}, x, y)


def copied(name, x, y):
    source_node = original[name]
    result = node(name, source_node['type'], source_node['typeVersion'],
                  copy.deepcopy(source_node['parameters']), x, y)
    if source_node.get('credentials'):
        result['credentials'] = copy.deepcopy(source_node['credentials'])
    return result


def connect(start, end, output=0, kind='main'):
    outputs = connections.setdefault(start, {}).setdefault(kind, [])
    while len(outputs) <= output:
        outputs.append([])
    outputs[output].append({'node': end, 'type': kind, 'index': 0})


webhook = node('Discord Webhook', 'n8n-nodes-base.webhook', 2,
     {'httpMethod': 'POST', 'path': 'snake-media-discord',
      'authentication': 'headerAuth', 'responseMode': 'responseNode', 'options': {}}, 0, 0,
     webhookId=str(uuid.uuid4()), notesInFlow=True,
     notes='Required: select a Header Auth credential. Name: X-Snake-Media-Key. Value: a private random shared secret. Never disable authentication.')

node('Discord Access Settings', 'n8n-nodes-base.set', 3.4, {
    'assignments': {'assignments': [
        {'id': str(uuid.uuid4()), 'name': 'allowedUserIds', 'type': 'string',
         'value': '100000000000000001'},
        {'id': str(uuid.uuid4()), 'name': 'allowedChannelIds', 'type': 'string',
         'value': '100000000000000004'}]},
    'includeOtherFields': True, 'options': {}}, 240, 0,
    notes='Editable comma-separated IDs. Keep these synchronized with the bot environment allowlists. IDs must stay strings.')

code('Validate Discord Request', r"""
const data = $input.first().json;
const b = data.body;
const denied = [{json: {authorized: false, version: 1, status: 'error'}}];
const validId = x => typeof x === 'string' && /^[1-9][0-9]{0,19}$/.test(x) && BigInt(x) < 2n ** 64n;
const ids = x => typeof x === 'string' ? x.split(',').map(s => s.trim()) : [];
const users = ids(data.allowedUserIds);
const channels = ids(data.allowedChannelIds);
if (!users.length || !channels.length || !users.every(validId) || !channels.every(validId)) return denied;
if (!b || typeof b !== 'object' || Array.isArray(b) || b.source !== 'discord') return denied;
if (![b.userId, b.channelId, b.guildId].every(validId)) return denied;
if (!users.includes(b.userId) || !channels.includes(b.channelId)) return denied;
if (typeof b.text !== 'string' || !b.text.trim() || b.text.trim().length > 2000) return denied;
return [{json: {authorized: true, text: b.text.trim(), userId: b.userId,
  channelId: b.channelId, guildId: b.guildId}}];
""", 480, 0)

node('Authorized Request?', 'n8n-nodes-base.if', 2.3, {
    'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 3},
        'conditions': [{'id': str(uuid.uuid4()), 'leftValue': '={{ $json.authorized }}',
                        'rightValue': '', 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, 720, 0)

interpret = copied('Interpret Media Request', 960, -100)
interpret.update(alwaysOutputData=True, onError='continueRegularOutput')
copied('OpenAI Chat Model', 960, 140)
code('Validate Interpretation', r"""
const data = $input.first().json;
if (Object.prototype.hasOwnProperty.call(data, 'error')) return [{json: {route: 'error'}}];
const out = data.output;
const clarify = [{json: {route: 'clarification'}}];
if (!out || !['movie', 'tv'].includes(out.type) || typeof out.title !== 'string' || !out.title.trim()) return clarify;
if (out.title.length > 300) return clarify;
const result = {route: out.type, title: out.title.trim()};
if (out.year !== undefined && out.year !== null) {
  if (!Number.isInteger(out.year) || out.year < 1800 || out.year > 2200) return clarify;
  result.year = out.year;
}
return [{json: result}];
""", 1220, -100)

rules = []
for route in ['movie', 'tv', 'clarification', 'error']:
    rules.append({'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 3},
        'conditions': [{'id': str(uuid.uuid4()), 'leftValue': '={{ $json.route }}',
                        'rightValue': route, 'operator': {'type': 'string', 'operation': 'equals'}}],
        'combinator': 'and'}, 'renameOutput': True, 'outputKey': route})
node('Route Media Type', 'n8n-nodes-base.switch', 3.4,
     {'rules': {'values': rules}, 'options': {'fallbackOutput': 3}}, 1460, -100)

for name, media, title_field, identifier, y in [
    ('Add Movie - Radarr', 'movie', 'movie', 'tmdbId', -400),
    ('Add TV Show - Sonarr', 'tv', 'show', 'tvdbId', -160),
]:
    child = copied(name, 1700, y)
    child.update(alwaysOutputData=True, onError='continueRegularOutput')
    child['parameters']['options']['waitForSubWorkflow'] = True
    child['parameters']['workflowInputs']['value'] = {
        title_field: '={{ $json.title }}', 'year': '={{ $json.year }}'}
    child['parameters']['workflowInputs']['convertFieldsToString'] = False
    normalizer = 'Normalize Movie Result' if media == 'movie' else 'Normalize TV Result'
    code(normalizer, """
const data = $input.first().json;
const result = {version: 1, status: 'error'};
if (Object.prototype.hasOwnProperty.call(data, 'error')) return [{json: result}];
if (Object.keys(data).length === 0) return [{json: {version: 1, status: 'not_found'}}];
const validTitle = x => typeof x === 'string' && !!x.trim();
if (data.status === 'already_added' && validTitle(data.movie)) {
  return [{json: {version: 1, status: 'already_added', mediaType: MEDIA, title: data.movie.trim()}}];
}
if (Number.isInteger(data.id) && data.id > 0 && Number.isInteger(data.IDENTIFIER)
    && data.IDENTIFIER > 0 && validTitle(data.title) && data.status !== 'already_added') {
  // Existing child workflow adds with searchForMovie/searchForMissingEpisodes=true.
  // Successful creation acknowledges that search request, not download completion.
  return [{json: {version: 1, status: 'added', mediaType: MEDIA,
    title: data.title.trim(), searchStarted: true}}];
}
return [{json: result}];
""".replace('MEDIA', json.dumps(media)).replace('IDENTIFIER', identifier), 1940, y)
    connect(name, normalizer)
    connect(normalizer, 'Respond to Discord')

code('Clarification Result', "return [{json: {version: 1, status: 'clarification'}}];", 1700, 80)
code('Error Result', "return [{json: {version: 1, status: 'error'}}];", 1700, 300)
node('Respond to Discord', 'n8n-nodes-base.respondToWebhook', 1.4,
     {'respondWith': 'json', 'responseBody': '={{ $json }}', 'options': {'responseCode': 200}}, 2200, -100)

node('Import Setup', 'n8n-nodes-base.stickyNote', 1, {'content':
    '## Snake Media — Discord\n1. Select Header Auth on Discord Webhook: X-Snake-Media-Key + private secret.\n'
    '2. Confirm existing OpenAI credential and Radarr/Sonarr workflow selections.\n'
    '3. Access Settings contains your IDs; extend comma-separated lists there and in the bot .env.\n'
    '4. Test before publishing; keep BOT_MODE=test until client deployment.\n'
    'No Telegram workflow is replaced. This workflow can add media when called.\n'
    'Production path: /webhook/snake-media-discord', 'height': 320, 'width': 680}, 0, -460)

for start, end in [('Discord Webhook', 'Discord Access Settings'),
                   ('Discord Access Settings', 'Validate Discord Request'),
                   ('Validate Discord Request', 'Authorized Request?'),
                   ('Authorized Request?', 'Interpret Media Request'),
                   ('Interpret Media Request', 'Validate Interpretation'),
                   ('Validate Interpretation', 'Route Media Type'),
                   ('Clarification Result', 'Respond to Discord'), ('Error Result', 'Respond to Discord')]:
    connect(start, end)
connect('Authorized Request?', 'Error Result', 1)
connect('OpenAI Chat Model', 'Interpret Media Request', kind='ai_languageModel')
for i, destination in enumerate(['Add Movie - Radarr', 'Add TV Show - Sonarr', 'Clarification Result', 'Error Result']):
    connect('Route Media Type', destination, i)

workflow = {'name': 'Media Request - Discord', 'nodes': nodes, 'connections': connections,
            'active': False, 'settings': {'executionOrder': 'v1', 'executionTimeout': 50},
            'pinData': {}, 'tags': []}
destination = Path(__file__).parent / 'Media Request - Discord.json'
destination.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'Created {destination.name}: {len(nodes)} nodes, inactive, no embedded secrets')
