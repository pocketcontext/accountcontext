# AccountContext

PocketContext company expense evidence, subscriptions, payment reconciliation and reimbursement claims, operated through a portable agent skill. An authenticated browser reader complements the portable skill. Read records through authenticated SQL; write through PocketBase REST. This is an expense register, not a general ledger, tax filing service or payment processor.

Invoices/receipts/credit notes, payments, allocations, subscriptions and claims remain separate. Money uses integer minor units and explicit currency/exponent. USD and EUR reports remain separate; cross-currency settlement requires rate/date/source evidence. Records use revision checks, server attribution and transactional audit history. Original documents are immutable protected files. Imports and document text are untrusted data. Recording a payment never executes one.

See [the agreed brief](docs/implementation-brief.md), [data model](docs/data-model.md) and [deployment](docs/deployment.md) for detailed contracts. The production launch starts empty; no vendor accounts, invoices, balances or legal entities are invented.

## Run

Build the PocketContext commit in `POCKETCONTEXT_VERSION` with its required Go version, CGO and a C compiler. Start that binary from this repository:

```sh
/path/to/pinned/pocketcontext serve --dir ./pb_data --http 127.0.0.1:8090
```

Application migrations/configuration/hooks resolve from this directory. Keep `pb_data`, credentials and financial records out of Git. Use isolated temporary storage for tests.

## Access

PocketBase's existing default `users` identity serves humans and their agents. Verified Google Workspace JIT is restricted to the configured domain; direct signup is blocked. New users can submit/read their own claims and documents. Explicit finance membership grants company-wide finance access; approval is independently controlled. Source-only roles are never exported through SQL. Permissions apply separately to SQL, REST, files, exports and history. Operator provisioning is separate from ordinary activity.

Configure `ACCOUNTCONTEXT_GOOGLE_CLIENT_ID` and `ACCOUNTCONTEXT_GOOGLE_CLIENT_SECRET` together, using a separate Internal Google Web client with `http://127.0.0.1:8765/callback` and `https://accounts.pocketcontext.com/api/oauth2-redirect`. Set `ACCOUNTCONTEXT_GOOGLE_WORKSPACE_DOMAIN=pocketcontext.com`. Server-side claims validation enforces the exact domain and verified email. Real human Google browser login is explicitly outside automated acceptance and must be reported as unverified until exercised.

An operator disables a user rather than deleting their identity. Disabling rotates the token key and rejects subsequent authentication/read/write access; re-enabling needs fresh login. Google Workspace suspension alone does not revoke existing app sessions. In-flight operations may finish.

## Portable client

The standalone launcher `skills/accountcontext/accountcontext` requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Add its directory to `PATH` to use the commands below. Its first run installs the client from a pinned Git revision. For development and validation, install the current package in a virtual environment with `python3 -m pip install .`. Release the tested package commit first, then update the launcher to that full commit and verify the copied launcher through uv. The package pins its ObserveContext instrumentation dependency separately.


Install with `npx skills add pocketcontext/accountcontext --skill accountcontext`, or copy `skills/accountcontext/` anywhere. It requires Python 3.11+ and uv, `ACCOUNTCONTEXT_URL`, and `ACCOUNTCONTEXT_USER_EMAIL`; optional `ACCOUNTCONTEXT_USER_PASSWORD` supports provisioned password login. Never use operator credentials in the client.

```sh
accountcontext login --google
accountcontext whoami
accountcontext check
accountcontext report
```

Over SSH forward port 8765 from the browser machine. Application tokens are cached privately per server/email; active Google sessions renew. `logout` removes only the local cache. See [skill workflows](skills/accountcontext/references/workflows.md) for manual CSV imports, immutable evidence upload/download and finance-only CSV/originals ZIP export. Export does not deliver files to an accountant.

## Validation

All fixtures are synthetic and use isolated temporary databases:

