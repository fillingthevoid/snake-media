# Server health

`/serverstatus` gives authorized Discord users a private snapshot. It uses the same
user and channel checks as other requests. `/status` remains media request status.

The n8n overlay routes an exact `serverstatus` command after authorization and
before other command parsing. It does not acquire the media mutation lock.
`build.py` accepts a current private workflow export, an output directory and the
private collector URL. Save a rollback export before importing either workflow.
The HTTP node reuses the media webhook's Header Auth credential.

`tools/server_health.py` runs on the host under systemd. Bind its HTTP listener only
to n8n's Docker bridge gateway. Do not publish its port or mount the Docker socket
into the bot. It requires a private mode-0600 configuration with:

- `bind`, `port` (default 17492), and `secret` matching Header Auth's
  `X-Snake-Media-Key` value;
- `jellyfin`: `url` and private authentication `headers`;
- `services`: fixed `Jellyfin`, `Radarr`, `Sonarr`, `Prowlarr`, `SABnzbd`,
  `qBittorrent`, and `n8n` entries containing a `url`, optional `headers` and a
  `json` boolean (false for an HTML web interface).

URLs are deployment configuration, never caller input. The host also needs the
existing `/usr/local/sbin/snake-storage-check` guard and the main, overflow and pool
mounts. Cache probes for 60 seconds to limit repeated disk/API work. n8n rejects
reports older than two minutes and returns a friendly error on failed collection.

The report includes load, memory, uptime, disk capacity, mount checks, service
endpoint availability and active playback count. A read-only Jellyfin library
query chooses an existing local video and requests exactly bytes 0â€“4095 through
`/Videos/{id}/stream?Static=true`. Only an exact HTTP206 range response with a
video/binary content type and the expected bytes passes. No playback progress is
reported, media is never marked watched, and no transcode is started.

**This checks server file streaming.** It cannot certify client decoding,
transcoding, remote network throughput, every file in the library or physical disk
SMART health. A service being available means its configured API/web endpoint
responded, rather than a complete test of its internal jobs. Viewer names, titles,
file paths, URLs and raw technical errors are excluded from the report.

Verify unauthenticated collector requests return 403, n8n can reach it through
the private bridge, the media webhook rejects unauthorized users, and slash
commands synchronize after rebuilding the bot. Existing media requests and
retention workflows stay on their previous routes.

GPU utilization and VRAM come from nvidia-smi. Upload is the sum of transmitted
bytes on active physical network interfaces over a two-second sample. It includes
all host/container traffic leaving those interfaces, including LAN and VPN
transport. Virtual Docker and Tailscale interfaces are excluded to avoid double
counting. Reports are cached for up to 60 seconds. Optional metrics fail to
unavailable rather than zero. This measures current traffic, not uplink capacity.
