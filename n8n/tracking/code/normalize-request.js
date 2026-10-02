// Called only by trusted request workflows after their own authentication.
const r = $input.first().json;
function requireThat(ok, reason) { if (!ok) throw new Error('Tracking input: ' + reason); }
const positiveId = x => typeof x === 'string' && /^[1-9][0-9]{0,19}$/.test(x);
const idList = x => Array.isArray(x) && x.length <= 10000 && x.every(positiveId);
requireThat(['discord', 'telegram'].includes(r.source), 'invalid source');
requireThat(positiveId(r.userId) && positiveId(r.messageId), 'IDs must be positive strings');
requireThat(typeof r.destinationId === 'string' &&
  (r.source === 'telegram' ? /^-?[1-9][0-9]{0,19}$/ : /^[1-9][0-9]{0,19}$/).test(r.destinationId), 'invalid destination');
requireThat(typeof r.requestedAt === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(r.requestedAt), 'timestamp must be UTC ISO with milliseconds');
requireThat(Number.isFinite(Date.parse(r.requestedAt)) && new Date(r.requestedAt).toISOString() === r.requestedAt, 'invalid timestamp');
requireThat(typeof r.text === 'string' && r.text.trim().length > 0 && r.text.length <= 2000, 'invalid request text');
requireThat(['movie', 'tv'].includes(r.mediaType), 'invalid media type');
requireThat(positiveId(r.mediaId) && positiveId(r.externalId), 'media IDs must be positive strings');
requireThat(typeof r.title === 'string' && r.title.trim().length > 0 && r.title.length <= 300, 'invalid title');
requireThat(typeof r.baselineCaptured === 'boolean', 'baseline state required');
requireThat(idList(r.preexistingFileIds) && idList(r.episodeIds), 'explicit file and episode lists required');
requireThat(r.mediaType === 'tv' ? r.episodeIds.length > 0 : r.episodeIds.length === 0, 'invalid episode scope');
const days = r.retentionDays === undefined ? null : r.retentionDays;
requireThat(days === null || (Number.isInteger(days) && days >= 1 && days <= 3650 && r.retentionExplicit === true), 'retention must be explicit and between 1 and 3650 days');
const canonical = ids => JSON.stringify([...new Set(ids)].sort());
return [{json: {
  requestKey: `${r.source}:${r.destinationId}:${r.messageId}`,
  source: r.source, userId: r.userId, destinationId: r.destinationId,
  messageId: r.messageId, requestedAt: r.requestedAt, text: r.text.trim(),
  mediaType: r.mediaType, mediaId: r.mediaId, externalId: r.externalId,
  title: r.title.trim(), episodeIdsJson: canonical(r.episodeIds),
  preexistingFileIdsJson: canonical(r.preexistingFileIds),
  baselineCaptured: r.baselineCaptured, retentionDays: days,
  deletionEligible: days !== null && r.baselineCaptured,
  state: 'registered',
}}];
