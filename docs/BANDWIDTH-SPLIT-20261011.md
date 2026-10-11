# LAN and internet upload — deployed October 11, 2026

Both Discord and Telegram `/serverstatus` use the published shared formatter.
It now displays separate local LAN and internet upload readings with one-minute
averages, alongside the existing total. Other/unclassified traffic is independent.

## Verification

- 238 Python tests and 221 JavaScript tests passed; the 48-workflow bundle validated.
- Public-file and whitespace checks passed.
- Counter rules passed nftables syntax validation before installation.
- A 4 MiB LAN test download increased local counters; concurrent NostalgiaTV LAN
  traffic also contributed. A bounded 256 KiB public HTTPS upload succeeded and
  increased internet counters by 271,404 bytes, with only 2,752 LAN bytes during
  that interval.
- The accounting service and collector are active. After correcting the service
  account's script access, the accounting service has zero restarts. Both current
  readings and warmed-up averages were verified through the private collector.
- Installed modules match the release. The active published formatter matches
  the scoped native release, and both platform workflows call it. Executing that
  exact formatter with real collector data produced distinct LAN/internet lines.
- Unrelated firewall rules remained semantically identical, ignoring changing
  counter values and handles. All seven monitored services were healthy.
- n8n health returned 200 and unauthenticated collector access returned 403.

## Deployment and recovery

Backups of the prior collector, active workflow and firewall state are kept in
the private `backups/bandwidth-split-20261011` directory. Only the shared health
formatter was imported/published. The collector restarted; n8n restarted after a
fresh idle/lock/schedule guard. Media containers and the Discord bot were untouched.

The systemd accounting unit runs as the existing service account with ambient
NET_ADMIN capability and a restricted writable runtime directory. It counts
destinations without storing packet contents or changing firewall policy.

Destination-based LAN/internet classification is a server-side estimate. Outer
Tailscale public transport counts as internet. NIC and nftables byte accounting
differ, so the split is measured independently rather than subtracting from total.
See the server-health README for installation, limitations and removal.
