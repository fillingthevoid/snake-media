# October 9 review fixes

The maintained bundle includes a guarded missing-movie path: persist tracking and
subscription, restore Radarr monitoring, verify the exact movie identity and
`monitored:true`, then issue `MoviesSearch`. Any failed or mismatched verification
stops the search. Existing available movies keep their monitoring unchanged.

The embedded retention policy also accepts `extend N days` without a title. It
lists only the actor's owned requests, carries the duration through title
selection, and requires final confirmation. Bare `extend` still asks for a title
and duration. The Python bot distinguishes omitted days from an explicit value.

For an existing installation, use a fresh private workflow export:

```sh
python tools/workflow_bundle.py validate private-before.json
python n8n/review-fixes/patch.py private-before.json private-after.json
python tools/workflow_bundle.py validate private-after.json
```

The overlay preserves installation bindings, metadata and unrelated policies,
including multi-season selection. Reapplying it is unchanged. It rejects unknown
missing-movie routes, conflicting node identities and unsupported command URL
expressions. Private input/output must stay outside Git. The tool only prepares
files; review the changed workflows and retain rollback before any import/publish.

The workflow overlay does not update running Python processes. The corresponding
bot changes are in `src/snake_media/bot.py` and `confirmations.py`; alert changes
are in `tools/alert_probes.py` and `server_alerts.py`. Bot replies check escaped
text at the send boundary, use embeds for long replies and bound text fallbacks.
The monitor keeps processing health separate from button expiry and retires
resolved/unalerted notification history while preserving unresolved incidents.

All tests run offline with fake service boundaries. Applying source changes and
validating prepared exports does not verify a running installation.
