"""Read-only execution checks. All state changes go through native n8n nodes."""
import argparse
import datetime
import json
import hashlib
import re
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

TERMINAL=('success','error','canceled','crashed')
OWNERS=('snakeRetentionCoordinatorV1','snakeLockRecoveryV1')
COOLDOWN=120
READ_CHILDREN=('snakeTargetLibraryV1','snakeStatusInspectV1','snakeInspectRequestV1')
# Pin reviewed code with CRLF normalized to LF, matching Git's line-ending policy.
CLEANUP_HASH='fff5b1dc5f12ed1b7f41e5323bac8b7d4c310f8b13078647020014dc9c4a6d67'
CATALOG_PIN_PATH=Path('/mnt/media/appdata/discord-bot/n8n/review-catalog/published-private-pin.json')


def verified_catalog_versions(connection):
    """Only the deployed, reviewed catalog may run independently of media jobs.

    Its HTTP calls are reads and its native writes affect only its own catalog
    lease/queue. Interrupting it is recoverable and cannot mutate media. Bind this
    exception to an exact published definition AND each execution's version.
    """
    try:
        pin=json.loads(CATALOG_PIN_PATH.read_text(encoding='utf-8'))
        if pin.get('workflowId')!='snakeReviewCatalogV1':return ()
        row=connection.execute('SELECT activeVersionId,settings FROM workflow_entity WHERE id=?',('snakeReviewCatalogV1',)).fetchone()
        if not row or row[0]!=pin.get('versionId'):return ()
        versions=pin.get('versions') or [{**pin,'settings':json.loads(row[1] or '{}')}]
        if not isinstance(versions,list) or len(versions)>64:return ()
        verified=[]
        for version in versions:
            ident=version.get('versionId');data=connection.execute('SELECT nodes,connections FROM workflow_history WHERE workflowId=? AND versionId=?',('snakeReviewCatalogV1',ident)).fetchone()
            if not data:continue
            settings=json.loads(row[1] or '{}') if ident==row[0] else version.get('settings')
            if not isinstance(settings,dict) or settings.get('errorWorkflow'):continue
            encoded=json.dumps({'nodes':json.loads(data[0]),'connections':json.loads(data[1]),'settings':settings},sort_keys=True,separators=(',',':'))
            if hashlib.sha256(encoded.encode()).hexdigest()==version.get('sha256'):verified.append(ident)
        return tuple(set(verified)) if row[0] in verified else ()
    except (OSError,ValueError,TypeError,AttributeError,sqlite3.Error):return ()


def verified_catalog_version(connection):
    versions=verified_catalog_versions(connection)
    return versions[0] if versions else None

def timestamp(value):
    if not isinstance(value,str):raise ValueError('missing_timestamp')
    dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()

def blocking_activity(rows,parents,executions,now,cleanup_safe=False):
    """Ignore proven finished read snapshots and verified presentation cleanup."""
    def harmless(row):
        if row.get('status')!='running':return False
        if row.get('workflowId')=='snakeTelegramControlsRetryV1':return cleanup_safe
        if row.get('workflowId') not in READ_CHILDREN:return False
        try:
            # Retained read snapshots may be soft-deleted while still labelled
            # running. Deletion alone proves nothing: require a valid old marker
            # AND the same retained terminal-ancestor proof below.
            if row.get('deletedAt') is not None and now-timestamp(row['deletedAt'])<COOLDOWN:return False
            if now-timestamp(row.get('startedAt'))<COOLDOWN:return False
            current=str(row['id']);seen=set()
            while current in parents:
                if current in seen or not parents[current]:return False
                seen.add(current);current=str(parents[current])
            root=executions.get(current)
            return bool(seen and root and root.get('deletedAt') is None and
                        root.get('status') in TERMINAL and now-timestamp(root.get('stoppedAt'))>=COOLDOWN)
        except (KeyError,ValueError,TypeError,AttributeError):return False
    return sum(not harmless(row) for row in rows)

def activity_count(connection,now):
    """Read a consistent snapshot. Any incomplete evidence keeps work blocking."""
    where="(status IS NULL OR status NOT IN (?,?,?,?))"
    parameters=TERMINAL
    catalog_versions=verified_catalog_versions(connection)
    if catalog_versions:
        where+=' AND NOT (workflowId=? AND COALESCE(workflowVersionId,\'\') IN ('+','.join('?' for _ in catalog_versions)+'))'
        parameters=(*parameters,'snakeReviewCatalogV1',*catalog_versions)
    count=connection.execute('SELECT count(*) FROM execution_entity WHERE '+where,parameters).fetchone()[0]
    if not count:return 0
    try:
        data=connection.execute('SELECT e.id,e.workflowId,e.status,e.startedAt,e.deletedAt,ed.data '
            'FROM execution_entity e LEFT JOIN execution_data ed ON ed.executionId=e.id '
            'WHERE '+where.replace('workflowId','e.workflowId').replace('workflowVersionId','e.workflowVersionId').replace('status','e.status'),parameters).fetchall()
        if len(data)>2000 or len(data)!=count:return count
        rows=[dict(zip(('id','workflowId','status','startedAt','deletedAt'),r[:5])) for r in data]
        raw={str(r[0]):r[5] for r in data if r[1] in READ_CHILDREN and r[5]}
        if sum(len(v) for v in raw.values())>16*1024*1024:return count
        script="const fs=require('fs'),{parse}=require('/usr/local/lib/node_modules/n8n/node_modules/flatted');console.log(JSON.stringify(Object.fromEntries(Object.entries(JSON.parse(fs.readFileSync(0,'utf8'))).map(([id,raw])=>[id,parse(raw).parentExecution?.executionId||null]))));"
        parents=json.loads(subprocess.check_output(['docker','exec','-i','n8n','node','-e',script],
            input=json.dumps(raw),text=True,timeout=10,stderr=subprocess.DEVNULL)) if raw else {}
        executions={}
        for ident in {str(r[0]) for r in data}|{str(v) for v in parents.values() if v}:
            r=connection.execute('SELECT id,status,stoppedAt,deletedAt FROM execution_entity WHERE id=?',(ident,)).fetchone()
            if r:executions[str(r[0])]=dict(zip(('id','status','stoppedAt','deletedAt'),r))
        cleanup=connection.execute("SELECT nodes FROM workflow_entity WHERE id='snakeTelegramControlsRetryV1'").fetchone()
        cleanup_safe=False
        if cleanup:
            nodes=json.loads(cleanup[0])
            shape=[(n['type'],n['parameters'].get('operation')) for n in nodes]
            cleanup_safe=(shape==[('n8n-nodes-base.scheduleTrigger',None),('CUSTOM.snakeTelegramControls','retry')] and
                hashlib.sha256(Path('/mnt/media/appdata/n8n/custom/SnakeTelegramControls.node.js').read_bytes().replace(b'\r\n',b'\n')).hexdigest()==CLEANUP_HASH)
        return blocking_activity(rows,parents,executions,now,cleanup_safe)
    except Exception:return count

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
    active=activity_count(connection,now)
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
