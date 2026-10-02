"""Generate native n8n setup, registration and synthetic verification workflows."""
import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

ROOT = Path(__file__).parent
SETUP_ID = 'snakeTrackingSetupV1'
REGISTER_ID = 'snakeTrackRequestV1'
VERIFY_ID = 'snakeTrackingVerifyV1'
SCHEMAS = {
    'snake_media_requests': {
        **dict.fromkeys(['requestKey', 'source', 'userId', 'destinationId', 'messageId',
                         'text', 'mediaType', 'mediaId', 'externalId', 'title',
                         'episodeIdsJson', 'preexistingFileIdsJson', 'state'], 'string'),
        'requestedAt': 'date', 'retentionDays': 'number', 'baselineCaptured': 'boolean',
        'deletionEligible': 'boolean',
    },
    'snake_media_request_files': {
        **dict.fromkeys(['requestKey', 'fileKey', 'mediaType', 'mediaId', 'fileId',
                         'episodeIdsJson', 'state'], 'string'),
        'importedAt': 'date', 'expiresAt': 'date', 'protected': 'boolean',
    },
    'snake_media_import_events': {
        **dict.fromkeys(['eventKey', 'mediaType', 'mediaId', 'fileId', 'episodeIdsJson',
                         'state', 'payloadJson'], 'string'),
        'importedAt': 'date', 'receivedAt': 'date',
    },
    'snake_media_notifications': {
        **dict.fromkeys(['notificationKey', 'requestKey', 'fileKey', 'source',
                         'destinationId', 'payloadJson', 'state', 'deliveredMessageId'], 'string'),
        'attempts': 'number', 'nextAttemptAt': 'date', 'deliveredAt': 'date',
    },
}


def node(name, kind, version, params, x, y=0, **extra):
    return dict(id=str(uuid5(NAMESPACE_URL, 'snake-tracking/' + name)), name=name,
                type='n8n-nodes-base.' + kind, typeVersion=version,
                parameters=params, position=[x, y], **extra)


def workflow(id_, name, nodes, edges):
    connections = {}
    for source, target, port in edges:
        outputs = connections.setdefault(source, {}).setdefault('main', [])
        while len(outputs) <= port:
            outputs.append([])
        outputs[port].append({'node': target, 'type': 'main', 'index': 0})
    return dict(id=id_, name=name, nodes=nodes, connections=connections, active=False,
                settings={'executionOrder': 'v1'}, pinData={}, tags=[])


setup = [node('Run Setup', 'manualTrigger', 1, {}, 0)]
edges = []
for i, (table, schema) in enumerate(SCHEMAS.items()):
    name = 'Create ' + table
    setup.append(node(name, 'dataTable', 1.1, {
        'resource': 'table', 'operation': 'create', 'tableName': table,
        'columns': {'column': [{'name': k, 'type': v} for k, v in schema.items()]},
        'options': {'createIfNotExists': True},
    }, 250 * (i + 1)))
    edges.append((setup[-2]['name'], name, 0))

