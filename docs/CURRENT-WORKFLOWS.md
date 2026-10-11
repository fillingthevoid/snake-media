# Maintaining workflows

The maintained workflow bundle is
[`config-templates/n8n-current-media-workflows.json`](../config-templates/n8n-current-media-workflows.json).
It includes the shared Discord/Telegram backend and current overlays. It is a
sanitized reference: credentials, users, service addresses, native tables and
webhook authentication must be configured before deployment.
Install the [Telegram control editor](../n8n/button-feedback/README.md) before
importing this bundle so poster cards can remove handled callback buttons.
Create and backfill the [completion index](../n8n/maintenance/README.md) and configure its table binding before enabling scheduled completion checks. Install both files supplied with the Telegram control editor for durable related-card cleanup.

Earlier JSON files and builders in `n8n/` are historical migration examples and
regression fixtures. Their existence does not make them additional active
workflows. Use the maintained bundle for a new installation and a fresh private
export for an existing installation. Never regenerate an existing server from
an older builder.

One entry point checks bundle references and prepares the current efficiency
overlay without contacting services:

```sh
python tools/workflow_bundle.py validate
python tools/workflow_bundle.py validate private-before.json
python tools/workflow_bundle.py apply-efficiency private-before.json private-after.json
```

The overlay preserves credentials and is safe to apply again. Keep private input
and output outside Git. Review changed workflows, save rollback, then use native
n8n import/publish tools while idle. The tool does not deploy or authorize users.
It checks duplicate IDs, node names and broken workflow/edge references; runtime
verification and credential/table configuration are still required.

For the October 9 review fixes, prepare a targeted overlay from a fresh private
export with `python n8n/review-fixes/patch.py private-before.json private-after.json`.
It restores and verifies monitoring before searching a missing movie, and embeds
the title-free extension-duration policy. Existing available movies, TV selection,
credentials, native tables and deployment metadata are preserved. See
[review fixes](../n8n/review-fixes/README.md) for the separate bot/alert-tool update.

The [short retention locks overlay](../n8n/retention-locks/README.md) moves watch
history and playback collection outside the mutation lock. Each title refreshes
its claims under a separate short acquisition of the same global lock. Native
nodes release verified preparation failures; uncertain mutations still require
guarded recovery. Apply this overlay last when using historical builders.
