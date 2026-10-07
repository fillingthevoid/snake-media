# Public release preparation — October 2, 2026

Prepared as a separate repository. The original workspace, credentials and live
server installation were not changed by release preparation.

## Included

Bot source, offline tests, Docker configuration, placeholder environment file,
sanitized n8n development templates/builders, MIT license, security policy and CI.

## Excluded or replaced

- Private environment, credentials, databases, runtime state, screenshots,
  backups, deployment archives and operational verification records.
- Real Discord IDs, LAN/Tailscale addresses and host account paths replaced
  with examples.
- Workflow credential references replaced with explicit configuration slots;
  pinned/runtime data and instance metadata removed. Templates are inactive.
- Host-specific credential restoration and smoke scripts omitted.

## Verified locally

- 64 Python tests passed, including four release-scanner checks.
- 85 JavaScript policy/workflow tests passed.
- Private-value comparison checked all release text against collected credentials
  and the private address/identity mapping without printing secret values.
- Public-file scanner checked JSON credential headers/references, pinned state,
  token-shaped strings and forbidden configuration/state/archive files.
- Retention setup template initializes preview mode.

The public Docker image was not rebuilt locally because Docker is unavailable on
the preparation host. GitHub CI has been added but has not run remotely. These
are offline checks, not proof of a new end-to-end Discord/Telegram installation.
No publication or live service changes were performed during preparation.

Before publishing, inspect the staged files and repository metadata. Before each
later push, run `python tools/check_public_release.py` and review your diff.
The scanner is a guardrail, not a guarantee: keep private generated exports
outside the repository and rotate any accidentally published credential.

## Compare a later release with the live installation

Keep native exports private, then run:

```sh
python tools/workflow_bundle.py validate /private/live-workflows.json
python tools/workflow_bundle.py compare /private/live-workflows.json
```

The comparison checks node behavior, code, connections and workflow settings. It ignores layout, version metadata and installation-specific credential/table bindings. Differences print paths only, never private values. Review reported behavior changes before updating the sanitized maintained bundle.
