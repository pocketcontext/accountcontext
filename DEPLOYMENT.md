# AccountContext release and deployment evidence

Deployed on 25 September 2026 at https://accounts.pocketcontext.com. Initial production checks and isolated recovery from the real R2 snapshot passed.

| Item | Recorded value |
| --- | --- |
| Application source | `bc0899f47ad6b2e1381e52c8069e465a8202881c` |
| PocketContext pin | `381f81042586afdaa6498b8c0e2a78229a55bdff` |
| Production origin | `https://accounts.pocketcontext.com` |
| Validated ARM64 registry digest | `sha256:cdd5424bdb6dbd49f884b5cd2c25ef9b5e24e9ad8f5acde8797af206330687c5` |
| Release CI | [Run 36159710051](https://github.com/pocketcontext/accountcontext/actions/runs/36159710051) — application, container and multiarchitecture publication checks passed |
| Public image archives | [Source-pinned release](https://github.com/pocketcontext/accountcontext/releases/tag/image-bc0899f47ad6b2e1381e52c8069e465a8202881c) — AMD64 and ARM64 archives, checksums and digest metadata |
| Initial live image/container identity | Verified source and ARM64 digest above; one writer, one CPU, 512 MiB, persistent storage, automatic updates disabled |
| Complete production backup and isolated restore | Passed; isolated ordinary-user login and SQL verified, measured recovery 1.0 seconds with empty expense data |

CI exercised isolated synthetic application, auth/policy, OAuth provider/client, portable skill, deployment workflow, backup, container configuration, startup, persistence and restore tests. These results do not substitute for the live checks below. No real financial records are seeded for deployment acceptance.

## Image distribution

The source repository and tested image archives in GitHub Releases are public. Anonymous registry manifest, ARM64 configuration and every ARM64 layer were verified accessible. Package visibility is independent of source visibility; recheck after access-policy changes. The deployment workflow supplies its short-lived registry token through the dedicated SSH connection. The fixed wrapper uses a private temporary Docker credential directory and removes it afterward.

To inspect the published ARM64 image on an isolated Docker host, download the matching release archive and checksum file into a private working directory, then run:

```sh
sha256sum --check accountcontext-linux-arm64.tar.gz.sha256
docker load --input accountcontext-linux-arm64.tar.gz
```

The archive loads `ghcr.io/pocketcontext/accountcontext:sha-bc0899f47ad6b2e1381e52c8069e465a8202881c`. The archive checksum, architecture-specific registry digest and local Docker image ID are different identifiers; record each according to its source. See [deployment transport](deploy/README.md).

## Live acceptance

- [Initial deployment](https://github.com/pocketcontext/accountcontext/actions/runs/36160591094) passed after accepting the CI token's dotted/base64url format. Regression checks cover this format without logging credentials.
- HTTPS and database health passed; anonymous schema/SQL rejected. The default `users` collection, seven-day tokens, configured separate Google provider and OAuth-only signup rule were verified.
- Approved finance/approval membership was provisioned through maintenance REST. Ordinary finance login, refresh, schema and SQL passed; source-only authority/auth tables and ordinary REST financial reads were denied. Other Workspace users receive no finance membership. Requester isolation, role revocation and protected files were verified with synthetic tests.
- All twelve business collections started empty. No financial fixtures were inserted in production.
- One ARM64 app container uses persistent `/storage`, one CPU and 512 MiB with automatic updates disabled. Sibling containers retained their names and uptime. Existing authorized-key bytes were verified unchanged.
- Dedicated private R2 write/read/list/delete probe passed and was removed. Nonempty Litestream objects and a recent complete snapshot were verified. The complete snapshot restored into isolated local storage; checksum verification, restored finance login and SQL passed in 1.0 seconds. Temporary data was removed, and no production replica writer was started. Since production has no documents yet, original-byte recovery is established by the synthetic CI recovery tests.
- A controlled update through the dedicated restricted key passed: the old writer stopped cleanly before replacement, HTTPS/access checks passed afterward, and the approved finance identity was preserved. The dedicated root-owned fixed-target update wrapper is installed. Temporary bootstrap configuration, command and sudo permission were removed; the bootstrap workflow was disabled. CI uses pinned SSH host identity and a dedicated restricted key.
- Complete backups run at startup, one hour after each completed upload and after clean shutdown. Snapshots and originals have no automatic deletion; monitor backup age and storage growth. Logs, thumbnails and operator-uploaded user avatars are outside the financial-evidence snapshot.

Real human Google browser login remains **unverified by design** under the accepted unattended handoff. Automated synthetic OAuth tests and provider-configuration checks are not a claim that a person completed Google login.

## Recovery procedure

See [deployment and recovery](docs/deployment.md) for configuration and failure semantics. The engineering targets are approximately one hour plus upload duration of recoverable-data loss while complete snapshots succeed and recovery within two hours for the initial small deployment. Record actual backup age and restore duration; these are targets, not guarantees.

Complete snapshots contain a consistent database and every original referenced by that database, with SHA-256 checksums. They are stored privately under `once-pocketcontext/accountcontext/full-backups` in the dedicated bucket. Litestream alone does not recover original files. Recovery selects a consistent complete snapshot, which can be older than the newest database-only replica. Startup verifies all referenced originals and refuses inconsistent evidence.

For a read-only recovery drill, use a new isolated directory and the tested image. Prepare an operator-only mode-0600 environment file with the required replica variables; do not print it or commit it. The following template runs only the recovery helper, not the application writer:

```sh
ACCOUNTCONTEXT_DRILL_DIR=$(mktemp -d /tmp/accountcontext-drill.XXXXXXXX)
chmod 700 "$ACCOUNTCONTEXT_DRILL_DIR"
ACCOUNTCONTEXT_TEST_IMAGE=ghcr.io/pocketcontext/accountcontext:sha-bc0899f47ad6b2e1381e52c8069e465a8202881c
docker run --rm --env-file /protected/path/accountcontext-recovery.env \
  --mount "type=bind,src=$ACCOUNTCONTEXT_DRILL_DIR,dst=/storage" \
  --entrypoint python3 "$ACCOUNTCONTEXT_TEST_IMAGE" \
  /usr/local/bin/accountcontext-backup.py restore
docker run --rm --network none \
  --mount "type=bind,src=$ACCOUNTCONTEXT_DRILL_DIR,dst=/storage,readonly" \
  --entrypoint python3 "$ACCOUNTCONTEXT_TEST_IMAGE" \
  /usr/local/bin/accountcontext-backup.py verify
```

The restore helper returns without creating a database if no complete snapshot pointer exists. **Require a nonempty `pb_data/data.db` after this step** before treating it as a successful complete-snapshot drill. Preserve sanitized timing and checksum results. Starting a test server for authorization checks must use the isolated restored copy, localhost-only ports, `LITESTREAM_DISABLED=true`, and no production replica or outbound settings. Keep copies private and remove the specifically identified drill directory after verification.

Do not run an additional restored writer against the live replica. Do not discard a newer production volume merely because an older snapshot starts successfully.

## Rollback procedure

The normal `/usr/local/sbin/deploy-accountcontext` wrapper takes no arguments and updates its fixed current image target; it is not a generic rollback command. Its failure recovery restarts the old stopped container only when it is still the sole unambiguous matching container. If replacement or recovery remains ambiguous, leave the deployment failed and inspect it before starting another writer.

For deliberate rollback:

1. Acquire the same AccountContext deployment lock, `/run/lock/deploy-accountcontext.lock`. Disable concurrent deployment triggers during recovery. Identify the exact application container and persistent volume by the `accounts.pocketcontext.com` ONCE label; do not infer them from a broad image match.
2. Stop that sole container gracefully and require exit code zero. Preserve the stopped container and volume. If shutdown or backup fails, investigate before replacement; do not force a second writer to start.
3. Select a previously tested image and check its migration/schema compatibility. If compatible, perform a targeted ONCE replacement while holding the lock, with automatic updates disabled. Never use broad scaffold convergence or the ordinary `latest` update wrapper to select an older revision.
4. If schema rollback requires data recovery, select a deliberate complete snapshot, restore and verify it into a separate private destination, and document the recovery point and any excluded later records. Preserve the original production volume for reconciliation. Choose a new isolated replica prefix before starting recovered state; do not silently rewrite the live replica history.
5. Reconnect only one verified writer, then repeat HTTPS, auth/access, evidence, backup and sibling-health checks. Record the resulting source/image identity, recovery point and outcome here.

Operator recovery may require changing the fixed wrapper/image target and private deployment configuration; validate the targeted change before executing it. Never include credentials, complete container labels, private financial records, account identities or full environments in deployment evidence.
