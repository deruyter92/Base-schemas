"""Row-level write provenance for tracked tables."""

from __future__ import annotations

from typing import ClassVar

import datajoint as dj

from base_schemas.core.types import DjKey, DjRow
from base_schemas.schemas.provenance._schema import schema
from base_schemas.schemas.provenance.deployment import Deployment  # noqa: F401
from base_schemas.schemas.scene.lab import Lab
from base_schemas.schemas.scene.session import Session
from base_schemas.schemas.scene.subject import Subject
from base_schemas.schemas.scene.task import Task


# do not use this base class directly (no @schema decorator)
class RowMetaBase(dj.Manual):
    """Base class for row-level provenance tables."""

    tracked_table: ClassVar[type[dj.Manual]]

    ROW_META_ATTRS = """
    ---
    -> Deployment
    ingestion_version: varchar(32)
    content_hash: char(64)
    updated_at: datetime
    """

    @classmethod
    def tracked_key(cls, row: DjRow) -> DjKey:
        """Extract the tracked table's primary key."""
        return {name: row[name] for name in cls.tracked_table.primary_key}

    @classmethod
    def build_definition(cls, tracked_table: type[dj.Manual]) -> str:
        """Build the definition for the row-meta table."""
        return f"-> {tracked_table.__name__}{cls.ROW_META_ATTRS}"


@schema
class SessionRowMeta(RowMetaBase):
    """Provenance for one ``Session`` row."""

    tracked_table = Session
    definition = RowMetaBase.build_definition(tracked_table)


@schema
class SubjectRowMeta(RowMetaBase):
    """Provenance for one ``Subject`` row."""

    tracked_table = Subject
    definition = RowMetaBase.build_definition(tracked_table)


@schema
class LabRowMeta(RowMetaBase):
    """Provenance for one ``Lab`` row."""

    tracked_table = Lab
    definition = RowMetaBase.build_definition(tracked_table)


@schema
class TaskRowMeta(RowMetaBase):
    """Provenance for one ``Task`` row."""

    tracked_table = Task
    definition = RowMetaBase.build_definition(tracked_table)
