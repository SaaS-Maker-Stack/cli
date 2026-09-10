"""Provisioning: best-effort, never aborts the scaffold.

A failed step prints its manual command and disables only its dependents;
everything independent still runs. `--skip-provision` lists the same steps
as manual commands.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from saas_maker.wizard import Answers


@dataclass
class StepResult:
    title: str
    ok: bool
    skipped: bool = False
    manual_cmd: str = ""
    detail: str = ""


@dataclass
class Step:
    title: str
    cwd: str  # relative to the project dir
    argv: list[str]
    needs: list[str] = field(default_factory=list)  # titles of prerequisite steps
    env: dict[str, str] = field(default_factory=dict)
    ok_in_stderr: list[str] = field(default_factory=list)  # failure exemptions

    @property
    def manual_cmd(self) -> str:
        return f"cd {self.cwd} && {' '.join(self.argv)}"


UV_SYNC = "Install backend dependencies (uv sync)"
MIGRATE = "Run migrations (alembic upgrade head)"


def plan(a: Answers) -> list[Step]:
    steps = [
        Step(UV_SYNC, "backend", ["uv", "sync"]),
        Step("Install frontend dependencies (npm install)", "frontend", ["npm", "install"]),
        Step("Install admin dependencies (npm install)", "admin", ["npm", "install"]),
    ]
    if a.pg_is_local:
        steps.append(
            Step(
                "Create database",
                "backend",
                ["createdb", "-h", a.pg_host, "-p", str(a.pg_port), "-U", a.pg_user, a.db_name],
                env={"PGPASSWORD": a.pg_password} if a.pg_password else {},
                ok_in_stderr=["already exists"],
            )
        )
    steps.append(
        Step(MIGRATE, "backend", ["uv", "run", "alembic", "upgrade", "head"], needs=[UV_SYNC])
    )
    return steps


def run(project_dir: Path, steps: list[Step], echo=print) -> list[StepResult]:
    results: list[StepResult] = []
    failed: set[str] = set()

    for step in steps:
        blocked = [n for n in step.needs if n in failed]
        if blocked:
            failed.add(step.title)
            results.append(
                StepResult(
                    step.title,
                    ok=False,
                    skipped=True,
                    manual_cmd=step.manual_cmd,
                    detail=f"skipped — needs: {blocked[0]}",
                )
            )
            echo(f"  ⏭  {step.title} (skipped — prerequisite failed)")
            continue

        echo(f"  ⏳ {step.title} …")
        try:
            proc = subprocess.run(
                step.argv,
                cwd=project_dir / step.cwd,
                env={**os.environ, **step.env},
                capture_output=True,
                text=True,
                timeout=900,
            )
            ok = proc.returncode == 0 or any(
                marker in (proc.stderr or "") for marker in step.ok_in_stderr
            )
            detail = "" if ok else (proc.stderr or proc.stdout).strip()[-400:]
        except FileNotFoundError:
            ok, detail = False, f"`{step.argv[0]}` not found on PATH"
        except subprocess.TimeoutExpired:
            ok, detail = False, "timed out"

        if ok:
            echo(f"  ✅ {step.title}")
        else:
            failed.add(step.title)
            echo(f"  ❌ {step.title} — run it yourself later:\n       {step.manual_cmd}")
        results.append(StepResult(step.title, ok=ok, manual_cmd=step.manual_cmd, detail=detail))
    return results
