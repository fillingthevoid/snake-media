# Local and internet upload readings

## Goal

Both Discord and Telegram `/serverstatus` show local LAN upload and internet upload independently, with current two-second samples and elapsed-time weighted one-minute averages. Preserve the physical-interface total as a useful reconciliation reading. Missing or stale counters display unavailable, never a false zero.

## Approach

Use dedicated Linux nftables named byte counters at the physical interface egress hook. This sees host and Docker outbound traffic and the outer Tailscale transport once, without counting virtual interfaces again. Rules count only; they do not drop, reject, redirect, or change packets. Only the dedicated table is managed, preserving existing Docker and Tailscale rules.

Discover physical interfaces and directly connected LAN prefixes from the host. Classify destinations within those LAN prefixes, link-local destinations, local broadcast, and multicast as local. Classify public internet destinations as internet; private or reserved destinations outside the identified LAN and non-IP traffic remain other/unclassified. Do not assume every private address or every Tailscale address is LAN.

A small privileged counter publisher exports only counters, interface identity, timestamps, and classification identity to a runtime file. The existing unprivileged health collector reads this file. Do not grant the Discord container network privileges or provide a general privileged command endpoint. Runtime state is disposable; start the counter service at boot and restore only its own rules. Publish files atomically and reject stale or malformed data.

Tailscale encryption is measured by its outer destination. Public direct/relay transports count as internet; a local direct transport counts as local. A VPN using a local gateway can conceal the ultimate destination, so these are destination-based server-side estimates, not router WAN billing figures. Explain this limitation in documentation. Counter bytes also need not exactly equal NIC bytes because of accounting layers, offload, and link overhead; never infer internet upload by subtracting LAN from NIC totals.

## Presentation

- Local LAN upload: current Mbps; one-minute average Mbps.
- Internet upload: current Mbps; one-minute average Mbps.
- Other traffic: show when nonzero or unavailable.
- Keep total physical upload as separately labeled total.
- Averages warm up after restarts, resets, interface/classification changes, or missing data.
- Use the existing shared n8n formatter so both chat platforms match.

## Validation and deployment

Test classification, counter deltas, warmup, stale input, reset and topology changes, absence of duplicate counting, and shared report formatting. Validate nftables syntax before applying. Back up changed files and workflow exports, install only the counter service and scoped health changes, then deploy both platforms through the existing shared status workflow. Use guarded n8n restart only if needed.

Verify a known LAN transfer increments local counters, a bounded public HTTP transfer increments internet counters, and the health collector remains private. Check unrelated firewall rules and media service availability. Run focused and required release checks and compare installed code with the release before claiming completion.

## Alternatives considered

Packet capture offers destination detail but adds continuous packet processing and unnecessary visibility into connections. Router measurements can identify actual WAN traffic more exactly, but require a separate router integration. Dedicated kernel counters fit this small server best.
