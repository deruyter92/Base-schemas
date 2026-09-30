"""Shared core helpers (config + registry / versioning / hash / types)."""

from base_schemas.core.access_markers import (
    SyncAuthority,
    WriteRole,
    mark_sync_authority,
    mark_write_role,
    sync_authority_of,
    write_role_of,
)
from base_schemas.core.config import Settings, deployment_row_from_settings, load_settings
from base_schemas.core.hash import content_hash
from base_schemas.core.registry import SCENE_REGISTRY, SchemaRegistry, activate_schema
from base_schemas.core.types import DjKey, DjRow
from base_schemas.core.versioning import (
    SchemaVersionError,
    SchemaVersionStatus,
    assert_schema_compatible,
    check_schema_version,
    ensure_schema_version,
    get_db_schema_version,
)

__all__ = [
    "DjKey",
    "DjRow",
    "SCENE_REGISTRY",
    "SchemaRegistry",
    "SchemaVersionError",
    "SchemaVersionStatus",
    "Settings",
    "SyncAuthority",
    "WriteRole",
    "activate_schema",
    "assert_schema_compatible",
    "check_schema_version",
    "content_hash",
    "deployment_row_from_settings",
    "ensure_schema_version",
    "get_db_schema_version",
    "load_settings",
    "mark_sync_authority",
    "mark_write_role",
    "sync_authority_of",
    "write_role_of",
]
