"""SCENE-shared lab provenance.

Placeholder — table definitions are subject to change.
"""

import datajoint as dj

from base_schemas.core.access_markers import (
    SyncAuthority,
    WriteRole,
    mark_sync_authority,
    mark_write_role,
)
from base_schemas.schemas.scene._schema import schema


@mark_sync_authority(SyncAuthority.CENTRAL)
@mark_write_role(WriteRole.ADMIN)
@schema
class Lab(dj.Manual):
    """Admin-only insertion: Lab / group that collected the data."""

    definition = """
    lab_id: varchar(8)  # short stable token, e.g. mlai — never renamed
    ---
    lab_name='': varchar(255)  # human-readable name
    institution='': varchar(255)
    """
