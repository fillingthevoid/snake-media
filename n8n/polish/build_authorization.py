"""Build append-only authorization from a private current export; no SQLite writes."""
import copy
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent


def parse_id_csv(value, name):
    parts = [part.strip() for part in value.split(',')]
    if any(not re.fullmatch(r'[1-9][0-9]{0,19}', part) or int(part) >= 2**64 for part in parts):
        raise ValueError(name + ' must contain comma-separated Discord IDs')
    return sorted(set(parts), key=int)


def build(source, env, control_id):
    if not isinstance(source, list) or not isinstance(control_id, str) or not control_id:
        raise ValueError('Current export and exact control table ID required')
    matches = [w for w in source if w['id'] == 'HXtTzVTrpNZMZVt3']
    if len(matches) != 1:
        raise ValueError('Missing or duplicate Discord workflow')
    discord = copy.deepcopy(matches[0])
    # Reuse existing native node helpers without executing the status builder.
    definitions = (ROOT.parent / 'status/build.py').read_text(encoding='utf-8-sig').split('status=wf(')[0]
    scope = {'copy': copy, 'uuid': uuid, 'S': {w['id']: w for w in source}}
    exec(compile(definitions[definitions.index('def get('):], 'status/build.py helpers', 'exec'), scope)
    get, code, data, wf, chain = [scope[name] for name in ['get', 'code', 'data', 'wf', 'chain']]
    owners = parse_id_csv(env['ADMIN_DISCORD_USER_IDS'], 'ADMIN_DISCORD_USER_IDS')
    channels = parse_id_csv(env['ALLOWED_DISCORD_CHANNEL_IDS'], 'ALLOWED_DISCORD_CHANNEL_IDS')
    settings = get(discord, 'Discord Access Settings')
    original = next(x['value'] for x in settings['parameters']['assignments']['assignments'] if x['name'] == 'allowedUserIds')
    baseline = parse_id_csv(original, 'allowedUserIds')
    if 'ALLOWED_DISCORD_USER_IDS' in env:
        baseline += parse_id_csv(env['ALLOWED_DISCORD_USER_IDS'], 'ALLOWED_DISCORD_USER_IDS')
    baseline = sorted(set(baseline + owners), key=int)

    def control(name, operation='get'):
        out = data(name, 'snake_media_retention_control')
        p = out['parameters']
        p['dataTableId'] = {'__rl': True, 'mode': 'id', 'value': control_id}
        p['operation'] = operation
        # Read legacy and per-user rows; policy ignores other control rows.
        p['filters']['conditions'] = []
        if operation != 'get':
            p.pop('returnAll', None)
            p['filters']['conditions'] = [{'keyName': 'key', 'condition': 'eq', 'keyValue': '={{ $json.key }}'}]
            values = {'key': '={{ $json.key }}', 'owner': '={{ $json.owner }}'}
            p['columns'] = {'mappingMode': 'defineBelow', 'value': values, 'schema': [
                {'id': k, 'displayName': k, 'type': 'string', 'display': True, 'required': False,
                 'defaultMatch': False, 'canBeUsedToMatch': True} for k in values]}
        return out

    web = copy.deepcopy(get(discord, 'Discord Webhook'))
    web.update(name='Authorization Webhook', webhookId='snake-discord-authorization-v1')
    web['parameters']['path'] = 'snake-discord-authorization'
    response = copy.deepcopy(get(discord, 'Respond to Discord'))
    response['name'] = 'Authorization Response'
    policy = (ROOT / 'authorization.js').read_text(encoding='utf-8-sig')
    verify = control('Verify Saved Discord Users')
    verify['executeOnce'] = True
    backend = wf('snakeDiscordAuthorizationV1', 'Snake Media - Authorize Discord User', [
        web, control('Read Current Discord Users'),
        code('Validate Owner Grant', policy + "\nconst existing=authorizationUsers($input.all().map(x=>x.json)," + json.dumps(baseline) + ");const users=authorizeAdmin($('Authorization Webhook').first().json.body," + json.dumps(owners) + ',' + json.dumps(channels) + ",existing);return users.map(id=>({json:{key:'discord-user:'+id,owner:id,users}}));"),
        control('Save Discord Users', 'upsert'), verify,
        code('Authorization Synchronized', policy + "\nreturn [{json:authorizationAcknowledgment($input.all().map(x=>x.json)," + json.dumps(baseline) + ",$('Validate Owner Grant').first().json.users)}];"), response])
    chain(backend, *[n['name'] for n in backend['nodes']])

    replaced = {'Read Discord Authorization', 'Resolve Discord Authorization'}
    discord['nodes'] = [n for n in discord['nodes'] if n['name'] not in replaced]
    for name in replaced:
        discord['connections'].pop(name, None)
    discord['nodes'] += [control('Read Discord Authorization'), code('Resolve Discord Authorization',
        policy + "\nconst original=$('Discord Access Settings').first().json;const users=authorizationUsers($input.all().map(x=>x.json)," + json.dumps(baseline) + ");return [{json:{...original,allowedUserIds:users.join(',')}}];")]
    chain(discord, 'Discord Access Settings', 'Read Discord Authorization', 'Resolve Discord Authorization', 'Validate Discord Request')
    for workflow in [backend, discord]:
        for key in ['createdAt', 'updatedAt', 'versionId', 'activeVersionId', 'versionCounter', 'shared', 'triggerCount', 'meta', 'isArchived']:
            workflow.pop(key, None)
        workflow.update(active=False, pinData={})
    return backend, discord


def main():
    if len(sys.argv) != 4:
        raise ValueError('Usage: build_authorization.py PRIVATE_EXPORT PRIVATE_ENV EXACT_CONTROL_TABLE_ID')
    env = {}
    for line in Path(sys.argv[2]).read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('\"\'')
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    workflows = build(source, env, sys.argv[3])
    out = ROOT / 'authorization-workflows'
    out.mkdir(exist_ok=True, mode=0o700)
    for workflow in workflows:
        path = out / (workflow['name'] + '.json')
        path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        path.chmod(0o600)
    print('Generated authenticated authorization endpoint and Discord lookup overlay')


if __name__ == '__main__':
    main()
