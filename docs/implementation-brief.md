# Initial release contract

AccountContext is a single-organization expense evidence and reconciliation application. The initial release supports manual receipt/invoice uploads, CSV imports, subscriptions, credit notes/refunds, partial/multiple payments, personal expense claims/reimbursements, and accountant exports containing CSVs and original documents with checksums.

Store original currencies, including USD and EUR. Keep original invoice and settlement amounts separate; cross-currency allocations require explicit rate/date/source evidence. Reports group currencies separately. Preserve billed party, actual payer and unknown legal/tax details. Do not infer tax treatment.

Use PocketBase default `users`, verified Workspace Google JIT, private per-request SQL snapshots, independent REST/file authorization, revision-checked writes and transactional audit. Ordinary users see their own claims/documents. Operator-assigned finance users manage company expenses; approval is a separate authority, and authorized approvers may approve their own claims with audit history. Deployment-specific identities and credentials remain outside source control.

Original files are immutable and protected. Complete database-and-file backups supplement Litestream; restores must validate actual evidence bytes. Target hourly complete backups and a two-hour recovery for small deployments, subject to measured validation. Keep originals and audit history; no automatic statutory tax/retention claims.

Production starts without expense records. No general ledger, payroll, tax filing, payment execution, vendor API connections, automated email, third-party OCR or advertising campaign management. Export creation does not send it to an accountant.

The initial public repository/image target is `pocketcontext/accountcontext`; origin is `https://accounts.pocketcontext.com`. Reuse the specifically provisioned private bucket and Google client through private configuration. Deploy only on the existing ONCE host, keep one writer and automatic updates disabled, and preserve siblings. The serving image must pass application, authentication, policy, portable client, container and complete restore checks. Real Google browser login is explicitly outside unattended deployment verification.

Infrastructure sources: RaiseContext `44f8f10537388f9a934a2bc1800d3df6a046c580`, TaskContext `5bb214ef32fcffa9a42bb1de2d13cfd4052dc80f`, PeopleContext `b41a0f26f674222ae24b9268029a65c867ffaa99`. Initial server pin: `381f81042586afdaa6498b8c0e2a78229a55bdff`. Adapt infrastructure only; no donor records or credentials are copied.
