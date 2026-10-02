"""Bind initialized native tables by exact ID before importing deployment JSON."""
import copy
import json
import sqlite3
import sys
from pathlib import Path


def bind_tables(workflows, table_rows):
    tables = {}
    for name, table_id in table_rows:
        tables.setdefault(name, []).append(table_id)
    result = copy.deepcopy(workflows)
    for workflow in result:
        for node in workflow['nodes']:
            locator = node.get('parameters', {}).get('dataTableId', {})
            if locator.get('mode') != 'name':
                continue
            matches = tables.get(locator['value'], [])
            if len(matches) != 1:
                raise ValueError('Table must exist with one exact name: ' + locator['value'])
            node['parameters']['dataTableId'] = {'__rl': True, 'mode': 'id', 'value': matches[0]}
    return result


if __name__ == '__main__':
    source, database, destination = map(Path, sys.argv[1:])
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        rows = connection.execute('select name,id from data_table').fetchall()
    output = bind_tables(json.loads(source.read_text()), rows)
    destination.write_text(json.dumps(output))
    destination.chmod(0o600)
    print('Bound exact tables in', len(output), 'workflows')
