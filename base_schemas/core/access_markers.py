"""Access-intent markers for SCENE tables (documentation for deploy / grants).

These do not enforce MySQL privileges. They name which database role should
INSERT. ``ADMIN_WRITE`` tables are catalog rows (pipeline users SELECT only).
``PIPELINE_WRITE`` tables are everyday ingestion rows.
"""

from __future__ import annotations

from enum import Enum


class AccessRole(str, Enum):
    """Intended write role for a table (hint for DB grants, not enforcement)."""

    ADMIN_WRITE = "admin_write"
    PIPELINE_WRITE = "pipeline_write"


def mark_access_role(role: AccessRole):
    """Declare which database role should INSERT into this table."""

    def decorator(cls):
        cls._access_role = role
        return cls

    return decorator
