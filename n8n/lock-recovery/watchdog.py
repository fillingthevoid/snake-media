"""Read-only execution checks. All state changes go through native n8n nodes."""
import argparse
import datetime
import json
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

TERMINAL=('success','error','canceled','crashed')
OWNERS=('snakeRetentionCoordinatorV1','snakeLockRecoveryV1')
COOLDOWN=120

def timestamp(value):
    if not isinstance(value,str):raise ValueError('missing_timestamp')
    dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()

def inspect(connection,now):
    tables=connection.execute('SELECT id FROM data_table WHERE name=?',('snake_media_retention_control',)).fetchall()
    if len(tables)!=1 or not re.fullmatch(r'[A-Za-z0-9_]+',tables[0][0]):
        return {'state':'blocked','reason':'control_table_unknown'}
    rows=connection.execute('SELECT owner FROM "data_table_user_'+tables[0][0]+'" WHERE key=?',('global',)).fetchall()
    if len(rows)!=1:return {'state':'blocked','reason':'lock_not_unique'}
    owner=rows[0][0]
    if owner=='':return {'state':'idle'}
    if not isinstance(owner,str) or not re.fullmatch(r'[1-9][0-9]{0,15}',owner):
        return {'state':'blocked','reason':'owner_unknown'}
    row=connection.execute('SELECT workflowId,status,stoppedAt,deletedAt FROM execution_entity WHERE id=?',(owner,)).fetchone()
    if not row or row[3] is not None or row[0] not in OWNERS:
        return {'state':'blocked','reason':'owner_execution_unknown','owner':owner}
    if row[1] not in TERMINAL:return {'state':'waiting','reason':'owner_not_stopped','owner':owner}
    try:stopped=timestamp(row[2])
    except (TypeError,ValueError):return {'state':'blocked','reason':'stop_time_unknown','owner':owner}
    if now-stopped<COOLDOWN:return {'state':'waiting','reason':'cooldown','owner':owner}
    # Include waiting/queued/unknown executions and soft-deleted running rows.
    active=connection.execute('SELECT count(*) FROM execution_entity WHERE status IS NULL OR status NOT IN (?,?,?,?)',TERMINAL).fetchone()[0]
    if active:return {'state':'waiting','reason':'n8n_work_active','owner':owner}
    iso=lambda t:datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat().replace('+00:00','Z')
    return {'state':'ready','proof':{'owner':owner,'workflowId':row[0],'status':row[1],
            'stoppedAt':iso(stopped),'checkedAt':iso(now),'activeExecutions':0}}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirect_refused')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--database',default='/mnt/media/appdata/n8n/database.sqlite')
    parser.add_argument('--env-file',default='/mnt/media/appdata/discord-bot/.env')
    args=parser.parse_args()
    try:
        with sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True,timeout=5) as c:
            c.execute('BEGIN')
            result=inspect(c,time.time())
            c.rollback()
        if args.check_only:
            print(json.dumps(result));return 0
        if result['state']=='blocked':
            print('Lock recovery requires review: '+result['reason']);return 0
        if result['state']!='ready':return 0
        env=dict(line.split('=',1) for line in Path(args.env_file).read_text().splitlines() if '=' in line and not line.startswith('#'))
        key=env['N8N_WEBHOOK_SECRET'];assert key
        req=urllib.request.Request('http://127.0.0.1:5678/webhook/snake-lock-recovery',
            json.dumps(result['proof']).encode(),{'Content-Type':'application/json','X-Snake-Media-Key':key})
        with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as response:
            if response.status!=200:raise ValueError('recovery_http_error')
            raw=response.read(8193)
            if len(raw)>8192:raise ValueError('recovery_response_too_large')
            reply=json.loads(raw)
        if reply.get('recovered') is True:
            print('Recovered stopped lock owner '+result['proof']['owner']+'; automatic deletion paused for review')
        elif reply.get('reason')!='owner_changed':raise ValueError('recovery_not_confirmed')
        return 0
    except Exception as exc:
        print('Lock recovery deferred error_type='+type(exc).__name__)
        return 1

if __name__=='__main__':raise SystemExit(main())
