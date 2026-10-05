# Current configuration templates

Maintained workflow reference, updated **2026-10-05**. Arr configuration snapshots
remain from **2026-10-02**:

- Radarr and Sonarr quality profiles, quality definitions, custom formats and delay profiles.
- Prowlarr application profiles and selected non-sensitive indexer settings. Indexer names are generic; credentials and URLs are omitted.
- `n8n-current-media-workflows.json`: current media workflows, including server
  health and excluding test and verification workflows. All are inactive, without
  pinned execution data or runtime state; credential bindings are placeholders.
  Set the health collector URL to your n8n Docker gateway; the address is an example.

These are reference templates. Configure credentials, URLs, users, channels, webhook authentication, workflow references and data-table references for your installation. Native workflow/table identifiers may remain as reference metadata; they do not create the corresponding backend resources on a new instance. Check every cross-workflow reference after import.

The `n8n/` directory elsewhere in this repository also includes historical development templates. Use this bundle when reviewing the latest exported workflow set; do not activate multiple historical versions of the same workflow.

Use the [workflow maintenance tool](../docs/CURRENT-WORKFLOWS.md) to validate the
bundle or prepare the current overlay against a private export.

No database, private credential export or recovery key belongs here. Complete recovery backups are [encrypted and stored privately](../docs/BACKUPS.md). New public snapshots require manual review and the public-file checks before publication.