table_locator = {'__rl': True, 'mode': 'name', 'value': 'snake_media_requests'}
columns = SCHEMAS['snake_media_requests']
register = [
    node('Request Input', 'executeWorkflowTrigger', 1.1, {'inputSource': 'passthrough'}, 0),
    node('Normalize Request', 'code', 2, {'jsCode': (ROOT/'code/normalize-request.js').read_text()}, 240),
    node('Find Existing Request', 'dataTable', 1.1, {
        'resource': 'row', 'operation': 'get', 'dataTableId': table_locator,
        'matchType': 'allConditions', 'filters': {'conditions': [
            {'keyName': 'requestKey', 'condition': 'eq', 'keyValue': '={{ $json.requestKey }}'}]},
        'returnAll': True,
    }, 480, alwaysOutputData=True),
    node('Resolve Existing', 'code', 2, {'jsCode': (ROOT/'code/resolve-existing.js').read_text()}, 720),
    node('Already Registered?', 'if', 2.3, {
        'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 3},
            'conditions': [{'id': 'exists', 'leftValue': '={{ $json.exists }}', 'rightValue': '',
                            'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
            'combinator': 'and'}, 'options': {}}, 960),
    node('Keep Existing', 'code', 2, {'jsCode': 'return [{json: $input.first().json.record}];'}, 1200, -140),
    node('Insert Request', 'dataTable', 1.1, {
        'resource': 'row', 'operation': 'insert', 'dataTableId': table_locator,
        'columns': {'mappingMode': 'defineBelow',
            'value': {key: '={{ $json.record.' + key + ' }}' for key in columns},
            'schema': [{'id': key, 'displayName': key, 'type': typ, 'display': True,
                        'required': False, 'defaultMatch': False, 'canBeUsedToMatch': True}
                       for key, typ in columns.items()]}, 'options': {}}, 1200, 140),
    node('Return Tracking Record', 'code', 2, {'jsCode':
        "const r=$input.first().json; return [{json:{trackingVersion:1,requestKey:r.requestKey,state:r.state,retentionDays:r.retentionDays,deletionEligible:r.deletionEligible}}];"}, 1440),
]
register_edges = [(a,b,0) for a,b in zip([n['name'] for n in register[:4]], [n['name'] for n in register[1:5]])]
register_edges += [('Already Registered?', 'Keep Existing', 0), ('Already Registered?', 'Insert Request', 1),
                   ('Keep Existing', 'Return Tracking Record', 0), ('Insert Request', 'Return Tracking Record', 0)]

fixture = {'source': 'discord', 'userId': '1', 'destinationId': '1', 'messageId': '1',
           'requestedAt': '2026-09-29T00:00:00.000Z', 'text': 'synthetic storage test only',
           'mediaType': 'movie', 'mediaId': '1', 'externalId': '1', 'title': 'SYNTHETIC TEST - NOT MEDIA',
           'episodeIds': [], 'preexistingFileIds': [], 'baselineCaptured': False}
verify = [node('Run Storage Test', 'manualTrigger', 1, {}, 0),
          node('Synthetic Input', 'code', 2, {'jsCode': 'return [{json:' + json.dumps(fixture) + '}];'}, 240)]
for i in (1,2):
    verify.append(node('Register Test ' + str(i), 'executeWorkflow', 1.3, {
        'workflowId': {'__rl': True, 'mode': 'id', 'value': REGISTER_ID},
        'options': {'waitForSubWorkflow': True},
        'workflowInputs': {'mappingMode': 'passThrough'},
    }, 240 + i * 360))
    if i == 1:
        verify.append(node('Repeat Original Input', 'code', 2, {
            'jsCode': "return [{json:$('Synthetic Input').first().json}];"}, 840))
verify.append(node('Check Stored Rows', 'dataTable', 1.1, {
    'resource': 'row', 'operation': 'get', 'dataTableId': table_locator,
    'matchType': 'allConditions', 'filters': {'conditions': [
        {'keyName': 'requestKey', 'condition': 'eq', 'keyValue': 'discord:1:1'}]},
    'returnAll': True}, 1440, alwaysOutputData=True))
verify.append(node('Verify Exactly One Row', 'code', 2, {'jsCode':
    "const rows=$input.all(); if(rows.length!==1 || rows[0].json.requestKey!=='discord:1:1' || rows[0].json.retentionDays!==null || rows[0].json.deletionEligible!==false) throw new Error('Storage verification failed'); return rows;"}, 1680))
verify.append(node('Remove Synthetic Row', 'dataTable', 1.1, {
    'resource': 'row', 'operation': 'deleteRows', 'dataTableId': table_locator,
    'matchType': 'allConditions', 'filters': {'conditions': [
        {'keyName': 'requestKey', 'condition': 'eq', 'keyValue': 'discord:1:1'},
        {'keyName': 'title', 'condition': 'eq', 'keyValue': 'SYNTHETIC TEST - NOT MEDIA'}]},
    'options': {}}, 1920, alwaysOutputData=True))
verify.append(node('Storage Test Passed', 'code', 2, {'jsCode':
    "return [{json:{test:'shared-request-registration',passed:true,duplicateRetry:'one row',cleanup:'synthetic row removed'}}];"}, 2160))
verify_edges = [(a['name'],b['name'],0) for a,b in zip(verify,verify[1:])]

artifacts = [workflow(SETUP_ID,'Snake Media - Setup Tracking Tables',setup,edges),
             workflow(REGISTER_ID,'Snake Media - Register Request',register,register_edges),
             workflow(VERIFY_ID,'Snake Media - Verify Tracking Storage',verify,verify_edges)]
out = ROOT/'workflows'
out.mkdir(exist_ok=True)
for item in artifacts:
    (out/(item['name']+'.json')).write_text(json.dumps(item,indent=2)+'\n',encoding='utf-8')
(ROOT/'schema.json').write_text(json.dumps(SCHEMAS,indent=2)+'\n',encoding='utf-8')
print('Generated setup, registration, verification workflows and schema')
