"""A minimal fake saas-maker project with the generator anchors."""

from pathlib import Path

import pytest

MAIN_PY = """from fastapi import FastAPI

from app.controllers import auth, base, organizations

app = FastAPI()
app.include_router(base.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
# generator:tenant-routers
"""

MODELS_INIT = """from app.models.admin import AdminUser
from app.models.tenant import (
    Organization,
    User,
)

__all__ = [
    "Organization",
    "User",
    "AdminUser",
    # generator:models
]
"""

ENV_PY = """from app.models import (  # noqa: F401
    AdminUser,
    Organization,
    User,
)
"""

MIGRATION = '''"""base"""
revision: str = 'aaa111'
down_revision = None
'''

ROUTER = """import { DashboardPage } from '@/pages/DashboardPage';
// generator:route-imports

export const router = createBrowserRouter([
  {
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      // generator:routes
    ],
  },
]);
"""

SIDEBAR = """import { LayoutDashboard, Building2 } from 'lucide-react';

const navItems: NavItem[] = [
  { label: 'Panel Principal', path: '/dashboard', icon: LayoutDashboard },
  // generator:nav
];
"""

TYPES = """export interface MessageResponse {
  message: string;
}

// generator:types
"""


def make_project(root: Path) -> Path:
    backend = root / "backend"
    (backend / "app" / "models").mkdir(parents=True)
    (backend / "app" / "schemas").mkdir()
    (backend / "app" / "services").mkdir()
    (backend / "app" / "controllers").mkdir()
    (backend / "tests").mkdir()
    (backend / "alembic" / "versions").mkdir(parents=True)
    (backend / "app" / "main.py").write_text(MAIN_PY)
    (backend / "app" / "models" / "__init__.py").write_text(MODELS_INIT)
    (backend / "alembic" / "env.py").write_text(ENV_PY)
    (backend / "alembic" / "versions" / "aaa111_base.py").write_text(MIGRATION)

    frontend = root / "frontend" / "src"
    for sub in ("router", "components/layout", "components/features", "types", "hooks", "pages"):
        (frontend / sub).mkdir(parents=True, exist_ok=True)
    (frontend / "router" / "index.tsx").write_text(ROUTER)
    (frontend / "components" / "layout" / "Sidebar.tsx").write_text(SIDEBAR)
    (frontend / "types" / "api.ts").write_text(TYPES)
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return make_project(tmp_path / "demo")
