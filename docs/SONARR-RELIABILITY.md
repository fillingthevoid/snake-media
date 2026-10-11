# Sonarr open-file limits

An `Out of memory.` exit can occur while the server still has plenty of free RAM.
Check the process limits and descriptor count before changing memory settings.
In our observed failure, Sonarr reached its 1,024 open-file soft limit during a
scheduled media check while using about 242 MiB of RAM. Database reads also failed
intermittently. Both databases passed read-only integrity checks.

The targeted configuration change raises the soft limit for Sonarr only:

```yaml
services:
  sonarr:
    # Keep the existing image, environment, mounts and other settings.
    ulimits:
      nofile:
        soft: 65536
        hard: 524288
```

This example preserves the hard limit measured on our installation. Docker
Compose supports separate soft and hard limits through
[the service's ulimits setting](https://docs.docker.com/reference/compose-file/services/#ulimits).
Save the change in the source used to deploy the stack, then recreate only Sonarr.
Verify the actual application process limit afterward, rather than relying only
on the Compose text.

Verification should include a complete run of the job that caused the failure,
the peak descriptor count, the count after completion, API availability and
whether the application restarted. A higher ceiling avoids the observed limit;
continued growth after jobs finish still needs investigation.

Our live verification completed the same scheduled job with 1,155 descriptors
and no application restart. Usage returned to 264 afterward, with the same
process ID. The peak was mostly temporary network connections. This verified
the limit change against the workload that had previously crashed Sonarr.

Keep diagnostic traces and private deployment backups outside the public repo.
