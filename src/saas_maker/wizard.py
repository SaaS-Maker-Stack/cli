"""The `saas-maker new` wizard.

Every prompt maps to something the generated project consumes: a `.env`
value, a Kamal secret, a `config/deploy.yml` placeholder or the brand hue.
Defaults are the `--defaults` run (non-interactive, CI-friendly).
"""

from dataclasses import dataclass

import questionary

from saas_maker import stack
from saas_maker.color import parse_brand

# Named brand colors -> OKLCH hue. The template's palette derives every accent
# shade from this one angle (`--brand-hue` in frontend/src/index.css, DESIGN.md).
BRAND_COLORS: list[tuple[str, int | str]] = [
    ("indigo (default)", 265),
    ("blue", 250),
    ("teal", 185),
    ("green", 145),
    ("orange", 25),
    ("rose", 350),
    ("violet", 300),
    ("custom (hex like #0066ff, or a hue 0-360)", "custom"),
]


def display_name_from_slug(slug: str) -> str:
    """my-app -> My App (what generate-project.sh did)."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


@dataclass
class Answers:
    """Everything `saas-maker new` needs — defaults are the `--defaults` run."""

    project_name: str = "my-saas"
    display_name: str = ""  # defaults to the slug title-cased
    slogan: str = stack.TEMPLATE_SLOGAN
    brand_hue: int = stack.TEMPLATE_BRAND_HUE

    # Postgres (backend .env: POSTGRES_*)
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "postgres"
    pg_password: str = ""
    pg_db: str = ""  # defaults to the slug (underscored)

    # Deployment (config/deploy.yml + .kamal/secrets) — placeholders until filled
    docker_user: str = "your-username"
    docker_password: str = "your_docker_password"
    domain: str = ""  # defaults to <slug>.com
    server_ip: str = "your-server-ip"
    ssh_user: str = "deploy"

    # Production SMTP (.kamal/secrets only; local dev uses Mailpit on :1025)
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""  # defaults to noreply@<domain>

    @property
    def slug(self) -> str:
        return self.project_name.lower().replace("_", "-").replace(" ", "-")

    @property
    def name(self) -> str:
        return self.display_name or display_name_from_slug(self.slug)

    @property
    def db_name(self) -> str:
        return self.pg_db or self.slug.replace("-", "_")

    @property
    def domain_base(self) -> str:
        return self.domain or f"{self.slug}.com"

    @property
    def api_domain(self) -> str:
        return f"api.{self.domain_base}"

    @property
    def admin_domain(self) -> str:
        return f"admin.{self.domain_base}"

    @property
    def app_domain(self) -> str:
        return f"app.{self.domain_base}"

    @property
    def smtp_from(self) -> str:
        return self.smtp_from_email or f"noreply@{self.domain_base}"

    @property
    def pg_is_local(self) -> bool:
        return self.pg_host in ("localhost", "127.0.0.1")


def _valid_brand(value: str) -> bool | str:
    try:
        parse_brand(value)
    except ValueError as exc:
        return str(exc)
    return True


def _ask_project(a: Answers) -> None:
    a.display_name = questionary.text("Display name:", default=a.name).ask()
    a.slogan = questionary.text("Slogan (login page tagline):", default=a.slogan).ask()
    choice = questionary.select(
        "Brand color (drives the whole accent palette — buttons, links, focus rings; "
        "change it later in frontend/src/index.css):",
        choices=[questionary.Choice(label, hue) for label, hue in BRAND_COLORS],
        default=a.brand_hue if a.brand_hue in dict(BRAND_COLORS).values() else None,
    ).ask()
    if choice == "custom":
        raw = questionary.text(
            "Brand color as hex (#0066ff) or OKLCH hue angle 0-360:",
            default=str(a.brand_hue),
            validate=_valid_brand,
        ).ask()
        a.brand_hue = parse_brand(raw)
    else:
        a.brand_hue = choice


def _ask_postgres(a: Answers) -> None:
    where = questionary.select(
        "Where is your Postgres?",
        choices=[
            "local (this machine)",
            "docker-compose (the generated one)",
            "managed / remote host",
        ],
    ).ask()
    if where.startswith("managed"):
        a.pg_host = questionary.text("Host:").ask()
        a.pg_port = int(questionary.text("Port:", default="5432").ask())
        a.pg_user = questionary.text("User:", default="postgres").ask()
        a.pg_password = questionary.password("Password:").ask() or ""
    elif where.startswith("docker"):
        a.pg_host, a.pg_user, a.pg_password = "localhost", "postgres", "postgres"
    else:
        a.pg_user = questionary.text("Postgres user:", default=a.pg_user).ask()
        a.pg_password = questionary.password("Postgres password (blank if none):").ask() or ""
    a.pg_db = questionary.text("Database name:", default=a.db_name).ask()


def _ask_deploy(a: Answers) -> None:
    configure = questionary.confirm(
        "Configure deployment (Kamal) now? Placeholders are written otherwise.",
        default=False,
    ).ask()
    if not configure:
        return
    a.docker_user = questionary.text("Docker Hub username:", default=a.docker_user).ask()
    a.docker_password = (
        questionary.password("Docker registry password (blank to fill later):").ask()
        or a.docker_password
    )
    a.domain = questionary.text(
        "Base domain (app./admin./api. get prefixed):", default=a.domain_base
    ).ask()
    a.server_ip = questionary.text("Server IP:", default=a.server_ip).ask()
    a.ssh_user = questionary.text("SSH user:", default=a.ssh_user).ask()


def _ask_smtp(a: Answers) -> None:
    configure = questionary.confirm(
        "Configure production SMTP now? (local dev uses Mailpit on :1025 regardless)",
        default=False,
    ).ask()
    if not configure:
        return
    a.smtp_host = questionary.text("SMTP host:", default=a.smtp_host).ask()
    a.smtp_port = int(questionary.text("SMTP port:", default=str(a.smtp_port)).ask())
    a.smtp_user = questionary.text("SMTP user:").ask() or ""
    a.smtp_password = questionary.password("SMTP password:").ask() or ""
    a.smtp_from_email = questionary.text("From email:", default=a.smtp_from).ask()


def run_wizard(project_name: str) -> Answers:
    a = Answers(project_name=project_name)
    _ask_project(a)
    _ask_postgres(a)
    _ask_deploy(a)
    _ask_smtp(a)
    return a


def default_answers(project_name: str) -> Answers:
    """`--defaults`: non-interactive, CI-friendly placeholders."""
    return Answers(project_name=project_name)


# --- `generate module` prompts ----------------------------------------------


def run_module_wizard(name: str, default_fields: str) -> dict:
    """Ask for the Spanish labels, gender, fields and statuses of a module."""
    from saas_maker.naming import humanize

    label = questionary.text("Label, singular (e.g. Factura):", default=humanize(name)).ask()
    label_plural = questionary.text(
        "Label, plural (e.g. Facturas):",
        default=label + ("es" if label[-1:] not in "aeiou" else "s"),
    ).ask()
    feminine = questionary.confirm(
        'Is the label feminine? ("Nueva factura" vs "Nuevo proyecto")', default=False
    ).ask()
    fields = questionary.text(
        "Fields — name:kind[?][:Label], kinds: str text int float bool date datetime "
        "(first one is the title):",
        default=default_fields,
    ).ask()
    status = questionary.text(
        "Statuses — value=Label, comma-separated (blank for none):", default=""
    ).ask()
    return {
        "label": label,
        "label_plural": label_plural,
        "feminine": bool(feminine),
        "fields": fields,
        "status": status or None,
    }