```sh
python3 tests/launcher.py
python3 tests/integration.py --binary /absolute/path/to/pinned/pocketcontext
python3 tests/auth.py --binary /absolute/path/to/pinned/pocketcontext
python3 tests/oauth_integration.py --binary /absolute/path/to/pinned/pocketcontext
python3 tests/skill.py --binary /absolute/path/to/pinned/pocketcontext
python3 tests/skill.py --binary /absolute/path/to/pinned/pocketcontext --trace
python3 tests/deploy.py --binary /absolute/path/to/pinned/pocketcontext
python3 tests/oauth.py
python3 tests/client.py
python3 tests/deploy_workflow.py
python3 tests/bootstrap.py
python3 tests/backup.py
python3 tests/backup_integration.py --binary /absolute/path/to/pinned/pocketcontext
```

Container release gates additionally run `docker/smoke.py config`, `smoke`, and `restore` against the built image. Database-and-document recovery must verify original SHA-256 bytes and permissions. Litestream alone does not back up uploaded originals. Complete recoverable snapshots target at least hourly creation and two-hour recovery for the initial small deployment; these are engineering targets, not guarantees.

Disable ONCE automatic updates. Replace the app only through its dedicated locked graceful-stop wrapper, preserving one writer. Deployment uses a dedicated private R2 bucket/prefix, separate operator credentials and deployment key. Preserve sibling apps and never restore a second writer against the active production replica.

Infrastructure and client patterns were adapted from RaiseContext and TaskContext; requester filtering follows PeopleContext, using default `users` identities throughout.

