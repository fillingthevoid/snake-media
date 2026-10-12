"""Apply reviewed presentation changes without replacing private runtime bindings."""
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ['server-health/policy.js', 'status/policy.js',
            'polish/presentation/policy.js', 'telegram-commands/policy.js']


def replace_policy(code, policy):
    header = policy.splitlines()[0]
    start = code.find(header)
    if start < 0:
        return code
    end = code.find("\nif(typeof module!=='undefined')module.exports=", start)
    if end < 0:
        raise ValueError('Unrecognized policy boundary')
    end = code.find('\n', end+1)
    if end < 0:
        end = len(code)
    old = code[start:end]
    if header.startswith('// Media presentation'):
        local = re.search(r"const LOCAL_JELLYFIN_BASE\s*=\s*[^;]+;", old)
        remote = re.search(r"jellyfinLinks\(item,(['\"])(https?://[^'\"]+)\1,LOCAL_JELLYFIN_BASE\)", old)
        if not local or not remote:
            raise ValueError('Missing private Jellyfin bindings')
        policy = re.sub(r"const LOCAL_JELLYFIN_BASE\s*=\s*[^;]+;", lambda _:local[0], policy)
        policy = re.sub(r"jellyfinLinks\(item,(['\"])(https?://[^'\"]+)\1,LOCAL_JELLYFIN_BASE\)",
                        lambda _:remote[0], policy)
    return code[:start] + policy.rstrip() + code[end:]


def build(source):
    out = copy.deepcopy(source)
    policies = [(ROOT/'n8n'/p).read_text(encoding='utf-8-sig') for p in POLICIES]
    for w in out:
        for n in w['nodes']:
            p = n.get('parameters', {})
            code = p.get('jsCode')
            if not isinstance(code, str):
                continue
            for policy in policies:
                code = replace_policy(code, policy)
            code = code.replace('Extend by 7 days','Extend 7 days').replace('Extend by 30 days','Extend 30 days')
            if w['id'] in ('HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh'):
                if n['name'] == 'Parse Server Health Command':
                    origin = "$json" if w['id']=='0e67KTcphqxEKNsh' else "$('Validate Discord Request').first().json"
                    code = "const p="+origin+";return [{json:{...p,serverHealthCommand:typeof p.text==='string'&&/^\\/?(?:serverstatus|serverdetails)\\s*$/i.test(p.text.trim()),serverHealthDetails:typeof p.text==='string'&&/^\\/?serverdetails\\s*$/i.test(p.text.trim())}}];"
                elif n['name'] == 'Normalize Health Reply':
                    code = "return [{json:{version:1,status:'notice',text:typeof $json.text==='string'?$json.text:'⚠️ Server health is temporarily unavailable.',menuChoices:Array.isArray($json.menuChoices)?$json.menuChoices:[]}}];"
            if w['id']=='snakeServerHealthV1' and n['name']=='Format Health Report':
                code = policies[0].rstrip()+"\nconst actor=$('Health Input').first().json;return [{json:reply($json,actor.serverHealthDetails===true)}];"
            p['jsCode'] = code
    return out


if __name__ == '__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    changed=build(source)
    changed=[w for w,old in zip(changed,source) if w!=old]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:
            w.pop(k,None)
        w.update(active=False,pinData={})
    p=Path(sys.argv[2]);p.write_text(json.dumps(changed,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Built scoped presentation updates:',len(changed))
