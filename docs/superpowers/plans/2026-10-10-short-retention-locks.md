# Short retention locks implementation

1. Add `n8n/retention-locks/policy.js`: validate group owner/identity, replace
   stale requests and amendments with current table reads, reject snapshots older
   than five minutes, and represent removed groups as deferred.
2. Add failing JS policy tests and Python overlay tests. Assert that scan dispatch
   occurs before lock acquisition, every group enters the coordinator, amendment
   and commit routes remain guarded, and error release requires preparing phase
   plus exact lock owner. Exercise the actual retention planner with a newly
   permanent amendment to prove stale scans cannot delete a protected file.
3. Add `n8n/retention-locks/patch.py`, preserving private native table IDs,
   credentials, HTTP headers, monitoring/search/deletion nodes and existing graph
   routes. Create internal `snakeRetentionGroupV1` for current reads under lock.
   Patch only the scan, coordinator and mutation-phase boundary in the media
   worker. Use native Set, IF and Data Table nodes on the safe failure release path.
4. Run relevant tests, full Python/JS suites, bundle validation and whitespace
   checks. Review the private overlay diff by paths without displaying secrets.
5. Export live workflows privately, apply the tested overlay privately, import
   only changed workflows plus the new internal child while idle and clear of
   the schedule boundary. Preserve rollback exports. Verify published internal
   versions without restart first; use the restart preflight if one is necessary.
6. Observe a scheduled preview scan. Check each group's independent coordinator
   owner, fresh claims, completed releases and unchanged protection decisions.
   Report any limitation and current cleanup mode. Document restart preflight
   as part of the operating procedure.
