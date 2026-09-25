# Workflows

## Evidence and review

Upload the original using `upload FILE '{"owner":"USER_ID","title":"Invoice title"}'`. Record its returned ID and checksum. Documents require explicit ownership; ordinary users may upload only for themselves. Finance users can see company evidence and own-claim evidence. Downloads use a short-lived protected file token and verify SHA-256. A filename alone is not a public download URL.

Create bills in draft with source document, supplier, currency, exponent, net/tax/gross amounts, billed party and service period when known. Enter a business purpose and category; unknown facts must remain unknown. Preserve the tax shown without inferring treatment. Review requires the server's completeness and arithmetic checks. Material edits invalidate review; final corrections use explicit void/correction links. Never edit original bytes or an audit row.

## Payment matching

Record a payment independently from its bill. Allocate each settlement with `bill_minor` and `payment_minor`; the first is in the bill currency and the second in payment currency. Cross-currency allocations additionally require `fx_rate`, `fx_date`, and `fx_source`. Capture card/FX fees separately in `payments.fee_minor`; do not add them twice to allocation amounts. Partial/multiple allocations are supported subject to transactional limits. Credit notes and refund-direction payments remain distinct from outgoing payments. Void the allocation before voiding an allocated payment or bill when required by the server.

## Claims

Create a draft claim under the claimant's user ID, retaining billed party, actual payer, purpose, currency and source document. Submit for review. An explicitly authorized approver approves/rejects with a decision note; ordinary users cannot self-grant authority. Approved claims may be linked to payment through claim reimbursements. Reimbursement totals are separate from claim approval status. Recordkeeping never triggers a transfer.

## Imports

`import-csv FILE` accepts the exact header `collection,json`; each JSON cell contains a typed record object. One file holds 1–19 rows and commits together with an import marker in one REST batch. Monetary values must be JSON integers, not decimals or formatted currency strings. Supply IDs to link records within the batch; otherwise deterministic IDs derive from the input bytes and row position. Repeating identical bytes fails atomically as a duplicate. Semantically equivalent differently formatted imports still require review; no heuristic merger is performed. The marker preserves source filename and SHA-256. Documents must be uploaded separately. Split larger imports deliberately; separate files are separate transactions.

## Reports and accountant handoff

`report` returns bill totals by currency/kind/review state, payment totals by currency/direction/state, monthly payments, missing evidence, outstanding bills, unreimbursed approved claims, subscription commitments and the next 30 days of renewals. These are independent measures, never a combined expense total. Query allocations to compute outstanding bill balances and reimbursements; aggregates cover only your visible records. Never label a truncated query complete.

`export FILE.zip` requires finance authority, paginates all exported tables, downloads and hashes every visible original, repeats record reads and aborts when records/permissions changed. Run when writes are quiet; this is a stability check over multiple requests, not a single database snapshot. A failed attempt can leave a preparing export marker; inspect it before retrying. The client never overwrites an existing destination and creates output mode 0600. CSV cells beginning with formula-sensitive characters are apostrophe-prefixed; the manifest documents this reversible transformation and hashes every CSV/original. Archive paths derive from validated IDs and sanitized names. Review export contents before separately authorizing any delivery.
