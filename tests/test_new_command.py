"""`saas-maker new` against a fake local template (--source), no network."""

from pathlib import Path

import pytest

from saas_maker import envfiles, rename, scaffold
from saas_maker.secrets_gen import GeneratedSecrets
from saas_maker.wizard import Answers, display_name_from_slug


@pytest.fixture
def template(tmp_path: Path) -> Path:
    src = tmp_path / "template"
    for service in ("backend", "frontend", "admin"):
        (src / service / "config").mkdir(parents=True)
        (src / service / "config" / "deploy.yml").write_text(
            f"service: saas-template-{service}\nimage: your-username/saas-template-{service}\n"
            "registry:\n  username: your-username\nservers:\n  web:\n    - your-server-ip\n"
            "ssh:\n  user: deploy\nproxy:\n  host: api.example.com\n"
        )
        (src / service / ".gitignore").write_text(".env\n.kamal/secrets\n")
    (src / "backend" / "pyproject.toml").write_text('name = "saas-template-api"\n')
    (src / "backend" / ".env").write_text("SECRET=never-copied\n")
    (src / "frontend" / "src").mkdir()
    (src / "frontend" / "src" / "index.css").write_text(":root {\n  --brand-hue: 265;\n}\n")
    (src / "frontend" / "package.json").write_text('{"name": "saas-template-frontend"}\n')
    (src / "frontend" / "node_modules").mkdir()
    (src / "frontend" / "node_modules" / "junk.js").write_text("x")
    (src / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\nSaaS Template - "
        + rename.OVERVIEW_SUBMODULES
        + "\n\n"
        + rename.SUBMODULES_PARAGRAPH
        + "\n\nDatabase saas_template.\n"
    )
    (src / "DESIGN.md").write_text("name: SaaS Template\nhue 265 = indigo\noklch(0.55 0.16 265)\n")
    (src / "docker-compose.yml").write_text("services: {}\n")
    (src / "PRPs" / "templates").mkdir(parents=True)
    (src / "PRPs" / "templates" / "prp_base.md").write_text("# PRP\n")
    return src


def test_new_scaffolds_a_branded_project(template: Path, tmp_path: Path):
    answers = Answers(
        project_name="acme-crm",
        brand_hue=145,
        docker_user="acme",
        domain="acme.io",
        server_ip="203.0.113.5",
        ssh_user="ubuntu",
    )
    lines: list[str] = []
    project = scaffold.run_new(
        answers,
        target_parent=tmp_path,
        ref="main",
        source=template,
        skip_provision=True,
        echo=lines.append,
    )
    assert project == tmp_path / "acme-crm"
    assert not (project / "backend" / ".env.bak").exists()
    assert not (project / "frontend" / "node_modules").exists()

    deploy = (project / "backend" / "config" / "deploy.yml").read_text()
    assert "service: acme-crm-backend" in deploy
    assert "image: acme/acme-crm-backend" in deploy
    assert "username: acme" in deploy
    assert "- 203.0.113.5" in deploy
    assert "user: ubuntu" in deploy
    assert "host: api.acme.io" in deploy

    assert "--brand-hue: 145;" in (project / "frontend/src/index.css").read_text()
    design = (project / "DESIGN.md").read_text()
    assert "name: Acme Crm" in design and "0.16 145)" in design
    claude = (project / "CLAUDE.md").read_text()
    assert "submodule" not in claude and "Database acme_crm." in claude
    assert (project / "PRPs/templates/prp_base.md").exists()

    env = (project / "backend" / ".env").read_text()
    assert "never-copied" not in env
    assert "POSTGRES_DB=acme_crm" in env and "APP_NAME=Acme Crm" in env
    assert "JWT_SECRET_KEY=" in env and "your_secret_key_here" not in env
    secrets = (project / "backend" / ".kamal" / "secrets").read_text()
    assert "FRONTEND_URL=https://app.acme.io" in secrets
    assert "SMTP_FROM_EMAIL=noreply@acme.io" in secrets
    assert (project / "frontend" / ".kamal" / "secrets").read_text().startswith("# Docker Registry")
    assert "# Acme Crm" in (project / "README.md").read_text()

    for service in ("backend", "frontend", "admin"):
        assert (project / service / ".git").is_dir()
    assert not (project / ".git").exists()
    assert any("Provisioning skipped" in line for line in lines)
    assert any("cd backend && uv sync" in line for line in lines)


def test_new_refuses_existing_dir_and_bad_names(template: Path, tmp_path: Path):
    (tmp_path / "taken").mkdir()
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.run_new(
            Answers(project_name="taken"),
            target_parent=tmp_path,
            ref="main",
            source=template,
            skip_provision=True,
            echo=lambda _: None,
        )
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate_name("Bad Name!")
    assert scaffold.validate_name("My_App") == "my-app"


def test_display_name_and_defaults():
    assert display_name_from_slug("somos-peru") == "Somos Peru"
    a = Answers(project_name="my-app")
    assert (a.name, a.db_name, a.domain_base, a.smtp_from) == (
        "My App",
        "my_app",
        "my-app.com",
        "noreply@my-app.com",
    )
    assert a.pg_is_local


def test_env_renderers_are_deterministic():
    a = Answers(project_name="demo", pg_password="pw")
    s = GeneratedSecrets(jwt_secret="x" * 64)
    backend = envfiles.render_backend_env(a, s)
    assert backend == envfiles.render_backend_env(a, s)
    assert "POSTGRES_PASSWORD=pw" in backend and "JWT_SECRET_KEY=" + "x" * 64 in backend
    assert "SMTP_HOST=localhost" in backend  # dev mail goes to Mailpit
    assert "SMTP_TLS=true" in envfiles.render_backend_secrets(a, s)  # prod secrets differ


def test_brand_colors_cover_the_default_hue():
    from saas_maker import stack
    from saas_maker.wizard import BRAND_COLORS

    hues = [hue for _, hue in BRAND_COLORS]
    assert stack.TEMPLATE_BRAND_HUE in hues
    assert hues[-1] == "custom"
    assert all(0 <= h <= 360 for h in hues if isinstance(h, int))
