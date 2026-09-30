"""Write a tracked row together with its row-level provenance stamp."""

from __future__ import annotations

import enum
import warnings
from datetime import datetime, timezone
from typing import Any

from base_schemas.core.db import atomic
from base_schemas.core.hash import content_hash
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.ingestion_version import SCENE_WRITER_VERSION
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import RowMetaBase


class DuplicatePolicy(str, enum.Enum):
    """What to do when the tracked row's primary key is already stored.

    DataJoint's ``skip_duplicates`` / ``replace`` flags only look at the primary
    key. This policy also compares the ``content_hash`` stored in the row-meta
    stamp, so callers can detect a re-registration with different content.

    Attributes:
        REJECT: Raise ``ValueError``.
        SKIP: Leave the stored row and its stamp untouched.
        VERIFY: Leave the stored row untouched when the stamp hash matches
            ``payload``; raise ``ValueError`` when it differs or no stamp exists.
        UPDATE: Update the row and its stamp; warn when the hash changed.
    """

    REJECT = "reject"
    SKIP = "skip"
    VERIFY = "verify"
    UPDATE = "update"


def insert_tracked_row(
    row_meta_table: type[RowMetaBase],
    row: DjRow,
    *,
    payload: dict[str, Any],
    deployment: DjRow[Deployment],
    if_exists: DuplicatePolicy,
    writer_version: str | None = None,
) -> DjKey:
    """Insert ``row`` into ``row_meta_table.tracked_table`` and stamp it.

    A new primary key is inserted and stamped. An existing primary key is
    handled by ``if_exists``. The ``Deployment`` row is inserted when missing.
    All statements run atomically: inside the caller's open transaction when
    there is one, otherwise in a transaction opened here.

    Args:
        row_meta_table: Row-meta table; its ``tracked_table`` receives ``row``.
        row: Full insert dict for the tracked table.
        payload: Fields hashed into ``content_hash`` (caller-defined shape).
        deployment: Deployment row to stamp with.
        if_exists: Policy when the tracked primary key already exists.
        writer_version: Stamped ``ingestion_version``; ``SCENE_WRITER_VERSION``
            when omitted.

    Returns:
        Primary key of the tracked row.

    Raises:
        ValueError: When ``if_exists`` rejects the existing row.
    """
    tracked_table = row_meta_table.tracked_table
    row_key = row_meta_table.tracked_key(row)
    stamp = {
        **row_key,
        **{name: deployment[name] for name in Deployment.primary_key},
        "ingestion_version": writer_version or SCENE_WRITER_VERSION,
        "content_hash": content_hash(payload),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }

    with atomic(tracked_table.connection):
        if not (tracked_table & row_key):
            Deployment.insert1(deployment, skip_duplicates=True)
            tracked_table.insert1(row)
            row_meta_table.insert1(stamp)
            return row_key

        stored_hash = _stored_hash(row_meta_table, row_key)
        overwrite = _resolve_duplicate(
            if_exists,
            label=f"{tracked_table.__name__} row {row_key}",
            stored_hash=stored_hash,
            new_hash=stamp["content_hash"],
        )
        if not overwrite:
            return row_key

        Deployment.insert1(deployment, skip_duplicates=True)
        tracked_table.update1(row)
        if stored_hash is None:
            row_meta_table.insert1(stamp)
        else:
            row_meta_table.update1(stamp)
        return row_key


def _stored_hash(row_meta_table: type[RowMetaBase], row_key: DjKey) -> str | None:
    """Return the stamped ``content_hash`` for ``row_key``, or None when unstamped."""
    stamp = row_meta_table & row_key
    return stamp.fetch1("content_hash") if stamp else None


def _resolve_duplicate(
    if_exists: DuplicatePolicy,
    *,
    label: str,
    stored_hash: str | None,
    new_hash: str,
) -> bool:
    """Apply ``if_exists`` to an existing tracked row; return whether to overwrite."""
    if if_exists is DuplicatePolicy.REJECT:
        raise ValueError(f"{label} is already registered")
    if if_exists is DuplicatePolicy.SKIP:
        return False
    if if_exists is DuplicatePolicy.VERIFY:
        if stored_hash is None:
            raise ValueError(f"{label} has no provenance stamp to verify against")
        if stored_hash != new_hash:
            raise ValueError(f"{label} is already registered with a different content hash")
        return False
    if if_exists is DuplicatePolicy.UPDATE:
        if stored_hash is not None and stored_hash != new_hash:
            # stacklevel: warn -> here -> insert_tracked_row -> helper -> caller
            warnings.warn(f"{label} content hash changed; updating", UserWarning, stacklevel=4)
        return True
    raise ValueError(f"unknown DuplicatePolicy {if_exists!r}")
