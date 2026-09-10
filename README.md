# saas-maker CLI

`uvx saas-maker new <name>` scaffolds a configured multi-tenant SaaS from the
[saas-maker](https://github.com/willywg/saas-maker) template (FastAPI + SQLModel
+ PostgreSQL backend, React 19 + Vite + shadcn/ui frontend, admin panel, Kamal
deploys). `saas-maker generate module <name>` adds a tenant-scoped CRUD — table,
API, page, sidebar entry and tests — to a generated project.

```bash
uvx saas-maker new my-saas                 # wizard → branding → .envs → uv/npm/createdb/migrate → git
uvx saas-maker new my-saas --defaults      # non-interactive, placeholder deploy config
uvx saas-maker new my-saas --skip-provision

cd my-saas
uvx saas-maker generate module invoice \
  --label Factura --label-plural Facturas --feminine \
  --fields "number:str:Número,amount:float:Monto,notes:text?:Notas,due:date?:Vence" \
  --status "draft=Borrador,sent=Enviada,paid=Pagada"
```

## `generate module`

- `--fields "name:kind[?][:Label],…"` — kinds `str text int float bool date datetime`;
  `?` = optional. The first field must be a required `str`: it is the title,
  the searchable column and the delete confirmation.
- `--status "value=Label,…"` — adds a status column, list filter and badge.
- `--label / --label-plural / --feminine` — Spanish UI copy ("Nueva factura").
- Without `--fields` the command asks; `--defaults` skips the questions.

What it writes (for `invoice`):

| Backend | Frontend |
|---|---|
| `app/models/invoice.py` | `src/types/api.ts` (Invoice types, at `// generator:types`) |
| `app/schemas/invoice.py` | `src/hooks/useInvoices.ts` |
| `app/services/invoice_service.py` | `src/components/features/invoices/` (list, form, delete, badge) |
| `app/controllers/invoices.py` | `src/pages/InvoicesPage.tsx` + test |
| `alembic/versions/<rev>_add_invoices_table.py` | `src/router/index.tsx`, `Sidebar.tsx` (at the anchors) |
| `tests/test_invoices.py` | |

Every service function filters by `organization_id`; a row of another
organization answers 404. Read: any member. Write: admin or owner.

## Generator anchors

`generate module` inserts code before these comment lines; projects generated
before they existed can add them by hand:

- `backend/app/main.py`: `# generator:tenant-routers` (after the last `include_router`)
- `backend/app/models/__init__.py`: `# generator:models` (inside `__all__`)
- `frontend/src/router/index.tsx`: `// generator:route-imports`, `// generator:routes`
- `frontend/src/components/layout/Sidebar.tsx`: `// generator:nav` (inside `navItems`)
- `frontend/src/types/api.ts`: `// generator:types` (end of file)

## Development

```bash
uv sync && uv run pytest
uv run saas-maker new demo --defaults --skip-provision --source ~/path/to/saas-maker
```

Apache-2.0.
