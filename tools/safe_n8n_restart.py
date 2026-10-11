"""Refuse a restart during mutations or near the fifteen-minute scan boundary."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import re
import subprocess
import time


def restart_ready(owner,activity,now):
    # The retention schedule fires at second 5 of each fifteen-minute boundary.
    until_scan=(5-now%900)%900
    return owner=='' and activity==0 and until_scan>120


def main():
    root=Path('/mnt/media/appdata/discord-bot')
    spec=importlib.util.spec_from_file_location('watchdog',root/'n8n/lock-recovery/watchdog.py')
    watchdog=importlib.util.module_from_spec(spec);spec.loader.exec_module(watchdog)
    now=time.time()
    with sqlite3.connect('file:/mnt/media/appdata/n8n/database.sqlite?mode=ro',uri=True,timeout=5) as c:
        c.execute('BEGIN')
        tables=c.execute('SELECT id FROM data_table WHERE name=?',('snake_media_retention_control',)).fetchall()
        if len(tables)!=1 or not re.fullmatch(r'[A-Za-z0-9_]+',tables[0][0]):raise ValueError('Control table is not unique')
        rows=c.execute('SELECT owner FROM "data_table_user_'+tables[0][0]+'" WHERE key=?',('global',)).fetchall()
        if len(rows)!=1:raise ValueError('Global lock is not unique')
        active=watchdog.activity_count(c,now)
        owner=rows[0][0]
        c.rollback()
    if not restart_ready(owner,active,time.time()):
        print(json.dumps({'restart':False,'lockHeld':bool(owner),'blockingExecutions':active,'nearScanBoundary':not restart_ready('',0,time.time())}))
        return 2
    # Keep the check and restart in one process. Do not reuse earlier idle evidence.
    subprocess.run(['docker','restart','--time','120','n8n'],check=True)
    print('n8n restarted after fresh idle and schedule checks')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
