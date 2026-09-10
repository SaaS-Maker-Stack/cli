# AGENTS.md — saas-maker CLI

The **project generator**: `uvx saas-maker new <name>` scaffolds a configured
multi-tenant SaaS from the saas-maker template; `saas-maker generate module
<name>` scaffolds a tenant-scoped CRUD (backend + frontend) inside it.
Part of [SaaS-Maker-Stack/saas-maker](https://github.com/SaaS-Maker-Stack/saas-maker).

## Stack & structure

Python ≥3.11 · `typer` (commands) · `questionary` (wizard) · `httpx` (fetch) ·
`jinja2` (module templates) · `uv` · pytest · ruff. PyPI package: `saas-maker`.

- `stack.py` — pinned template ref + repo map + template placeholders.
- `wizard.py` — `Answers` dataclass + prompts (defaults ARE the `--defaults` run),
  and the `generate module` prompts.
- `envfiles.py` — pure renderers: answers → `.env`, `.kamal/secrets`, README.
- `fetch.py` — codeload tarballs, degit-style; `--source` copies a local checkout.
- `rename.py` — the placeholder manifest (ported from generate-project.sh).
- `provision.py` — best-effort steps; a failure prints its manual command.
- `scaffold.py` — `new` orchestration: fetch → rename → envs → provision → git init
  per service (three repos, like the template's submodules).
- `naming.py` / `fields.py` — identifiers, Spanish copy, the `--fields`/`--status`
  DSL and every per-kind code fragment the templates use.
- `module_gen.py` + `templates/module/**` — `generate module`: plan everything
  (render + find anchors), then write. Templates mirror the `projects` reference
  module on the `reference/projects` branches of the template repos.

## Key rules

- The CLI must never import template code (it runs in uvx's ephemeral venv).
- Templates track the reference module: when `reference/projects` changes shape,
  update the `.j2` files (and the tests that pin their content).
- Generated code must pass the template's own gates: backend `make lint`
  (ruff + isort + format) and `make test`; frontend eslint + tsc + vitest.
  `_format_backend` runs ruff best-effort; TS templates must be clean as written.
- Anchors are inserted BEFORE the `generator:*` comment, re-using its indent.
  Missing anchor ⇒ error before anything is written.
- English-only code and output; the generated UI copy is Spanish (DESIGN.md).

## Dev

```bash
uv sync && uv run pytest && uv run ruff check src tests
uv run saas-maker new demo --defaults --skip-provision --source ~/proyectos/pet-projects/saas-maker
cd demo && uv run --project ~/proyectos/pet-projects/saas-maker-cli saas-maker generate module invoice --defaults
```

## Releasing

1. Tag the template repos (backend, frontend, admin, parent) `vX.Y.Z`.
2. `STACK_REF = "vX.Y.Z"` in `stack.py`; bump the version in `pyproject.toml`
   AND `src/saas_maker/__init__.py`. Tests, commit, push.
3. `git tag -a vX.Y.Z && git push origin vX.Y.Z` → `publish.yml` (PyPI trusted
   publishing). A version that reached PyPI is burned.
4. Verify: `uvx saas-maker@X.Y.Z --version`, then `new demo --defaults --skip-provision`.
