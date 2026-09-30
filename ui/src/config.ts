export interface Entity {
  table: string;
  label: string;
  title: string[];
  subtitle?: string[];
  search: string[];
  filters?: Record<string, string[]>;
  relations?: Record<string, string>;
  hidden?: string[];
  markdown?: string[];
  menu?: boolean;
  files?: string[];
  relationLabels?: Record<string, string>;
}
export const app: { name: string; authCollection: string; entities: Entity[] } =
  {
    name: "AccountContext",
    authCollection: "users",
    entities: [
      {
        table: "claims",
        label: "Claims",
        title: ["title"],
        search: ["id", "title", "business_purpose"],
        filters: {
          status: ["draft", "submitted", "approved", "rejected", "void"],
        },
        relations: {
          owner: "user_directory",
          document: "documents",
        },
        markdown: ["business_purpose", "decision_note"],
      },
      {
        table: "documents",
        label: "Documents",
        title: ["title"],
        search: ["id", "title", "sha256"],
        relations: {
          owner: "user_directory",
        },
        files: ["original"],
      },
      {
        table: "bills",
        label: "Bills",
        title: ["number"],
        search: ["id", "number", "business_purpose", "category"],
        subtitle: ["status", "currency"],
        filters: {
          status: ["draft", "reviewed", "void"],
        },
        relations: {
          supplier: "parties",
          billing_account: "billing_accounts",
          billed_party: "parties",
          document: "documents",
          correction_of: "bills",
        },
        markdown: ["business_purpose"],
      },
      {
        table: "payments",
        label: "Payments",
        title: ["paid_at"],
        search: ["id", "paid_at", "direction"],
        subtitle: ["currency", "status"],
        relations: {
          payer: "parties",
          document: "documents",
        },
      },
      {
        table: "subscriptions",
        label: "Subscriptions",
        title: ["name"],
        search: ["id", "name"],
        subtitle: ["status", "currency"],
        relations: {
          supplier: "parties",
          billing_account: "billing_accounts",
        },
      },
      {
        table: "parties",
        label: "Parties",
        title: ["name"],
        search: ["id", "name", "kind", "details"],
        subtitle: ["kind"],
        markdown: ["details"],
      },
      {
        table: "billing_accounts",
        label: "Billing accounts",
        title: ["label"],
        search: ["id", "label", "external_id"],
        relations: {
          supplier: "parties",
          billed_party: "parties",
        },
      },
      {
        table: "bill_lines",
        label: "Bill lines",
        title: ["description"],
        search: ["id", "description"],
        relations: {
          bill: "bills",
        },
        menu: false,
      },
      {
        table: "payment_allocations",
        label: "Payment allocations",
        title: ["id"],
        search: ["id", "id"],
        relations: {
          bill: "bills",
          payment: "payments",
        },
        menu: false,
      },
      {
        table: "claim_reimbursements",
        label: "Reimbursements",
        title: ["id"],
        search: ["id", "id"],
        relations: {
          claim: "claims",
          payment: "payments",
        },
        menu: false,
      },
      {
        table: "user_directory",
        label: "People",
        title: ["name"],
        search: ["id", "name"],
        menu: false,
      },
    ],
  };
for (const e of app.entities)
  if (e.table !== "user_directory")
    e.relations = {
      ...e.relations,
      created_by: "user_directory",
      updated_by: "user_directory",
    };
