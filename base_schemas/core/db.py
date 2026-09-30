"""Small DataJoint helpers shared by the write paths (ids, transactions, key lookup)."""

from __future__ import annotations

import uuid
from contextlib import nullcontext

import datajoint as dj

from base_schemas.core.types import DjKey


def new_id() -> str:
    """Return a new opaque id for a minted primary key (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex


def atomic(connection: dj.Connection):
    """Open a transaction, or join the one already open (DataJoint cannot nest)."""
    return nullcontext() if connection.in_transaction else connection.transaction


def lookup_key(table: type[dj.Manual], restriction: DjKey) -> DjKey | None:
    """Return the primary key of the row matching ``restriction``, or None.

    ``restriction`` should cover a unique index (e.g. ``lab_id`` + a code), so
    at most one row matches.
    """
    match = table & restriction
    return match.fetch1("KEY") if match else None
