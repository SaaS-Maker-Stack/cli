"""Branding pass: replace the template's placeholders with the project's values.

Ported from generate-project.sh: an ordered list of (old, new) pairs applied
to text files across the tree, plus a few file-specific pairs. Order matters
(`saas-template-frontend` before `saas-template`). The placeholders are
unique strings that never collide with code identifiers.
"""

import os
from pathlib import Path

from saas_maker import stack
from saas_maker.wizard import Answers

_TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".json",
    ".yml",
    ".yaml",
    ".md",
    ".toml",
    ".html",
    ".txt",
    ".sql",
    ".ini",
    ".css",
}
_TEXT_NAMES = {"Makefile", "Dockerfile", ".env.example", "secrets"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}

SUBMODULES_PARAGRAPH = (
    "`backend/`, `frontend/` and `admin/` are git submodules (each one is its own repo, "
    "deployed independently). Clone with `git clone --recurse-submodules`; commit and push "
    "inside each subrepo first, then update the pointer in the root repo."
)
OVERVIEW_SUBMODULES = (
    "This is the monorepo root containing frontend, backend, and admin as git submodules."
)
OVERVIEW_SEPARATE_REPOS = (
    "This is the project root; frontend, backend and admin are separate git repositories."
)
SEPARATE_REPOS_PARAGRAPH = (
    "`backend/`, `frontend/` and `admin/` are separate git repositories (each one is "
    "deployed independently with Kamal). Commit inside each one."
)


def tree_pairs(a: Answers) -> list[tuple[str, str]]:
    """Pairs applied to every text file, in order."""
    slug, db, name = a.slug, a.db_name, a.name
    t = stack.TEMPLATE_SLUG
    pairs = [
        (f"{t}-frontend", f"{slug}-frontend"),
        (f"{t}-admin", f"{slug}-admin"),
        (f"{t}-api", f"{slug}-api"),
        (t, slug),
        (stack.TEMPLATE_DB, db),
        (stack.TEMPLATE_DISPLAY_NAME, name),
        (stack.TEMPLATE_SLOGAN, a.slogan),
        # Docker images + registry (after the slug pass)
        (f"your-username/{slug}", f"{a.docker_user}/{slug}"),
        ("username: your-username", f"username: {a.docker_user}"),
        # Domains
        ("api.example.com", a.api_domain),
        ("admin.example.com", a.admin_domain),
        ("app.example.com", a.app_domain),
        ("noreply@example.com", a.smtp_from),
        ("your-server-ip", a.server_ip),
    ]
    return [(old, new) for old, new in pairs if old != new]


def file_pairs(a: Answers) -> dict[str, list[tuple[str, str]]]:
    """Pairs applied to specific files only."""
    hue, default_hue = a.brand_hue, stack.TEMPLATE_BRAND_HUE
    pairs: dict[str, list[tuple[str, str]]] = {
        "CLAUDE.md": [
            (SUBMODULES_PARAGRAPH, SEPARATE_REPOS_PARAGRAPH),
            (OVERVIEW_SUBMODULES, OVERVIEW_SEPARATE_REPOS),
        ],
        "DESIGN.md": [("name: SaaS Template", f"name: {a.name}")],
    }
    if hue != default_hue:
        pairs["frontend/src/index.css"] = [(f"--brand-hue: {default_hue};", f"--brand-hue: {hue};")]
        pairs["DESIGN.md"] += [
            (f"{default_hue} = indigo", f"{hue} (project brand hue)"),
            *[(f"{c} {default_hue})", f"{c} {hue})") for c in ("0.16", "0.03", "0.13", "0.06")],
        ]
    for service in stack.SERVICES:
        pairs[f"{service}/config/deploy.yml"] = [("user: deploy", f"user: {a.ssh_user}")]
    return pairs


def _is_text_file(path: Path) -> bool:
    return path.suffix in _TEXT_SUFFIXES or path.name in _TEXT_NAMES


def _replace_in(path: Path, pairs: list[tuple[str, str]]) -> bool:
    try:
        text = original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    for old, new in pairs:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def apply(project_dir: Path, a: Answers) -> list[str]:
    """Apply both passes; returns the relative paths actually touched."""
    touched: list[str] = []
    pairs = tree_pairs(a)
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for filename in files:
            path = Path(root) / filename
            if path.is_symlink() or not _is_text_file(path):
                continue
            if _replace_in(path, pairs):
                touched.append(str(path.relative_to(project_dir)))
    for rel, specific in file_pairs(a).items():
        path = project_dir / rel
        if path.is_file() and _replace_in(path, specific) and rel not in touched:
            touched.append(rel)
    return sorted(touched)
