# SQL schema and writes

All business records include id, revision, created/updated timestamps and server-owned created_by/updated_by. Read schema.json or the live schema for exported column types. Authority records and authentication secrets are not exposed. Every business update requires expected_revision; ordinary deletion is blocked.

| Collection | Domain fields |
| --- | --- |
| parties | `name` (text!), `kind` (text), `details` (text) |
| billing_accounts | `supplier` (rel:parties!), `billed_party` (rel:parties), `label` (text!), `external_id` (text) |
| documents | `owner` (rel:users!), `title` (text!), `original` (file), `sha256` (text) |
| bills | `supplier` (rel:parties!), `billing_account` (rel:billing_accounts), `billed_party` (rel:parties), `document` (rel:documents), `number` (text), `kind` (select:invoice,receipt,credit_note), `issue_date` (date), `due_date` (date), `service_start` (date), `service_end` (date), `currency` (currency), `currency_exponent` (exponent), `net_minor` (money), `tax_minor` (money), `gross_minor` (money), `business_purpose` (text), `category` (text), `status` (select:draft,reviewed,void), `void_reason` (text), `correction_of` (self) |
| bill_lines | `bill` (rel:bills!), `description` (text!), `net_minor` (money), `tax_minor` (money), `gross_minor` (money) |
| payments | `payer` (rel:parties), `document` (rel:documents), `paid_at` (date), `currency` (currency), `currency_exponent` (exponent), `amount_minor` (money), `fee_minor` (money), `direction` (select:outgoing,refund), `status` (select:recorded,void), `void_reason` (text) |
| payment_allocations | `bill` (rel:bills!), `payment` (rel:payments!), `bill_minor` (money), `payment_minor` (money), `fx_rate` (text), `fx_date` (date), `fx_source` (text), `status` (select:recorded,void), `void_reason` (text) |
| subscriptions | `supplier` (rel:parties!), `billing_account` (rel:billing_accounts), `name` (text!), `currency` (currency), `currency_exponent` (exponent), `amount_minor` (money), `interval` (select:monthly,annual,other), `renewal_date` (date), `status` (select:active,cancelled) |
| claims | `owner` (rel:users!), `document` (rel:documents), `title` (text!), `billed_party` (text), `payer` (text), `currency` (currency), `currency_exponent` (exponent), `amount_minor` (money), `business_purpose` (text), `status` (select:draft,submitted,approved,rejected,void), `decision_note` (text) |
| claim_reimbursements | `claim` (rel:claims!), `payment` (rel:payments!), `claim_minor` (money), `payment_minor` (money), `fx_rate` (text), `fx_date` (date), `fx_source` (text), `status` (select:recorded,void), `void_reason` (text) |
| import_batches | `source` (text!), `sha256` (text!), `notes` (text) |
| export_batches | `name` (text!), `notes` (text), `status` (select:preparing,complete,failed), `manifest_sha256` (text), `record_count` (money), `document_count` (money), `failure_reason` (text) |

`rel:collection` is a relation; `!` denotes required. Currency values use uppercase codes and explicit currency_exponent. Money is integer minor units bounded by safe numeric limits. No implicit FX conversion occurs. Document sha256 is server computed; supply original through multipart upload. Audit records are read-only and follow source visibility.

Finance authority is required for company bills, payments, subscriptions, imports and exports. Claimants access their own claims, reimbursements and documents. Finance approval is distinct from general identity admission. Verify the live schema with `check` before operation.
