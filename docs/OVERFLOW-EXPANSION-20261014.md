# Additional SSD overflow capacity

The media pool supports a second overflow SSD at `/mnt/media-overflow-2`.
Storage stays primary-first, followed by the original overflow and then the new
SSD, with the existing 50 GiB placement reserve. Application media paths remain
the same. Existing files are not redistributed.

The host health collector includes both mounted overflow SSDs in the existing
`SSD` total. The `Pool` total includes all three drives. This preserves the
Discord/Telegram report format. The storage guard verifies every expected drive
and the exact live branch order; a missing or incorrect drive fails the guard.

The installed pool was expanded through its live mergerfs branch control. No
media container or Docker daemon restart was needed. Persistent UUID mounts and
Docker boot dependencies were updated alongside the guard, with private backups.

Verification covered six media containers reading and updating disposable files
on the new SSD as UID 1000, primary-first and forced-third-drive placement in an
isolated pool, and rejection of four wrong/hidden mounts in private namespaces.
The fixtures were removed and the live placement settings remained unchanged.

The collector change passed 288 Python tests and 10 relevant JavaScript tests.
The live pool is approximately 2,791 GiB total. SSD capacity adds space rather
than redundancy. No full server reboot or actual production disk-full test was
performed. Per-server UUIDs, serial numbers and rollback copies stay private.