Public tested container archives are published in [GitHub Releases](https://github.com/pocketcontext/accountcontext/releases); see [deployment transport](deploy/README.md) for checksums and registry authentication.

## Optional observability

The pinned server supports per-request, requester-owned buffer tracing. Ordinary requests remain untraced. See [the portable skill](skills/accountcontext/SKILL.md#optional-request-tracing) for separate ObserveContext login, command capture, SQL disclosure and retry instructions. Filtered snapshot timings preserve the application’s existing read policies. Validate adoption with `python3 tests/tracing.py --binary /absolute/path/to/pinned/pocketcontext`.

## Browser reader

The application origin serves a read-only reader inspired by WikiContext. Choose a business collection, search all authorized records, page through results, and follow explicit outgoing and reverse relationships. Stable `/#/<collection>/<record-id>` links survive login and reload; Copy record link omits search state while Copy search link preserves it. URLs show current records, not immutable historical snapshots. Search/filter state stays in the URL, so avoid sharing a search containing private terms.

Each request uses the existing filtered SQL snapshot. Related labels and lists are resolved through the same permissions, never unrestricted record expansion. Browser authentication uses the official PocketBase JavaScript SDK LocalAuthStore with an application-specific key. Sign-in persists across tabs and browser restarts in the same browser profile and origin; logout propagates to other tabs but does not revoke copied tokens. Tokens are accessible to application JavaScript, so sign out on shared devices. Existing per-tab sessions are discarded on upgrade and require one new login. Session changes clear displayed private data and subscriptions; stale requests cannot restore an earlier session. Active sessions refresh on startup or focus, at most once per five minutes. Realtime and file access retain their independent authorization; these readers do not subscribe to record events. Password and configured Google login use ordinary application identities. Markdown is rendered without raw HTML or remote images. On mobile the collection sidebar collapses into a Browse drawer. No record editing or acknowledgement is performed.

Build with Node.js 24 and pnpm 10.33.2 from `ui/`: `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm test`, and `pnpm build`. Then start the pinned server from the repository root. Run `python3 tests/ui_browser.py --binary /absolute/path/to/pinned/pocketcontext` after installing Chromium with `pnpm exec playwright install chromium` in `ui/`. Container builds include the reader; generated bundles are not committed.

## Runtime maintenance freeze

Superusers use `GET /api/context/maintenance` and generation-checked
`PUT /api/context/maintenance` with `{"readOnly":true,"expectedGeneration":N}`
to drain and block writes without restarting. Existing authorized reads and
protected original downloads remain available. Authentication that creates or
updates records is blocked; preserve an existing operator token for thaw.
Set `readOnly:false` with the returned generation to resume writes explicitly.

The private durable `pb_data/maintenance.json` marker survives restart. Frozen
startup requires the existing database, skips restore and superuser/settings
provisioning, verifies original files, and refuses pending migrations. Malformed
markers fail closed. Backup/Litestream supervision remains active; this is a
managed database/API freeze, not cross-host writer fencing or byte-immutable disk.
Keep the marker with migration snapshots and fence the source before cutover.

Validate with `python3 tests/maintenance_entrypoint.py` and
`python3 tests/maintenance.py --binary /absolute/path/to/pinned/pocketcontext`.

Replicated startup waits for a private Litestream IPC synchronization before
serving, including fresh Google-only databases. A failed initial sync refuses
traffic; clean early shutdown therefore uses an initialized replica.

## Primary object storage (opt-in)

Set all of `ACCOUNTCONTEXT_S3_BUCKET`, `ACCOUNTCONTEXT_S3_ENDPOINT`,
`ACCOUNTCONTEXT_S3_REGION`, `ACCOUNTCONTEXT_S3_ACCESS_KEY_ID`, and
`ACCOUNTCONTEXT_S3_SECRET_ACCESS_KEY` to use a dedicated private S3/R2 bucket
for PocketBase uploads. `ACCOUNTCONTEXT_S3_FORCE_PATH_STYLE` defaults to `true`.
Partial configuration and shared primary/replica buckets or access keys fail closed. This is primary file storage, separate from
the `LITESTREAM_*` SQLite replica bucket and prefix. Protected downloads still
require independent application authorization.

In this mode startup restores SQLite through Litestream and verifies every
referenced immutable original by streaming its remote SHA-256; it does not
restore or periodically create legacy database-and-file archives. Local mode
retains complete archives. Keep object retention independent of replica retention;
SQLite replication alone cannot recover deleted objects. Unexpected crashes can
lose database writes since Litestream is asynchronous.

This configuration does not move existing files. Copy and checksum all referenced
objects before enabling it. A frozen startup refuses any storage configuration
change: prepare the destination settings before establishing its frozen snapshot.
Preserve `maintenance.json`, pause CD, and fence the source before thawing a
destination. Never point a second writable process at the live replica.

Run `python3 tests/object_storage_settings.py` plus the documented backup,
maintenance and deployment tests. Use `tests/object_storage_integration.py --binary /path/to/pinned/server
--synthetic-bucket BUCKET` with a disposable local MinIO bucket and the S3
environment above for real uploads, protected downloads and database-only recovery.
Container and Litestream fresh-volume recovery validation remain release gates.

### Container primary-storage recovery gate

After building the image, run the existing `docker/smoke.py config`, `smoke`,
and `restore` checks, then `python3 docker/object_storage_smoke.py --image IMAGE`
(use the locked Python environment for VaultContext). The restore check builds
its pinned local MinIO fixture. The primary-storage check uses separate bucket-scoped
synthetic keys, uploads real protected files, rejects unrelated-user downloads,
and tests frozen restart plus a new destination volume. It compares every main
database table restored by Litestream before destroying the source volume and
explicitly thawing the destination. A final upload and clean stop are followed
by destruction of that volume and automatic entrypoint recovery into a third
empty volume, with authorized and denied protected-file checks. No cloud buckets
or live replicas are used.

A **frozen handoff bundle** must also carry `maintenance.json` and a consistent
SQLite backup of `auxiliary.db` from the stopped source: frozen startup refuses
to create a missing auxiliary database. The main `data.db` still comes from
Litestream. A writable disaster recovery can recreate auxiliary state, but must
not be substituted for a deliberately frozen migration. Keep source fencing and
this bundle explicit in migration tooling.
