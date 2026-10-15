"""Verify a reviewed private catalog definition before classifying its jobs."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

WORKFLOW_ID='snakeReviewCatalogV1'


def verify_and_pin(connection,expected,output):
    matches=[w for w in expected if w['id']==WORKFLOW_ID]
    if len(matches)!=1:raise ValueError('Expected one reviewed catalog workflow')
    w=matches[0]
    if w.get('settings',{}).get('errorWorkflow'):raise ValueError('Catalog must not invoke another error workflow')
    pending=next(n['parameters']['dataTableId']['value'] for n in w['nodes'] if n['name']=='Read Catalog Rows')
    writes={'Initialize Catalog','Claim Catalog Lease','Save Catalog'}
    for node in w['nodes']:
        kind=node['type'].rsplit('.',1)[-1];p=node['parameters']
        if kind not in {'webhook','code','if','dataTable','httpRequest','respondToWebhook'}:raise ValueError('Unexpected catalog node type')
        if kind=='httpRequest' and p.get('method')!='GET':raise ValueError('Catalog contains an external write')
        if kind=='dataTable' and p.get('operation')!='get' and (node['name'] not in writes or p['dataTableId']['value']!=pending):raise ValueError('Catalog contains an unrelated native write')
    entity=connection.execute('SELECT activeVersionId,settings FROM workflow_entity WHERE id=?',(WORKFLOW_ID,)).fetchone()
    if not entity or not entity[0]:raise ValueError('Catalog is not published')
    version=connection.execute('SELECT nodes,connections FROM workflow_history WHERE workflowId=? AND versionId=?',(WORKFLOW_ID,entity[0])).fetchone()
    if not version:raise ValueError('Published catalog snapshot is missing')
    actual={'nodes':json.loads(version[0]),'connections':json.loads(version[1]),'settings':json.loads(entity[1] or '{}')}
    wanted={k:w.get(k,{}) for k in actual}
    if actual!=wanted:raise ValueError('Published catalog differs from the reviewed private export')
    encoded=json.dumps(actual,sort_keys=True,separators=(',',':'))
    current={'versionId':entity[0],'settings':actual['settings'],'sha256':hashlib.sha256(encoded.encode()).hexdigest()}
    versions=[]
    if output.exists():
        previous=json.loads(output.read_text(encoding='utf-8'))
        if previous.get('workflowId')!=WORKFLOW_ID:raise ValueError('Unexpected existing publication pin')
        history=previous.get('versions') or [{**previous,'settings':actual['settings']}]
        for record in history:
            if record.get('versionId')==entity[0]:continue
            snapshot=connection.execute('SELECT nodes,connections FROM workflow_history WHERE workflowId=? AND versionId=?',(WORKFLOW_ID,record.get('versionId'))).fetchone()
            if not snapshot:continue
            value={'nodes':json.loads(snapshot[0]),'connections':json.loads(snapshot[1]),'settings':record.get('settings')}
            old_encoded=json.dumps(value,sort_keys=True,separators=(',',':'))
            if hashlib.sha256(old_encoded.encode()).hexdigest()==record.get('sha256'):versions.append(record)
    versions.append(current)
    if len(versions)>64:raise ValueError('Too many retained catalog versions; review old execution metadata')
    pin={'workflowId':WORKFLOW_ID,**current,'versions':versions}
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp');temporary.write_text(json.dumps(pin),encoding='utf-8');temporary.chmod(0o600);temporary.replace(output)
    return pin


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected',type=Path,help='Reviewed installation-specific private workflow export')
    parser.add_argument('--output',type=Path,default=Path('/mnt/media/appdata/discord-bot/n8n/review-catalog/published-private-pin.json'))
    args=parser.parse_args()
    expected=json.loads(args.expected.read_text(encoding='utf-8'))
    with sqlite3.connect('file:/mnt/media/appdata/n8n/database.sqlite?mode=ro',uri=True) as connection:
        verify_and_pin(connection,expected,args.output)
    print('Reviewed catalog publication verified and pinned; SQLite was read-only')


if __name__=='__main__':main()
