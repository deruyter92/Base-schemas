"""Central configuration for base_schemas.

Read-only and side-effect free: nothing here mutates the environment or the
process.

Environment
-----------
DJ_SCHEMA_PREFIX
    Prefix for every schema name; empty, or ending in an underscore
    (e.g. ``dev_`` → ``dev_experiment``).
AUTO_ACTIVATE
    Opt-in eager bind. If unset/false (default), schemas stay unbound until
    ``activate_schema`` / ``SCENE_REGISTRY.activate`` — no DB required on
    import (see SCENE-Collaboration/Base-schemas#8). If truthy, ``make_schema``
    and table modules that honor this setting bind immediately.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_PREFIX_RE = re.compile(r"[A-Za-z0-9_]*")
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class Settings:
    """Immutable resolved settings. ``prefix`` includes the trailing underscore."""

    prefix: str
    auto_activate: bool

    def db_name(self, suffix: str) -> str:
        """Full prefixed database name, e.g. ``'experiment'`` → ``'dev_experiment'``."""
        if not suffix:
            raise ValueError("schema suffix must be a non-empty string")
        return f"{self.prefix}{suffix}"


def load_settings() -> Settings:
    """Resolve settings from the environment. Pure: no mutation, no caching."""
    prefix = (os.environ.get("DJ_SCHEMA_PREFIX") or "").strip()
    if not _PREFIX_RE.fullmatch(prefix):
        raise ValueError(f"Invalid DJ_SCHEMA_PREFIX {prefix!r}: must match [A-Za-z0-9_]*")
    if prefix and not prefix.endswith("_"):
        raise ValueError(
            f"Invalid DJ_SCHEMA_PREFIX {prefix!r}: must end with '_' "
            f"(e.g. {prefix + '_'!r} → {prefix + '_experiment'!r})"
        )
    return Settings(prefix=prefix, auto_activate=_env_flag("AUTO_ACTIVATE"))
