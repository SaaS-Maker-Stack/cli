"""Secrets generated once per scaffold (never asked, never printed in full)."""

import secrets
from dataclasses import dataclass, field


def _hex(n_bytes: int = 32) -> str:
    return secrets.token_hex(n_bytes)


@dataclass
class GeneratedSecrets:
    jwt_secret: str = field(default_factory=_hex)
