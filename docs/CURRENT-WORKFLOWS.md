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
