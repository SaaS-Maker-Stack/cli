"""`saas-maker generate module <name>` — a tenant-scoped CRUD on both sides.

Renders the Jinja templates under `templates/module/` (derived from the
`projects` reference module on the `reference/projects` branches of the
template repos) and wires the result at the `generator:*` anchors:

    backend/app/main.py                    # generator:tenant-routers
    backend/app/models/__init__.py         # generator:models
    frontend/src/router/index.tsx          // generator:route-imports, // generator:routes
    frontend/src/components/layout/Sidebar.tsx   // generator:nav
    frontend/src/types/api.ts              // generator:types

Everything is planned first (all files rendered, all anchors found) and only
then written, so a missing anchor never leaves a half-generated module.
"""

import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader

from saas_maker.fields import Field, Status
from saas_maker.naming import Names

ANCHOR_HELP = (
    "This project predates the generator anchors. Add the comment lines listed in "
    "https://github.com/SaaS-Maker-Stack/saas-maker#generator-anchors (or copy the reference "
    "module by hand with the saas-maker-add-module skill)."
)


class ModuleGenError(RuntimeError):
    pass


@dataclass
class Column:
    field: Field
    responsive: str


@dataclass
class Plan:
    created: dict[Path, str] = field(default_factory=dict)
    modified: dict[Path, str] = field(default_factory=dict)

    def add_new(self, path: Path, content: str) -> None:
        if path.exists():
            raise ModuleGenError(f"{path} already exists — pick another name or remove it")
        self.created[path] = content

    def apply(self) -> list[Path]:
        for path, content in {**self.created, **self.modified}.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return list(self.created) + list(self.modified)


