# Deployment and recovery

AccountContext serves port 80 and database-backed `/up`, with persistent state in `/storage/pb_data`. Build the server revision in `POCKETCONTEXT_VERSION`; publish only after application, identity/policy, portable client and container configuration/smoke/restore checks pass. Record the deployed source revision and immutable image digest in `DEPLOYMENT.md`.

## Configuration

| Variables | Use |
| --- | --- |
| `ACCOUNTCONTEXT_SUPERUSER_EMAIL`, `ACCOUNTCONTEXT_SUPERUSER_PASSWORD` | Dedicated maintenance identity, supplied together; never ordinary agent credentials |
| `ACCOUNTCONTEXT_GOOGLE_CLIENT_ID`, `ACCOUNTCONTEXT_GOOGLE_CLIENT_SECRET` | Separate Google Web client, supplied together; absence preserves stored settings |
| `ACCOUNTCONTEXT_GOOGLE_WORKSPACE_DOMAIN` | Exact trusted Workspace domain enabling validated JIT |
| `ACCOUNTCONTEXT_TRUSTED_PROXY_HEADER` | `X-Forwarded-For` behind the existing ONCE proxy |
| `BASE_URL` | Public HTTPS origin, supplied by ONCE |
| `LITESTREAM_BUCKET`, `LITESTREAM_PATH` | Dedicated private bucket and replica prefix |
| `LITESTREAM_ENDPOINT`, `LITESTREAM_REGION` | Verified S3 endpoint and `auto` for R2 |
| `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY` | Bucket-scoped object access; also used for complete snapshots |
| `ACCOUNTCONTEXT_BACKUP_INTERVAL` | Complete snapshot interval in seconds, default 3600 and maximum 3600 |
| `LITESTREAM_DISABLED` | Exactly `true` only for isolated development and restore verification |

The production origin is `https://accounts.pocketcontext.com`; database replicas use `accountcontext-backup` / `once-pocketcontext/accountcontext`, and complete snapshots use the separate `full-backups/` subprefix. Public access must remain disabled. Originals and snapshot archives contain confidential information and must not be placed in Git, CI artifacts or public links.

All app credentials are sourced from the deployment scaffold's ignored `.envrc.private` with `COLORS_PAR_APP_ACCOUNTCONTEXT_*` names. The runtime discards operator passwords and replica credentials before starting the application server. Protect host access and ONCE labels, which contain private configuration.

## First deployment and updates

Use the existing ONCE host and a separate persistent volume, initially one CPU and 512 MiB. Deploy the tested immutable image with `--auto-update=false`. Limit DNS/scaffold changes to this application. The source repository and tested image archives are public through GitHub Releases. Anonymous GHCR image access was verified at launch; package visibility remains independently configurable. CI supplies its short-lived registry token over the dedicated SSH connection; the fixed wrapper uses a private temporary Docker configuration and removes it afterward. See [deployment transport](../deploy/README.md).

Use `deploy/install.py` to install the dedicated root-owned `/usr/local/sbin/deploy-accountcontext` wrapper after adding the app-specific restricted SSH key. Its installer preserves sibling keys. The wrapper takes no arguments; its bounded optional stdin accepts registry credentials only. It locks this application, pulls the intended image, gracefully stops the sole existing container and verifies its exit before replacement. Never use rolling updates, broad scaffold convergence, or a second replica writer. Environment updates require the same lock and stop discipline.

The GitHub environment `once-pocketcontext` holds the dedicated deployment key and pinned host identity. Enable repository variable `COLORS_PROFILE=once-pocketcontext` only after first deployment and wrapper verification. Application users and `finance_members` are provisioned through operator REST maintenance or verified JIT, never by seeding real identities in schema migrations. JIT never grants finance or approval authority.

## Complete evidence recovery

Litestream alone backs up the database. The backup supervisor also takes an online SQLite snapshot and copies exactly the immutable original files referenced by that snapshot. It writes checksums, uploads a complete archive, and publishes its latest pointer only after upload succeeds. It takes snapshots at startup, one hour after each completed upload, and after a clean shutdown. A backup failure stops the writer instead of silently continuing without complete evidence protection. No snapshots or originals are automatically deleted in this release; monitor storage growth.

With a missing local database, startup prefers the latest complete snapshot and verifies its archive, database and original file hashes. This may recover an older consistent state than the newest database-only replica. If no complete snapshot exists, Litestream restore may proceed, but every document referenced by the restored database must have its correct original before startup. Inaccessible or corrupt recovery data fails closed. An existing database is never automatically rolled back; missing/corrupt originals require operator recovery.

The engineering target is approximately one hour of recoverable-data loss plus upload duration while complete backups succeed, and recovery within two hours for a small deployment. Validate measured results and current backup timestamps; neither target is a zero-loss guarantee.

For a restore drill, download a complete snapshot into an isolated destination, verify its checksum manifest, and start the pinned application with `LITESTREAM_DISABLED=true`, temporary storage and no production outbound settings. Check ordinary-user schema access and protected original bytes/permissions. Never point the restored instance at the live replica for writes. Keep test copies private and remove them after verification.

For production rollback, stop the only writer first. Use a previous image only if its schema is compatible. Otherwise restore a deliberate complete snapshot while production writers remain stopped; verify every original, source/server compatibility and the selected replica strategy before bringing one writer back. Do not silently repair an inconsistent volume by discarding newer financial records.

Synthetic OAuth tests and provider configuration checks do not establish a real human Google login. The unattended deployment handoff explicitly reports that check as unverified.
