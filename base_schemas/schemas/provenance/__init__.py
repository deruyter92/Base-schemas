"""SCENE provenance (Deployment, row-meta tables, SchemaVersion).

Not part of the scientific graph. Row-meta tables FK scientific masters
(e.g. ``Session``, ``Lab``, ``Task``, ``Subject``) and stamp ``Deployment`` plus a
content hash and ``SCENE_WRITER_VERSION``.
"""

from base_schemas.schemas.provenance._schema import PROVENANCE_SCHEMA_VERSION

__all__ = ["PROVENANCE_SCHEMA_VERSION"]
