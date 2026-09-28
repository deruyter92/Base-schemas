"""Write row-level provenance for a master table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeVar

import datajoint as dj

from base_schemas.core.hash import content_hash
from base_schemas.core.types import DjKey
from base_schemas.ingestion.provenance.ingestion_version import SCENE_WRITER_VERSION
from base_schemas.schemas.provenance.deployment import Deployment

MasterTable = TypeVar("MasterTable", bound=dj.Manual)
MetaTable = TypeVar("MetaTable", bound=dj.Manual)


def insert_row_meta(
    row_key: DjKey[MasterTable],
    row_meta_table: MetaTable,
    *,
    payload: dict[str, Any],
    deployment_key: DjKey[Deployment],
    writer_version: str | None = None,
    replace: bool = False,
    skip_duplicates: bool = False,
) -> DjKey[MasterTable]:
    """Insert a row-meta row for a master row.

    Args:
        row_key: Primary key of the master row.
        row_meta_table: Row-meta table to insert.
        payload: Fields hashed into ``content_hash``.
        deployment_key: Deployment primary key.
        writer_version: ``SCENE_WRITER_VERSION`` when omitted.
        replace: Forwarded to DataJoint ``insert1``.
        skip_duplicates: Forwarded to DataJoint ``insert1``.

    Returns:
        ``row_key``.
    """
    row_meta_table.insert1(
        {
            **row_key,
            **deployment_key,
            "ingestion_version": writer_version or SCENE_WRITER_VERSION,
            "content_hash": content_hash(payload),
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        },
        replace=replace,
        skip_duplicates=skip_duplicates,
    )
    return row_key
