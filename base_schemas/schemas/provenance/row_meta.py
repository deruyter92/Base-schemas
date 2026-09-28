"""Row-level write provenance for tracked tables."""

from __future__ import annotations

import datajoint as dj

from base_schemas.schemas.provenance._schema import schema
from base_schemas.schemas.scene.lab import Lab  # noqa: F401
from base_schemas.schemas.scene.session import Session  # noqa: F401
from base_schemas.schemas.scene.subject import Subject  # noqa: F401
from base_schemas.schemas.scene.task import Task  # noqa: F401


class _Base:
    """Row-level metadata for a master table.

    Intended to be written by a supported registration path (not hand-edited). Use for sync
    etags and writer-version provenance — not schema DDL (see ``SchemaVersion``).

    ``ingestion_version`` stores ``SCENE_WRITER_VERSION`` at write time.
    ``content_hash`` is a SHA-256 etag of the payload (defined in ingestion)
    ``deployment_id`` identifies which DB/instance/dataset wrote the row.
    """

    ROW_META_ATTRS = """
    ---
    -> Deployment
    ingestion_version: varchar(32)  # SCENE_WRITER_VERSION at write time
    content_hash: char(64)          # sha256 of the caller payload
    updated_at: datetime
    """


@schema
class SessionRowMeta(dj.Manual):
    """Provenance for one ``Session`` row."""

    definition = "-> Session" + _Base.ROW_META_ATTRS


@schema
class SubjectRowMeta(dj.Manual):
    """Provenance for one ``Subject`` row."""

    definition = "-> Subject" + _Base.ROW_META_ATTRS


@schema
class LabRowMeta(dj.Manual):
    """Provenance for one ``Lab`` row."""

    definition = "-> Lab" + _Base.ROW_META_ATTRS


@schema
class TaskRowMeta(dj.Manual):
    """Provenance for one ``Task`` row."""

    definition = "-> Task" + _Base.ROW_META_ATTRS
