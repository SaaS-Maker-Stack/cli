"""Tool checks shown before the wizard — informative, never blocking."""

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    found: bool
    detail: str
    hint: str = ""


def _version(argv: list[str]) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return "?"


def run_checks() -> list[Check]:
    tools = [
        ("uv", ["uv", "--version"], "https://docs.astral.sh/uv/"),
        ("node", ["node", "--version"], "Node 24 — https://nodejs.org (or nvm)"),
        ("npm", ["npm", "--version"], "comes with Node"),
        ("psql", ["psql", "--version"], "PostgreSQL client (createdb) — optional"),
        ("git", ["git", "--version"], "https://git-scm.com"),
    ]
    checks = []
    for name, argv, hint in tools:
        found = shutil.which(name) is not None
        checks.append(Check(name, found, _version(argv) if found else "not found", hint))
    return checks
