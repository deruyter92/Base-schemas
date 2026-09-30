"""SCENE-shared deployment / dataset identity.

Placeholder — table definitions are subject to change.
"""

import datajoint as dj

from base_schemas.core.access_markers import SyncAuthority, mark_sync_authority
from base_schemas.schemas.provenance._schema import schema


@mark_sync_authority(SyncAuthority.SHARED)
@schema
class Deployment(dj.Manual):
    """Logical DB/instance/dataset identity for write provenance.

    Opaque ``deployment_id`` is stable across host/prefix moves. Human labels
    may change; identity must not. Stamp on row-meta tables at write time.
    """

    definition = """
    deployment_id: varchar(64)  # opaque stable token — never renamed
    ---
    label='': varchar(128)  # human label, e.g. kccl-prod
    """
