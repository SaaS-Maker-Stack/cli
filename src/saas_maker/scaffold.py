"""`saas-maker new` orchestration: fetch → rename → .envs → provision → git init."""

import re
import shutil
import subprocess
from pathlib import Path

from saas_maker import envfiles, fetch, provision, rename, stack
from saas_maker.secrets_gen import GeneratedSecrets
from saas_maker.wizard import Answers

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ScaffoldError(RuntimeError):
    pass


def validate_name(name: str) -> str:
    slug = name.lower().replace("_", "-").replace(" ", "-")
    if not SLUG_RE.match(slug):
        raise ScaffoldError(
            f"'{name}' is not a valid project name — use lowercase letters, "
            "digits and dashes, starting with a letter"
        )
    return slug


def write_files(project_dir: Path, a: Answers, s: GeneratedSecrets, ref: str) -> None:
    """Branding + .env + Kamal secrets + README. Pure file writes."""
    rename.apply(project_dir, a)
    backend, frontend, admin = (project_dir / d for d in ("backend", "frontend", "admin"))
    (backend / ".env").write_text(envfiles.render_backend_env(a, s), encoding="utf-8")
    (frontend / ".env").write_text(envfiles.render_vite_env(), encoding="utf-8")
    (admin / ".env").write_text(envfiles.render_vite_env(), encoding="utf-8")
    for service in (backend, frontend, admin):
        (service / ".kamal").mkdir(exist_ok=True)
    (backend / ".kamal" / "secrets").write_text(
        envfiles.render_backend_secrets(a, s), encoding="utf-8"
    )
    for service in (frontend, admin):
        (service / ".kamal" / "secrets").write_text(
            envfiles.render_registry_secrets(a), encoding="utf-8"
        )
    (project_dir / "README.md").write_text(envfiles.render_readme(a, ref), encoding="utf-8")


def run_new(
    a: Answers,
    *,
    target_parent: Path,
    ref: str,
    source: Path | None = None,
    skip_provision: bool = False,
    echo=print,
) -> Path:
    slug = validate_name(a.project_name)
    project_dir = target_parent / slug
    if project_dir.exists():
        raise ScaffoldError(f"{project_dir} already exists")

    secrets = GeneratedSecrets()

    echo(f"📦 Fetching the template ({'local ' + str(source) if source else ref}) …")
    try:
        fetch.fetch_stack(project_dir, ref=ref, source=source)
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise

    echo("🖋  Branding + writing .env files …")
    write_files(project_dir, a, secrets, ref)

    if skip_provision:
        echo("⏭  Provisioning skipped (--skip-provision)")
        results = [
            provision.StepResult(s.title, ok=False, skipped=True, manual_cmd=s.manual_cmd)
            for s in provision.plan(a)
        ]
    else:
        echo("🔧 Provisioning …")
        results = provision.run(project_dir, provision.plan(a), echo=echo)

    # One repo per service (they deploy independently). After provisioning so
    # lockfile updates land in the first commit. .env and .kamal/secrets are
    # gitignored per service.
    for service in stack.SERVICES:
        _git_init(project_dir / service, f"Initial commit: {a.name} {service}", echo)

    echo(epilogue(a, project_dir, results))
    return project_dir


def epilogue(a: Answers, project_dir: Path, results: list[provision.StepResult]) -> str:
    lines = ["", f"✨ {a.name} is ready at {project_dir}", ""]
    pending = [r for r in results if not r.ok]
    if pending:
        lines.append("Pending steps (run them yourself):")
        for r in pending:
            reason = f"  # {r.detail}" if r.detail and not r.skipped else ""
            lines.append(f"  {r.manual_cmd}{reason}")
        lines.append("")
    lines += [
        "Run it:",
        f"  cd {project_dir.name}/backend && make dev       # API on :8090",
        f"  cd {project_dir.name}/frontend && npm run dev   # app on :5190",
        f"  cd {project_dir.name}/admin && npm run dev      # admin on :5191",
        "",
        "Add your first module:",
        "  saas-maker generate module invoice",
        "",
        "Deploy placeholders live in */config/deploy.yml and */.kamal/secrets.",
    ]
    return "\n".join(lines)


def _git_init(repo_dir: Path, message: str, echo=print) -> None:
    if shutil.which("git") is None:
        echo("⚠️  git not found — skipping the initial commits")
        return
    try:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_dir, check=True, timeout=30)
        subprocess.run(["git", "add", "--all"], cwd=repo_dir, check=True, timeout=30)
        identity: list[str] = []
        probe = subprocess.run(
            ["git", "config", "user.email"], cwd=repo_dir, capture_output=True, timeout=30
        )
        if probe.returncode != 0:
            identity = ["-c", "user.name=saas-maker", "-c", "user.email=saas-maker@localhost"]
        subprocess.run(
            ["git", *identity, "commit", "-q", "-m", message],
            cwd=repo_dir,
            check=True,
            timeout=30,
        )
    except Exception as exc:  # git trouble must not kill the scaffold
        echo(f"⚠️  git init failed in {repo_dir.name} ({exc}) — initialize it yourself")
