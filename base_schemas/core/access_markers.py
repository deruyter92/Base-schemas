"""Intent markers for SCENE tables: sync authority and write role.

Markers enforce nothing. Deploy tooling turns a write role into MySQL grants;
sync tooling (not written yet) turns a sync authority into a conflict rule.
Read them with ``sync_authority_of`` / ``write_role_of``.

``SyncAuthority`` names which database holds the truth for a row:

- ``CENTRAL``: the central database (consortium catalogs such as ``Lab``).
  Site -> central verifies and central wins; central -> site overwrites.
- ``ORIGIN``: the site that acquired the data (subjects, sessions). The site's
  copy wins; central does not write these tables (enforced by grants, see
  ``WriteRole``). The row's provenance stamp records the last writer, not an
  owner.
- ``SHARED``: no owner; append-only identities (``Deployment``). Either
  direction inserts missing rows and never overwrites.

An unmarked table is ``ORIGIN``. A ``dj.Part`` follows its master, and a
row-meta table follows its ``tracked_table``.

``WriteRole`` restricts who may INSERT. ``ADMIN`` is a SCENE consortium
administrator; ``ACQUISITION`` is a lab's experimenter or acquisition pipeline,
and that marker admits no other role. No marker means unrestricted: admin,
acquisition, and any later role may write. The sync account is not a marker.
"""

from __future__ import annotations

import operator
import sys
from enum import Enum

import datajoint as dj


class SyncAuthority(str, Enum):
    """Which database holds the truth for a table's rows (see module docs)."""

    CENTRAL = "central"
    ORIGIN = "origin"
    SHARED = "shared"


class WriteRole(str, Enum):
    """Which kind of account may INSERT. Absent means unrestricted (see module docs)."""

    ADMIN = "admin"
    ACQUISITION = "acquisition"


def mark_sync_authority(authority: SyncAuthority):
    """Class decorator declaring which database owns this table's rows."""

    def decorator(cls):
        cls._sync_authority = authority
        return cls

    return decorator


def mark_write_role(role: WriteRole):
    """Class decorator restricting INSERT to one kind of account."""

    def decorator(cls):
        cls._write_role = role
        return cls

    return decorator


def sync_authority_of(table: type) -> SyncAuthority:
    """Return the table's sync authority: its marker, its master's, or ``ORIGIN``."""
    return _resolve(table, "_sync_authority", SyncAuthority.ORIGIN)


def write_role_of(table: type) -> WriteRole | None:
    """Return the table's write role, or None when INSERT is unrestricted."""
    return _resolve(table, "_write_role", None)


def _resolve(table: type, attr: str, default):
    marker = getattr(table, attr, None)
    if marker is not None:
        return marker
    if issubclass(table, dj.Part):
        return _resolve(_master_of(table), attr, default)
    tracked = getattr(table, "tracked_table", None)
    if tracked is not None:
        return _resolve(tracked, attr, default)
    return default


def _master_of(part: type[dj.Part]) -> type:
    """Return the master of a Part; resolved by name while the schema is unbound."""
    if part._master is not None:
        return part._master
    master_path, _, _ = part.__qualname__.rpartition(".")
    return operator.attrgetter(master_path)(sys.modules[part.__module__])
