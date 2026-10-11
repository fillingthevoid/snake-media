"""Retry transport failures in retention snapshot GETs without replaying writes."""
import copy
import json
from pathlib import Path

READS = {
    ('snakeRetentionScanV1', 'Read Jellyfin Users'),
    ('snakeRetentionScanV1', 'Read Active Playback'),
    ('snakeRetentionMediaV1', 'Read Retention Movie'),
    ('snakeRetentionMediaV1', 'Read Retention Series'),
    ('snakeRetentionMediaV1', 'Read Retention Episodes'),
}


def build(source):
    rows = copy.deepcopy(source)
    found = set()
    for workflow in rows:
        for node in workflow['nodes']:
            identity = (workflow['id'], node['name'])
            if identity not in READS:
                continue
            if node['type'] != 'n8n-nodes-base.httpRequest' or node['parameters'].get('method', 'GET') != 'GET':
                raise ValueError('Unexpected retention read node; no output prepared')
            found.add(identity)
            node.update(retryOnFail=True, maxTries=3, waitBetweenTries=1000)
    if found != READS:
        raise ValueError('Missing retention snapshot read; no output prepared')
    return rows


if __name__ == '__main__':
    import sys
    rows = build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    Path(sys.argv[2]).write_text(json.dumps(rows, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
