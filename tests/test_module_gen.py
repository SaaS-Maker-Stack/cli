from pathlib import Path

import pytest

from saas_maker import module_gen
from saas_maker.fields import parse_fields, parse_status
from saas_maker.naming import Names


def _generate(project: Path, name="invoice", spec=None, status=None, **kw):
    names = Names.build(name, label=kw.pop("label", None), feminine=kw.pop("feminine", False))
    return module_gen.generate(
        names,
        parse_fields(spec or "name:str:Nombre,description:text?:Descripción"),
        parse_status(status),
        cwd=project,
        **kw,
    )


def test_generate_writes_both_sides_and_wires_anchors(project: Path):
    written = _generate(
        project,
        "invoice",
        "number:str:Número,amount:float:Monto,paid:bool:Cobrada",
        status="draft=Borrador,paid=Pagada",
        label="Factura",
        feminine=True,
    )
    rel = {str(p.relative_to(project)) for p in written}
    assert {
        "backend/app/models/invoice.py",
        "backend/app/schemas/invoice.py",
        "backend/app/services/invoice_service.py",
        "backend/app/controllers/invoices.py",
        "backend/tests/test_invoices.py",
        "frontend/src/hooks/useInvoices.ts",
        "frontend/src/hooks/useDebounce.ts",
        "frontend/src/components/features/invoices/status.ts",
        "frontend/src/components/features/invoices/InvoiceStatusBadge.tsx",
        "frontend/src/components/features/invoices/InvoiceList.tsx",
        "frontend/src/components/features/invoices/InvoiceFormDialog.tsx",
        "frontend/src/components/features/invoices/DeleteInvoiceDialog.tsx",
        "frontend/src/pages/InvoicesPage.tsx",
        "frontend/src/pages/InvoicesPage.test.tsx",
    } <= rel
    migrations = list((project / "backend/alembic/versions").glob("*_add_invoices_table.py"))
    assert len(migrations) == 1
    migration = migrations[0].read_text()
    assert "down_revision: Union[str, Sequence[str], None] = 'aaa111'" in migration
    assert "sa.Column('amount', sa.Float(), nullable=False)" in migration
    assert "ondelete='CASCADE'" in migration

    main_py = (project / "backend/app/main.py").read_text()
    assert "from app.controllers import auth, base, invoices, organizations" in main_py
    assert (
        'app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])\n'
        "# generator:tenant-routers"
    ) in main_py

    init_py = (project / "backend/app/models/__init__.py").read_text()
    assert (
        "from app.models.admin import AdminUser\nfrom app.models.invoice import Invoice\n"
        in init_py
    )
    assert '    "Invoice",\n    # generator:models' in init_py

    env_py = (project / "backend/alembic/env.py").read_text()
    assert "    AdminUser,\n    Invoice,\n    Organization," in env_py

    model = (project / "backend/app/models/invoice.py").read_text()
    assert 'INVOICE_STATUSES = ("draft", "paid")' in model
    assert "paid: bool = Field(default=False, nullable=False)" in model
    controller = (project / "backend/app/controllers/invoices.py").read_text()
    assert 'detail="Factura no encontrada"' in controller
    assert 'require_role("admin")' in controller

    router = (project / "frontend/src/router/index.tsx").read_text()
    assert (
        "import { InvoicesPage } from '@/pages/InvoicesPage';\n// generator:route-imports" in router
    )
    assert (
        "      { path: '/invoices', element: <InvoicesPage /> },\n      // generator:routes"
        in router
    )
    sidebar = (project / "frontend/src/components/layout/Sidebar.tsx").read_text()
    assert "import { LayoutDashboard, Building2, FolderKanban } from 'lucide-react';" in sidebar
    assert (
        "  { label: 'Facturas', path: '/invoices', icon: FolderKanban },\n  // generator:nav"
        in sidebar
    )
    types = (project / "frontend/src/types/api.ts").read_text()
    assert "export type InvoiceStatus = 'draft' | 'paid';" in types
    assert types.rstrip().endswith("// generator:types")

    dialog = (
        project / "frontend/src/components/features/invoices/InvoiceFormDialog.tsx"
    ).read_text()
    assert "'Nueva factura'" in dialog
    assert "<Checkbox checked={field.value} onCheckedChange={field.onChange} />" in dialog
    assert "amount: Number(data.amount)," in dialog
    test = (project / "frontend/src/pages/InvoicesPage.test.tsx").read_text()
    assert "fireEvent.change(screen.getByLabelText('Monto'), { target: { value: '9.5' } });" in test
    assert "amount: 9.5," in test and "paid: false," in test


def test_generate_without_status_skips_status_files(project: Path):
    written = _generate(project, "project")
    names = {p.name for p in written}
    assert "status.ts" not in names and "ProjectStatusBadge.tsx" not in names
    page = (project / "frontend/src/pages/ProjectsPage.tsx").read_text()
    assert "SelectTrigger" not in page
    schemas = (project / "backend/app/schemas/project.py").read_text()
    assert "Literal" not in schemas and "status" not in schemas


def test_generate_twice_keeps_both_modules(project: Path):
    _generate(project, "project")
    _generate(project, "invoice")
    main_py = (project / "backend/app/main.py").read_text()
    assert "invoices, organizations, projects" in main_py
    assert main_py.count("include_router") == 5
    sidebar = (project / "frontend/src/components/layout/Sidebar.tsx").read_text()
    assert sidebar.count("FolderKanban") == 3  # one import, two nav items share the icon


def test_generate_runs_from_inside_a_service_dir(project: Path):
    _generate(project / "backend" / "app", "note")
    assert (project / "frontend/src/pages/NotesPage.tsx").exists()


def test_generate_refuses_duplicates_and_writes_nothing_on_missing_anchor(project: Path):
    _generate(project, "invoice")
    with pytest.raises(module_gen.ModuleGenError):
        _generate(project, "invoice")

    sidebar = project / "frontend/src/components/layout/Sidebar.tsx"
    sidebar.write_text(sidebar.read_text().replace("// generator:nav", ""))
    with pytest.raises(module_gen.ModuleGenError, match="generator:nav"):
        _generate(project, "ticket")
    assert not (project / "backend/app/models/ticket.py").exists()
    assert not (project / "frontend/src/pages/TicketsPage.tsx").exists()


def test_backend_only_and_outside_project(project: Path, tmp_path: Path):
    _generate(project, "task", backend=True, frontend=False)
    assert (project / "backend/app/models/task.py").exists()
    assert not (project / "frontend/src/pages/TasksPage.tsx").exists()
    with pytest.raises(module_gen.ModuleGenError):
        _generate(tmp_path, "task")


def test_alembic_head_detection(tmp_path: Path):
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "a.py").write_text("revision = 'a1'\ndown_revision = None\n")
    (versions / "b.py").write_text("revision: str = 'b2'\ndown_revision: Union[str, None] = 'a1'\n")
    assert module_gen.alembic_head(versions) == "b2"
    (versions / "c.py").write_text("revision = 'c3'\ndown_revision = 'a1'\n")
    with pytest.raises(module_gen.ModuleGenError):
        module_gen.alembic_head(versions)
