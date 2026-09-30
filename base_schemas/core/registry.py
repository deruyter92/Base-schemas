"""DataJoint schema registry with lazy-by-default activation.

Schemas created via ``SchemaRegistry.make_schema`` stay unbound unless
``AUTO_ACTIVATE`` is set. Bind later with ``activate`` / ``activate_all``, or
call ``activate_schema`` for any ``dj.Schema`` with an explicit suffix.

Foreign keys (``-> Lab``) resolve through the names imported in the module that
defines the table, as usual in DataJoint. The registry deliberately does not
inject extra names: shared tables must reference the shared tables, and labs
extend them by referencing them from their own schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import datajoint as dj

from base_schemas.core.config import load_settings


def activate_schema(
    schema: dj.Schema,
    suffix: str,
    *,
    create_tables: bool = True,
    connection: Any | None = None,
) -> dj.Schema:
    """Run DataJoint ``Schema.activate()`` with ``{DJ_SCHEMA_PREFIX}{suffix}``.

    Args:
        schema: Unbound (or rebound) ``dj.Schema`` instance.
        suffix: Logical schema name without prefix (e.g. ``"experiment"``).
        create_tables: Forwarded to ``schema.activate``.
        connection: Optional DataJoint connection forwarded to ``activate``.

    Returns:
        The same ``schema`` instance after activation.

    Raises:
        ValueError: If ``suffix`` is empty.
    """
    if not suffix:
        raise ValueError("schema suffix must be a non-empty string")

    name = load_settings().db_name(suffix)
    kwargs: dict[str, Any] = {"create_tables": create_tables}
    if connection is not None:
        kwargs["connection"] = connection
    schema.activate(name, **kwargs)
    return schema


@dataclass
class _Entry:
    """One registered schema and the defaults used when activating it."""

    schema: dj.Schema
    create_tables: bool = True


class SchemaRegistry:
    """Track schemas created via ``make_schema`` and bind them on demand.

    Lazy by default: ``make_schema`` returns an unbound ``dj.Schema`` but
    remembers the logical suffix (and ``create_tables``) so ``activate`` /
    ``activate_all`` can bind without re-stating the name. When
    ``AUTO_ACTIVATE`` is set, ``make_schema`` binds immediately.

    Entries are keyed by suffix: repeated ``make_schema`` calls with the same
    name return the existing instance; a conflicting ``create_tables`` raises. Inspect with
    ``get`` or the ``schemas`` property.

    Attributes:
        name: Label for this registry instance (e.g. ``"scene"``).
    """

    def __init__(self, name: str = "default") -> None:
        """Create an empty registry.

        Args:
            name: Human-readable label for this registry instance.
        """
        self.name = name
        self._entries: dict[str, _Entry] = {}

    @property
    def schemas(self) -> dict[str, dj.Schema]:
        """Snapshot map of suffix → ``dj.Schema`` (mutations do not affect the registry)."""
        return {suffix: entry.schema for suffix, entry in self._entries.items()}

    def get(self, suffix: str) -> dj.Schema | None:
        """Return the registered schema for ``suffix``, or ``None``."""
        entry = self._entries.get(suffix)
        return entry.schema if entry is not None else None

    def make_schema(
        self,
        suffix: str,
        *,
        create_tables: bool | None = None,
    ) -> dj.Schema:
        """Create a DataJoint schema, unbound unless ``AUTO_ACTIVATE`` is set.

        Repeated calls with the same ``suffix`` return the same instance. A
        repeated call that passes a different ``create_tables`` raises.

        Args:
            suffix: Logical name without prefix (e.g. ``"experiment"``).
            create_tables: Forwarded when activating; ``True`` when omitted.

        Returns:
            A ``dj.Schema`` instance (unbound unless ``AUTO_ACTIVATE``).

        Raises:
            ValueError: If ``suffix`` is empty, or a repeated call passes a
                ``create_tables`` that differs from the first registration.
        """
        if not suffix:
            raise ValueError("schema suffix must be a non-empty string")

        entry = self._entries.get(suffix)
        if entry is not None:
            if create_tables is not None and create_tables != entry.create_tables:
                raise ValueError(
                    f"schema {suffix!r} is already registered with "
                    f"create_tables={entry.create_tables}"
                )
            return entry.schema

        schema = dj.Schema()
        self._entries[suffix] = _Entry(
            schema=schema,
            create_tables=True if create_tables is None else create_tables,
        )
        if load_settings().auto_activate:
            return self.activate(suffix)
        return schema

    def activate(
        self,
        suffix: str,
        *,
        create_tables: bool | None = None,
        connection: Any | None = None,
    ) -> dj.Schema:
        """Bind a registered schema by suffix using ``activate_schema``.


        Args:
            suffix: Logical name without prefix (e.g. ``"experiment"``).
            create_tables: Forwarded to ``activate_schema``; defaults to the
                value stored at registration when omitted.
            connection: Optional DataJoint connection forwarded to activate.

        Returns:
            The registered ``dj.Schema`` instance after activation.

        Raises:
            KeyError: If ``suffix`` is not registered.
        """
        try:
            entry = self._entries[suffix]
        except KeyError as exc:
            raise KeyError(f"unknown schema {suffix!r}") from exc

        resolved_create = entry.create_tables if create_tables is None else create_tables
        return activate_schema(
            entry.schema,
            suffix,
            create_tables=resolved_create,
            connection=connection,
        )

    def activate_all(
        self,
        *,
        create_tables: bool | None = None,
        connection: Any | None = None,
    ) -> None:
        """Activate every registered schema that is still unbound.

        Skips schemas that already have a ``database`` set. Per-schema
        ``create_tables`` from ``make_schema`` is used unless overridden here.

        Args:
            create_tables: Shared create-tables flag. When omitted, each entry
                uses the value stored at registration.
            connection: Optional DataJoint connection forwarded to each
                ``activate`` call.
        """
        for suffix, entry in list(self._entries.items()):
            if getattr(entry.schema, "database", None):
                continue
            self.activate(
                suffix,
                create_tables=create_tables,
                connection=connection,
            )


# Process-wide registry for package schemas and consumers.
SCENE_REGISTRY = SchemaRegistry(name="scene")
