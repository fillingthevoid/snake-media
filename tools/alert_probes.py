"""Read-only operational facts. No media decisions, recovery or database writes."""
import datetime
from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess

SERVICES=('Jellyfin','Radarr','Sonarr','Prowlarr','SABnzbd','qBittorrent','n8n')


def health_facts(snapshot, now, minimum_free=50):
    facts={**{'service:'+s:None for s in SERVICES},'storage:mounts':None,'storage:space':None,'playback:sample':None,'monitor:health':False}
    if not isinstance(snapshot,dict) or snapshot.get('version')!=1:return facts
    checked=snapshot.get('checkedAt')
    if type(checked) not in (int,float) or not math.isfinite(checked) or not -5<=now-checked/1000<=120:return facts
    if not all(isinstance(snapshot.get(k,{}),dict) for k in ('services','storage','playback')):return facts
    if not isinstance(snapshot['storage'].get('disks',[]),list):return facts
    facts['monitor:health']=True
    for service in SERVICES:
        value=snapshot.get('services',{}).get(service)
        if type(value) is bool:facts['service:'+service]=value
    storage=snapshot.get('storage',{})
    guard=storage.get('guard')
    if type(guard) is bool:facts['storage:mounts']=guard
    pool=[d for d in storage.get('disks',[]) if isinstance(d,dict) and d.get('label')=='Pool']
    if len(pool)==1:
        free=pool[0].get('freeGiB')
        if type(free) in (int,float) and math.isfinite(free) and free>=0:facts['storage:space']=free>=minimum_free
    sample=snapshot.get('playback',{}).get('sample')
    if sample=='ok':facts['playback:sample']=True
    elif sample=='failed' and facts['service:Jellyfin'] is True:facts['playback:sample']=False
    return facts


def backup_fact(status,now,latest_completed,max_age=36*3600):
    if status.get('ActiveState') in ('activating','active'):return None
    if status.get('Result') and status['Result']!='success':return False
    if status.get('ActiveState')!='inactive' or status.get('Result')!='success':return None
    if latest_completed is None:return False
    if not math.isfinite(latest_completed) or latest_completed>now+5:return None
    return now-latest_completed<=max_age


def backup_probe(directory, now):
    try:
        output=subprocess.check_output(['systemctl','show','snake-stack-backup.service','--property=ActiveState,Result'],timeout=5,text=True,stderr=subprocess.DEVNULL)
        status=dict(line.split('=',1) for line in output.splitlines() if '=' in line)
        completed=[]
        for p in Path(directory).glob('snake-stack-*.tar.gz.age'):
            marker=Path(str(p)+'.sha256')
            if p.is_symlink() or marker.is_symlink() or not marker.is_file() or p.stat().st_size<=0:continue
            value=marker.read_text().strip().split()
            if len(value)==2 and re.fullmatch(r'[a-f0-9]{64}',value[0]) and value[1]==p.name:completed.append(p.stat().st_mtime)
        return backup_fact(status,now,max(completed) if completed else None)
    except Exception:return None


def timestamp(value):
    dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    return (dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)).timestamp()


def n8n_probe(database, now, users, stuck_seconds=900):
    unavailable={'available':False,'lock':None,'requests':{}}
    try:
        with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
            db.execute('BEGIN')
            def table(name):
                matches=db.execute('SELECT id FROM data_table WHERE name=?',(name,)).fetchall()
                if len(matches)!=1 or not re.fullmatch(r'[A-Za-z0-9_]+',matches[0][0]):raise ValueError('unknown_table')
                return '"data_table_user_'+matches[0][0]+'"'
            owners=db.execute('SELECT owner FROM '+table('snake_media_retention_control')+' WHERE key=?',('global',)).fetchall()
            if len(owners)!=1:raise ValueError('unknown_lock')
            owner=owners[0][0];lock=None
            if owner=='':lock=True
            elif not isinstance(owner,str) or not re.fullmatch(r'[1-9][0-9]{0,15}',owner):lock=False
            else:
                execution=db.execute('SELECT startedAt,status,workflowId,deletedAt FROM execution_entity WHERE id=?',(owner,)).fetchone()
                if not execution or execution[3] is not None or execution[2] not in ('snakeRetentionCoordinatorV1','snakeLockRecoveryV1'):lock=False
                else:
                    try:age=now-timestamp(execution[0]);lock=0<=age<stuck_seconds
                    except (ValueError,TypeError,AttributeError):lock=None
            requests={}
            rows=db.execute('SELECT id,source,userId,state,updatedAt,expiresAt,mediaJson FROM '+table('snake_media_pending')+' ORDER BY id DESC LIMIT 2000').fetchall()
            for identifier,source,user,state,updated,expiry,media in rows:
                if source!='discord' or user not in users or user=='1':continue
                healthy=True if state in ('done','cancelled','preview','scope','ready','seasons') else None
                if state=='processing':
                    try:
                        age=now-timestamp(updated);valid_until=timestamp(expiry)
                        # Historical expired confirmations cannot prove a current
                        # failed request. Never notify their owners retroactively.
                        if 0<=age and valid_until>now:healthy=age<stuck_seconds
                    except (ValueError,TypeError,AttributeError):pass
                try:title=str(json.loads(media).get('title','Your request'))
                except (ValueError,AttributeError,TypeError):title='Your request'
                title=' '.join(title.split())[:100]
                requests[str(identifier)]={'userId':user,'title':title,'healthy':healthy}
            db.rollback()
            return {'available':True,'lock':lock,'requests':requests}
    except Exception:return unavailable
