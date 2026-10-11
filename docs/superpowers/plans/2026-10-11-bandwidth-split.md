# Bandwidth split implementation plan

**Goal:** Split server upload into LAN and internet readings for both bots.

**Architecture:** A privileged nftables counter publisher writes disposable runtime data; the existing unprivileged sampler calculates rates; the shared health formatter displays them. Python standard library, nftables and systemd only.

## Constraints

Manage only the dedicated counter table. Never count Docker/tunnel interfaces twice. Preserve existing health endpoint authorization and media routing. Expose missing data as unavailable. Document destination-based estimates and counter accounting differences.

## Tasks

- [x] Add failing behavioral tests for destination classification, counter validation, sample/average calculations, resets, staleness, and report formatting.
- [x] Implement `tools/network_accounting.py`: pure rules builder, native topology discovery, validated named-counter reader, atomic runtime publisher. Add `deploy/snake-network-accounting.service` with only NET_ADMIN capability and a writable runtime directory.
- [x] Implement `tools/bandwidth_metrics.py`: file-based validated split sampler with generation/reset/warmup behavior. Integrate it into `tools/performance_metrics.py`, returning `network.split` independently of NIC totals.
- [x] Update `n8n/server-health/policy.js` and its canonical workflow formatter only. Test invalid split readings leave base health available.
- [x] Run Python/JavaScript suites, workflow validation, privacy scan, and whitespace checks. Document configuration and limitations.
- [x] Back up installed modules and fresh active health workflow. Validate nft syntax, install/start accounting service, update collector and publish shared formatter; guard any n8n restart.
- [x] Verify LAN transfer and bounded public request classification, private endpoint authorization, running media services and active formatter; record evidence, commit and push.

Tests use literal byte deltas: 2 MB LAN and 0.5 MB internet over two seconds must report 8 and 2 Mbps. The one-minute fixture totals 60 MB LAN and 15 MB internet, giving the same respective averages. Reset/generation changes must warm up instead of producing negative rates. Classification fixtures include the physical LAN, remote public addresses, remote private addresses, IPv6 LAN and internet destinations.
