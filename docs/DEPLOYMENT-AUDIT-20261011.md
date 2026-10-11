# Production deployment audit — October 11, 2026

Audited maintained release `0628419`, including the Telegram confirmation-photo
fallback. No application feature or fix remains awaiting production deployment.

## Verified production state

- All 45 production workflows are published. Compared their **active published
  history versions**, code, graph connections and settings with the maintained
  bundle using the existing sanitizer and runtime comparison tool. The sole code
  difference is one extra blank line in the notification queue; nonblank lines
  match exactly. No production workflow has an unpublished draft.
- The bundle's three setup/administration workflows are intentionally inactive:
  tracking-table setup, retention setup and retention administration. They are
  installation tools, not missing production features. The separate existing
  Jellyfin refresh workflow remains active.
- All 16 source modules inside the running Discord container match the maintained
  release. Its connection is recorded and its last 15 hours of logs contain zero
  ERROR lines. Both application containers are running without restart loops.
- All 29 installed host files match after LF/CRLF normalization. Checked the
  installed Telegram custom node and card store, recovery watchdog, bot source,
  requirements, Dockerfile, health collector, alert tools and backup worker.
- Admin and health daemons are active. Recovery, alerts and backup timers are
  active; their latest service results succeeded with exit status zero.
- Latest retained completion scan, Telegram notification poll and retention scan
  succeeded. The other three maintenance schedulers are published and configured
  not to retain successful executions, explaining their absent success history.
- n8n health returned 200, blocking execution count was zero, the global lock was
  clear and retention mode was enabled. Two Discord expiry reminders have
  delivery records. Sonarr's deployed descriptor limits remain 65,536 soft and
  524,288 hard.

## Source copies synchronized during audit

The server's deployment source folder still contained an older workflow-comparison
helper and an older duplicate Telegram custom-node source. Backed up and replaced
these two copies with the maintained helper and the already-installed sender.
The running application code was already current; no restart was needed.

Local historical `discord-bot/` sources are not the release authority. Future
deployments must use the maintained `snake-media-public/` sources and a fresh
private native workflow export. Historical builders and optional development or
Windows backup utilities are not additional production workloads.

## Completion evidence for future deployments

Before marking a feature or fix deployed, record the release, compare the running
container and installed host files, compare active published workflow versions,
and confirm service health after any guarded restart. Local tests or a successful
import alone do not prove production deployment. Keep rollback copies and state
any remaining runtime validation separately from deployment status.

The audit's transfer package was checked against committed public files and
contained only those files and opaque hashes. It contained no private workflow
export or credentials. Seven existing bundle/comparison tests passed and the
48-workflow maintained bundle validated. The photo-fallback tests had also passed
against the installed node inside the restarted n8n container.

A naturally eligible Telegram expiry reminder still needs end-to-end delivery
verification; its production workflows are deployed. This audit did not send
synthetic user messages or submit media requests.
