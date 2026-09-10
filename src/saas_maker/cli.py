"""SaaS Maker CLI — `uvx saas-maker new <name>` / `saas-maker generate module <name>`."""

from pathlib import Path

import typer

from saas_maker import (
    __version__,
    module_gen,
    preflight,
    scaffold,
    stack,
    wizard,
)
from saas_maker import (
    fields as fields_mod,
)
from saas_maker.naming import Names, NamingError

app = typer.Typer(
    name="saas-maker",
    help="The SaaS Maker generator — multi-tenant SaaS (FastAPI + React), omakase.",
    no_args_is_help=True,
)
generate_app = typer.Typer(help="Code generators (à la `rails generate`).", no_args_is_help=True)
app.add_typer(generate_app, name="generate")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"saas-maker {__version__} (template {stack.STACK_REF})")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the CLI and pinned template versions.",
    ),
) -> None:
    pass


@app.command()
def new(
    name: str = typer.Argument(..., help="Project name (lowercase, dashes)"),
    defaults: bool = typer.Option(
        False, "--defaults", help="Skip the wizard — placeholder config, CI-friendly."
    ),
    skip_provision: bool = typer.Option(
        False, "--skip-provision", help="Write files only; no uv/npm/createdb/migrate."
    ),
    ref: str = typer.Option(
        stack.STACK_REF, "--ref", help="Template tag/branch to scaffold (default: pinned)."
    ),
    source: Path | None = typer.Option(
        None, "--source", help="Local saas-maker checkout to copy instead of downloading (dev)."
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Parent directory for the project (default: current directory)."
    ),
) -> None:
    """Scaffold a configured SaaS project: wizard → branding → .envs → provision → git."""
    try:
        slug = scaffold.validate_name(name)

        typer.echo("🔎 Preflight:")
        for check in preflight.run_checks():
            mark = "✅" if check.found else "⚠️ "
            hint = "" if check.found else f"  ({check.hint})"
            typer.echo(f"  {mark} {check.name}: {check.detail}{hint}")
        typer.echo("")

        answers = wizard.default_answers(slug) if defaults else wizard.run_wizard(slug)
        scaffold.run_new(
            answers,
            target_parent=(output or Path.cwd()).expanduser().resolve(),
            ref=ref,
            source=source,
            skip_provision=skip_provision,
            echo=typer.echo,
        )
        typer.echo("")
        typer.echo("Teach your coding agent to extend this project:")
        typer.echo("  npx skills add SaaS-Maker-Stack/skills --skill '*'")
    except Exception as exc:
        if isinstance(exc, typer.Exit):
            raise
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@generate_app.command("module")
def gen_module(
    name: str = typer.Argument(..., help="Module name, snake_case singular (invoice, work_order)"),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="name:kind[?][:Label],… — kinds: str text int float bool date datetime. "
        "First field is the title. Default: " + fields_mod.DEFAULT_FIELDS,
    ),
    status: str | None = typer.Option(
        None, "--status", help="value=Label,… adds a status column, filter and badge."
    ),
    label: str | None = typer.Option(None, "--label", help="Spanish singular label (Factura)."),
    label_plural: str | None = typer.Option(None, "--label-plural", help="Spanish plural label."),
    feminine: bool = typer.Option(False, "--feminine", help='Feminine noun ("Nueva factura").'),
    plural: str | None = typer.Option(None, "--plural", help="snake_case plural override."),
    icon: str = typer.Option("FolderKanban", "--icon", help="lucide-react icon for the sidebar."),
    defaults: bool = typer.Option(False, "--defaults", help="No prompts; use flags/defaults."),
    backend_only: bool = typer.Option(False, "--backend-only"),
    frontend_only: bool = typer.Option(False, "--frontend-only"),
) -> None:
    """Scaffold a tenant-scoped CRUD (table, API, page, tests) inside a saas-maker project."""
    try:
        if fields is None and not defaults:
            answers = wizard.run_module_wizard(name, fields_mod.DEFAULT_FIELDS)
            label = label or answers["label"]
            label_plural = label_plural or answers["label_plural"]
            feminine = feminine or answers["feminine"]
            fields = answers["fields"]
            status = status or answers["status"]
        names = Names.build(
            name,
            plural=plural,
            label=label,
            label_plural=label_plural,
            feminine=feminine,
            icon=icon,
        )
        parsed_fields = fields_mod.parse_fields(fields or fields_mod.DEFAULT_FIELDS)
        parsed_status = fields_mod.parse_status(status)
        written = module_gen.generate(
            names,
            parsed_fields,
            parsed_status,
            cwd=Path.cwd(),
            backend=not frontend_only,
            frontend=not backend_only,
            echo=typer.echo,
        )
    except (module_gen.ModuleGenError, fields_mod.FieldError, NamingError) as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    project = module_gen.detect_project(Path.cwd())
    for path in written:
        typer.echo(f"  write   {path.relative_to(project)}")
    typer.echo("\nNext steps:")
    if not frontend_only:
        typer.echo("  cd backend && make migrate && make test && make lint")
    if not backend_only:
        typer.echo("  cd frontend && npm run lint && npm run typecheck && npm test")
    typer.echo(f"  document {names.api_prefix} in backend/CLAUDE.md and frontend/CLAUDE.md")


if __name__ == "__main__":
    app()
