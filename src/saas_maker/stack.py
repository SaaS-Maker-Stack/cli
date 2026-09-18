"""What the generator downloads: the saas-maker repos at a pinned ref.

The ref is pinned per CLI release: CLI vX.Y.Z scaffolds the template at tag
vX.Y.Z. `saas-maker new --ref <branch|tag>` overrides it for development
against unreleased branches.
"""

ORG = "SaaS-Maker-Stack"

# Template ref this CLI release scaffolds. Bumped together with the CLI version.
STACK_REF = "v0.1.0"

# target directory in the generated project -> GitHub repo name.
SERVICES = {
    "backend": "saas-maker-backend",
    "frontend": "saas-maker-frontend",
    "admin": "saas-maker-admin",
}

# The parent repo contributes root files to the generated project.
PARENT_REPO = "saas-maker"
PARENT_ROOT_FILES = [
    "CLAUDE.md",
    "DESIGN.md",
    "docker-compose.yml",
    "PRPs/templates/prp_base.md",
]

CODELOAD_URL = "https://codeload.github.com/{org}/{repo}/tar.gz/{ref}"

# Placeholders baked into the template (see generate-project.sh history).
TEMPLATE_SLUG = "saas-template"
TEMPLATE_DB = "saas_template"
TEMPLATE_DISPLAY_NAME = "SaaS Template"
TEMPLATE_SLOGAN = "Tu plataforma de gestion"
TEMPLATE_BRAND_HUE = 265
