# Server status

User approved `/serverstatus` on October 2. Access defaults to existing authorized
Discord users in allowed guild channels; replies are ephemeral. Existing `/status`
remains request status. Report host load/memory, main/SSD/pool free space and mount
guard, fixed media-service availability, Jellyfin active playback count and a bounded
sample video stream test. Do not expose viewers, titles, paths, credentials or raw
errors. A successful sample means server streaming works; client/network playback
and transcoding remain untested. Empty libraries or failed checks must not report
playback success. No watch-state updates, playback controls, searches or deletions.

Bot forwards `serverstatus` through the existing authenticated n8n media webhook.
n8n routes after its authorization gate, independently of media mutation locks,
and formats a versioned notice. A fixed read-only host health collector supplies
host metrics inaccessible from the bot container. Keep it on the private Docker
network with shared-header authentication, bounded work and a short cache. No
Docker socket or extra credentials in the Discord container, no public port.
No caller-supplied commands, URLs, filenames or item IDs reach the collector.

Tests cover denied callers, exact routing, stale/malformed telemetry, failed
services and absent/failed playback samples. Save rollback workflows and bot image
before deployment; verify native n8n execution, command synchronization and existing
media request routes. Publish only sanitized reusable source and documentation.
