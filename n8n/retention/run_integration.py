"""Run isolated native workflows. All media writes target fake loopback services."""
import concurrent.futures
import json
import subprocess
import time
import urllib.request
from pathlib import Path

root = Path('/mnt/media/appdata/discord-bot')
env = dict(line.split('=', 1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))


def post(path, body):
    req = urllib.request.Request('http://127.0.0.1:5678/webhook/'+path, json.dumps(body).encode(),
        {'Content-Type':'application/json','X-Snake-Media-Key':env['N8N_WEBHOOK_SECRET']})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()
        if not data: raise RuntimeError('Empty response; inspect n8n execution')
        return json.loads(data)


def fake_status():
    script="fetch('http://127.0.0.1:19187/status').then(r=>r.text()).then(t=>process.stdout.write(t))"
    return json.loads(subprocess.check_output(['docker','exec','n8n','node','-e',script]))


assert post('snake-retention-setup-test', {})['ready'] is True
print('Native test tables initialized', flush=True)
preview = post('snake-retention-run-test', {'mode':'preview'})
assert preview['scanned'] == 3, 'Three media groups expected'
assert not any(x['method']!='GET' for x in fake_status()['log']), 'Preview issued a media write'
decisions = [d for g in preview['groups'] for d in g['decisions']]
assert sum(d['due'] for d in decisions) == 2, 'Movie and watched episode should be due'
print('Preview: two due files; permanent movie and unwatched episode protected; no media writes', flush=True)
enabled = post('snake-retention-run-test', {'mode':'enabled'})
state = fake_status()
deleted = [x['path'] for x in state['log'] if x['method']=='DELETE']
assert sorted(deleted) == ['/movie/moviefile/100','/tv/episodefile/200'], deleted
assert set(state['files']) == {'movie:300','tv:201'}
assert next(e for e in state['episodes'] if e['id']==12)['monitored'] is True
assert next(e for e in state['episodes'] if e['id']==13)['monitored'] is False
assert next(e for e in state['episodes'] if e['id']==10)['monitored'] is False
print('Enabled fake cleanup removed only the two due files and monitored the future season', flush=True)
post('snake-retention-run-test', {'mode':'enabled'})
state = fake_status()
assert sum(x['method']=='DELETE' for x in state['log']) == 2
assert next(e for e in state['episodes'] if e['id']==10)['monitored'] is False
print('Repeat scan: no repeated deletion; expired episode remained unmonitored', flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    first = pool.submit(post, 'snake-retention-run-test', {'mode':'probe'})
    time.sleep(0.5)
    second = pool.submit(post, 'snake-retention-run-test', {'mode':'probe'})
    results = [first.result(), second.result()]
assert sum(r.get('probe') is True for r in results)==1
assert sum(r.get('busy') is True for r in results)==1
print('Concurrent lock test: exactly one owner and one busy result', flush=True)