_env = Environment(
    loader=PackageLoader("saas_maker", "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    autoescape=False,
)


def _render(name: str, ctx: dict) -> str:
    return _env.get_template(f"module/{name}").render(**ctx)


# --- project detection ---------------------------------------------------------


def detect_project(cwd: Path) -> Path:
    """Walk up from cwd to the directory holding backend/ and/or frontend/."""
    for candidate in (cwd, *cwd.parents):
        if (candidate / "backend" / "app" / "main.py").is_file() or (
            candidate / "frontend" / "src" / "router" / "index.tsx"
        ).is_file():
            return candidate
    raise ModuleGenError(
        "not inside a saas-maker project (no backend/app/main.py or "
        "frontend/src/router/index.tsx found upwards)"
    )


# --- anchors ------------------------------------------------------------------


def insert_before_anchor(text: str, anchor: str, snippet: str, *, where: str) -> str:
    """Insert `snippet` (one or more lines) right before the line holding `anchor`,
    re-using that line's indentation."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if anchor in line:
            indent = line[: len(line) - len(line.lstrip())]
            block = "".join(indent + s + "\n" for s in snippet.splitlines())
            return "".join(lines[:i]) + block + "".join(lines[i:])
    raise ModuleGenError(f"anchor `{anchor}` not found in {where}. {ANCHOR_HELP}")


def _insert_sorted(text: str, pattern: str, new_line: str, *, where: str) -> str:
    """Insert `new_line` into the run of consecutive statements matching `pattern`, sorted.

    A matching line that opens a parenthesised block (ends with `(`) is one statement
    together with everything up to its closing `)`, so a new import never lands inside
    a multi-line `from x import (...)`.
    """
    lines = text.splitlines(keepends=True)
    rx = re.compile(pattern)
    spans: list[tuple[int, int]] = []  # (start, end) inclusive, per statement
    i = 0
    while i < len(lines):
        if rx.match(lines[i]):
            end = i
            if lines[i].rstrip().endswith("("):
                while end < len(lines) - 1 and not lines[end].strip().startswith(")"):
                    end += 1
            spans.append((i, end))
            i = end + 1
        else:
            i += 1
    if not spans:
        raise ModuleGenError(f"could not find where to insert `{new_line.strip()}` in {where}")
    run = [spans[0]]
    for span in spans[1:]:
        if span[0] == run[-1][1] + 1:
            run.append(span)
    block = ["".join(lines[a : b + 1]) for a, b in run]
    if new_line + "\n" in block:
        return text
    block = sorted([*block, new_line + "\n"])
    return "".join(lines[: run[0][0]]) + "".join(block) + "".join(lines[run[-1][1] + 1 :])


def _add_to_import_line(text: str, prefix: str, name: str, *, where: str) -> str:
    """`from app.controllers import auth, base` -> adds `name`, keeps names sorted,
    wraps in parentheses when the line would exceed 100 chars (ruff-format style)."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            names = [n.strip() for n in line[len(prefix) :].strip().split(",") if n.strip()]
            if name in names:
                return text
            names = sorted([*names, name])
            one_line = prefix + ", ".join(names) + "\n"
            if len(one_line) <= 101:
                lines[i] = one_line
            else:
                lines[i] = prefix.rstrip() + " (\n" + "".join(f"    {n},\n" for n in names) + ")\n"
            return "".join(lines)
    raise ModuleGenError(f"could not find `{prefix.strip()}` in {where}")


def _add_lucide_icon(text: str, icon: str, *, where: str) -> str:
    rx = re.compile(r"^import \{([^}]*)\} from 'lucide-react';", re.M)
    match = rx.search(text)
    if not match:
        raise ModuleGenError(f"could not find the lucide-react import in {where}")
    names = [n.strip() for n in match.group(1).split(",") if n.strip()]
    if icon in names:
        return text
    names.append(icon)
    return (
        text[: match.start()]
        + "import { "
        + ", ".join(names)
        + " } from 'lucide-react';"
        + text[match.end() :]
    )


# --- alembic --------------------------------------------------------------


_REV_RE = re.compile(r"^revision(?:\s*:\s*str)?\s*=\s*['\"]([0-9a-zA-Z_]+)['\"]", re.M)
_DOWN_RE = re.compile(r"^down_revision[^=\n]*=\s*['\"]([0-9a-zA-Z_]+)['\"]", re.M)


def alembic_head(versions_dir: Path) -> str:
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in versions_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = _REV_RE.search(text)
        if not rev:
            continue
        revisions.add(rev.group(1))
        down = _DOWN_RE.search(text)
        if down:
            parents.add(down.group(1))
    heads = revisions - parents
    if len(heads) != 1:
        raise ModuleGenError(
            f"expected exactly one alembic head in {versions_dir}, found {sorted(heads) or 'none'}"
        )
    return heads.pop()


# --- planning -------------------------------------------------------------


def build_context(n: Names, fields: list[Field], status: Status | None) -> dict:
    title = fields[0]
    subtitle = next((f for f in fields[1:] if f.kind == "text" and f.optional), None)
    responsive = ["hidden sm:table-cell", "hidden md:table-cell", "hidden lg:table-cell"]
    candidates = [f for f in fields[1:] if f is not subtitle and f.kind != "text"][:3]
    columns = [Column(f, responsive[i]) for i, f in enumerate(candidates)]
    kinds = {f.kind for f in fields}
    return {
        "n": n,
        "fields": fields,
        "title": title,
        "subtitle": subtitle,
        "columns": columns,
        "status": status,
        "has_text": "text" in kinds,
        "has_date": "date" in kinds,
        "has_datetime_col": any(c.field.kind == "datetime" for c in columns),
        "uses_pyd_field": any(f.uses_pydantic_field for f in fields),
        "has_input": any(f.kind != "text" and f.kind != "bool" for f in fields),
        "has_textarea": "text" in kinds,
        "has_checkbox": "bool" in kinds,
        "required_extra": [f for f in fields[1:] if not f.optional and f.kind != "bool"],
        "needs_fire_event": any(
            not f.optional and f.kind in ("int", "float", "date", "datetime") for f in fields[1:]
        ),
    }


def plan_backend(backend: Path, ctx: dict) -> Plan:
    n: Names = ctx["n"]
    plan = Plan()
    app = backend / "app"
    plan.add_new(app / "models" / f"{n.snake}.py", _render("backend/model.py.j2", ctx))
    plan.add_new(app / "schemas" / f"{n.snake}.py", _render("backend/schemas.py.j2", ctx))
    plan.add_new(app / "services" / f"{n.snake}_service.py", _render("backend/service.py.j2", ctx))
    plan.add_new(
        app / "controllers" / f"{n.plural_snake}.py", _render("backend/controller.py.j2", ctx)
    )
    plan.add_new(
        backend / "tests" / f"test_{n.plural_snake}.py", _render("backend/test.py.j2", ctx)
    )

    versions = backend / "alembic" / "versions"
    rev = secrets.token_hex(6)
    migration_ctx = {
        **ctx,
        "rev": rev,
        "down_rev": alembic_head(versions),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
    }
    plan.add_new(
        versions / f"{rev}_add_{n.table}_table.py",
        _render("backend/migration.py.j2", migration_ctx),
    )

    main_py = app / "main.py"
    text = main_py.read_text(encoding="utf-8")
    text = _add_to_import_line(
        text, "from app.controllers import ", n.plural_snake, where="app/main.py"
    )
    text = insert_before_anchor(
        text,
        "# generator:tenant-routers",
        f"app.include_router({n.plural_snake}.router, "
        f'prefix="{n.api_prefix}", tags=["{n.plural_snake}"])',
        where="app/main.py",
    )
    plan.modified[main_py] = text

    init_py = app / "models" / "__init__.py"
    text = init_py.read_text(encoding="utf-8")
    text = _insert_sorted(
        text,
        r"^from app\.models\.\w+ import ",
        f"from app.models.{n.snake} import {n.camel}",
        where="app/models/__init__.py",
    )
    text = insert_before_anchor(
        text, "# generator:models", f'"{n.camel}",', where="app/models/__init__.py"
    )
    plan.modified[init_py] = text

    env_py = backend / "alembic" / "env.py"
    text = env_py.read_text(encoding="utf-8")
    text = _insert_sorted(text, r"^    [A-Z]\w*,$", f"    {n.camel},", where="alembic/env.py")
    plan.modified[env_py] = text
    return plan


def plan_frontend(frontend: Path, ctx: dict) -> Plan:
    n: Names = ctx["n"]
    status = ctx["status"]
    plan = Plan()
    src = frontend / "src"
    features = src / "components" / "features" / n.kebab_plural

    plan.add_new(src / "hooks" / f"use{n.camel_plural}.ts", _render("frontend/hook.ts.j2", ctx))
    debounce = src / "hooks" / "useDebounce.ts"
    if not debounce.exists():
        plan.add_new(debounce, _render("frontend/use_debounce.ts.j2", ctx))
    if status:
        plan.add_new(features / "status.ts", _render("frontend/status.ts.j2", ctx))
        plan.add_new(features / f"{n.camel}StatusBadge.tsx", _render("frontend/badge.tsx.j2", ctx))
    plan.add_new(features / f"{n.camel}List.tsx", _render("frontend/list.tsx.j2", ctx))
    plan.add_new(features / f"{n.camel}FormDialog.tsx", _render("frontend/form_dialog.tsx.j2", ctx))
    plan.add_new(
        features / f"Delete{n.camel}Dialog.tsx", _render("frontend/delete_dialog.tsx.j2", ctx)
    )
    plan.add_new(src / "pages" / f"{n.camel_plural}Page.tsx", _render("frontend/page.tsx.j2", ctx))
    plan.add_new(
        src / "pages" / f"{n.camel_plural}Page.test.tsx", _render("frontend/page_test.tsx.j2", ctx)
    )

    types = src / "types" / "api.ts"
    text = types.read_text(encoding="utf-8")
    text = insert_before_anchor(
        text, "// generator:types", _render("frontend/types.ts.j2", ctx), where="src/types/api.ts"
    )
    plan.modified[types] = text

    router = src / "router" / "index.tsx"
    text = router.read_text(encoding="utf-8")
    text = insert_before_anchor(
        text,
        "// generator:route-imports",
        f"import {{ {n.camel_plural}Page }} from '@/pages/{n.camel_plural}Page';",
        where="src/router/index.tsx",
    )
    text = insert_before_anchor(
        text,
        "// generator:routes",
        f"{{ path: '{n.api_prefix}', element: <{n.camel_plural}Page /> }},",
        where="src/router/index.tsx",
    )
    plan.modified[router] = text

    sidebar = src / "components" / "layout" / "Sidebar.tsx"
    text = sidebar.read_text(encoding="utf-8")
    text = _add_lucide_icon(text, n.icon, where="src/components/layout/Sidebar.tsx")
    text = insert_before_anchor(
        text,
        "// generator:nav",
        f"{{ label: '{n.label_plural}', path: '{n.api_prefix}', icon: {n.icon} }},",
        where="src/components/layout/Sidebar.tsx",
    )
    plan.modified[sidebar] = text
    return plan


# --- entry point ------------------------------------------------------------


def generate(
    n: Names,
    fields: list[Field],
    status: Status | None,
    *,
    cwd: Path,
    backend: bool = True,
    frontend: bool = True,
    echo=print,
) -> list[Path]:
    project = detect_project(cwd)
    backend_dir, frontend_dir = project / "backend", project / "frontend"
    ctx = build_context(n, fields, status)

    plans: list[tuple[Path, Plan]] = []
    if backend:
        if not (backend_dir / "app" / "main.py").is_file():
            raise ModuleGenError(f"no backend at {backend_dir} (use --frontend-only)")
        plans.append((backend_dir, plan_backend(backend_dir, ctx)))
    if frontend:
        if not (frontend_dir / "src" / "router" / "index.tsx").is_file():
            raise ModuleGenError(f"no frontend at {frontend_dir} (use --backend-only)")
        plans.append((frontend_dir, plan_frontend(frontend_dir, ctx)))

    written: list[Path] = []
    for _root, plan in plans:
        written += plan.apply()
    if backend:
        _format_backend(backend_dir, [p for p in written if backend_dir in p.parents], echo)
    return written


def _format_backend(backend_dir: Path, paths: list[Path], echo=print) -> None:
    """Best-effort ruff (isort + format) so `make lint` passes out of the box."""
    if shutil.which("uv") is None or not paths or not (backend_dir / "pyproject.toml").is_file():
        return
    rel = [str(p.relative_to(backend_dir)) for p in paths if p.suffix == ".py"]
    rel = [r for r in rel if not r.startswith("alembic/versions/")]
    try:
        subprocess.run(
            ["uv", "run", "ruff", "check", "--fix", "--select", "I", "-q", *rel],
            cwd=backend_dir,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["uv", "run", "ruff", "format", "-q", *rel],
            cwd=backend_dir,
            capture_output=True,
            timeout=120,
        )
    except Exception as exc:  # formatting is a nicety, never a failure
        echo(f"⚠️  ruff not run ({exc}); run `make format` in backend/")
