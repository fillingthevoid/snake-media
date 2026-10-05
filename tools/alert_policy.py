"""Persistent health transitions, keyed by issue and immutable recipient ID."""
import hashlib
import math


def observe(state, facts, recipients, now, confirmations=2, reminder_seconds=14400):
    if not math.isfinite(now) or now < 0 or confirmations < 1 or reminder_seconds < 300:
        raise ValueError('invalid_alert_timing')
    events=[]
    wanted={key+':'+recipient for key,ids in recipients.items() for recipient in ids}
    # Removed recipients or probes cannot receive stale pending messages.
    for identity in list(state):
        if identity not in wanted:del state[identity]
    for key,ids in recipients.items():
        value=facts.get(key)
        for recipient in set(ids):
            identity=key+':'+recipient
            row=state.setdefault(identity,{'key':key,'recipient':recipient,'bad':0,'good':0,'active':False,'generation':0,'lastSent':None,'pending':None})
            if value is None:
                row['bad']=row['good']=0
                continue
            if type(value) is not bool:raise ValueError('invalid_alert_fact')
            if value is False:
                row['bad']+=1;row['good']=0
                if row['pending'] and row['pending']['kind']=='recovery':row['pending']=None
                if row['bad']<confirmations:continue
                if not row['pending']:
                    kind='problem' if not row['active'] else 'reminder'
                    if row['active'] and now-row['lastSent']<reminder_seconds:continue
                    row['generation']+=1
                    row['pending']={'id':hashlib.sha256((identity+':'+str(row['generation'])).encode()).hexdigest()[:24],
                        'recipient':recipient,'key':key,'kind':kind}
            else:
                row['good']+=1;row['bad']=0
                if row['pending'] and row['pending']['kind']!='recovery':row['pending']=None
                if row['good']<confirmations or not row['active']:continue
                if not row['pending']:
                    row['generation']+=1
                    row['pending']={'id':hashlib.sha256((identity+':'+str(row['generation'])).encode()).hexdigest()[:24],
                        'recipient':recipient,'key':key,'kind':'recovery'}
            if row['pending']:events.append(dict(row['pending']))
    return events


def delivered(state, event, now):
    row=state.get(event['key']+':'+event['recipient'])
    if not row or row['pending']!=event:raise ValueError('stale_alert_delivery')
    row['active']=event['kind']!='recovery'
    row['lastSent']=now;row['pending']=None
