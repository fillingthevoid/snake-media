const request = $('Normalize Request').first().json;
const rows = $input.all().map(x => x.json).filter(x => x.requestKey);
if (rows.length > 1) throw new Error('Tracking conflict: duplicate request keys require reconciliation');
if (rows.length === 1) {
  const existing = rows[0];
  // state can change later; repeat delivery must not revert it.
  for (const key of Object.keys(request).filter(k => k !== 'state')) {
    if (existing[key] !== request[key]) throw new Error('Tracking conflict: original request cannot be overwritten');
  }
  return [{json: {exists: true, record: existing}}];
}
return [{json: {exists: false, record: request}}];
