"""Patch only completion nodes in current exports; preserve credentials/settings."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SCRIPTS = {
    'snakeInspectRequestV1': {'Imported Candidates': 'notification-candidates.js'},
    'snakeQueueCandidateV1': {'No Existing Notice': 'notice-dedup.js',
                            'Build Completion Notice': 'confirm-jellyfin.js'},
    'snakeNotificationQueueV1': {'Queue Batch': 'discord-queue-batch.js'},
    'snakeTelegramNoticesV1': {'Unique Telegram Notices': 'telegram-queue-batch.js'},
}


def patch(workflow):
    scripts = SCRIPTS[workflow['id']]
    nodes = {n['name']: n for n in workflow['nodes']}
    for name, filename in scripts.items():
        nodes[name]['parameters']['jsCode'] = (ROOT / 'code' / filename).read_text(encoding='utf-8')
    if workflow['id'] == 'snakeQueueCandidateV1':
        nodes['Find Existing Notice']['parameters']['filters']['conditions'] = [
            {'keyName': 'requestKey', 'condition': 'eq',
             'keyValue': '={{ $json.request.requestKey }}'}]
    return workflow


if __name__ == '__main__':
    if len(sys.argv) == 1:
        for path in (ROOT / 'notification-workflows').glob('*.json'):
            w = json.loads(path.read_text(encoding='utf-8'))
            if w['id'] in SCRIPTS:
                path.write_text(json.dumps(patch(w), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('Updated four local completion workflows')
    else:
        source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        chosen = [patch(w) for w in source if w['id'] in SCRIPTS]
        assert len(chosen) == len(SCRIPTS), 'Missing completion workflow in backup'
        target = Path(sys.argv[2])
        target.write_text(json.dumps(chosen, ensure_ascii=False), encoding='utf-8')
        target.chmod(0o600)
        print('Patched four current completion workflows')
