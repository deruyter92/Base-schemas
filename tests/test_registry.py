"""Unit tests for SchemaRegistry / activate_schema (no database)."""

import base_schemas.core.registry as registry_mod
import pytest
from base_schemas.core import SCENE_REGISTRY, SchemaRegistry


@pytest.fixture
def registry():
    """Isolated registry so tests do not touch SCENE_REGISTRY."""
    return SchemaRegistry(name="test")


class FakeSchema:
    """Minimal stand-in for dj.Schema (activate records name + kwargs)."""

    def __init__(self):
        self.database = None
        self.kwargs = None
        self.calls = 0

    def activate(self, name, **kwargs):
        self.database = name
        self.kwargs = kwargs
        self.calls += 1


def test_make_schema_lazy_by_default(monkeypatch, registry):
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setenv("DJ_SCHEMA_PREFIX", "ignored_until_activate_")
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)
    schema = registry.make_schema("experiment")
    assert schema.database is None
    assert schema.calls == 0


def test_make_schema_eager_when_auto_activate(monkeypatch, registry):
    monkeypatch.setenv("AUTO_ACTIVATE", "1")
    monkeypatch.setenv("DJ_SCHEMA_PREFIX", "unit_")
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    schema = registry.make_schema("exp", create_tables=False)
    assert schema.database == "unit_exp"
    assert schema.kwargs == {"create_tables": False}  # no add_objects: FKs resolve via imports


def test_make_schema_rejects_empty_suffix(registry):
    with pytest.raises(ValueError, match="non-empty"):
        registry.make_schema("")


def test_make_schema_reuses_same_suffix(monkeypatch, registry):
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    first = registry.make_schema("experiment", create_tables=False)
    assert registry.make_schema("experiment") is first
    assert registry.make_schema("experiment", create_tables=False) is first
    assert list(registry.schemas) == ["experiment"]
    assert registry.get("experiment") is first


def test_make_schema_rejects_conflicting_create_tables(monkeypatch, registry):
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    registry.make_schema("experiment", create_tables=False)
    with pytest.raises(ValueError, match="create_tables=False"):
        registry.make_schema("experiment", create_tables=True)


def test_registry_inspection(monkeypatch, registry):
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    schema = registry.make_schema("experiment")
    assert "experiment" in registry.schemas
    assert "missing" not in registry.schemas
    assert registry.get("missing") is None
    assert registry.schemas == {"experiment": schema}
    # Snapshot: mutating the returned dict does not alter the registry.
    registry.schemas["experiment"] = FakeSchema()
    assert registry.get("experiment") is schema


def test_activate_uses_registered_suffix_and_create_tables(monkeypatch, registry):
    monkeypatch.setenv("DJ_SCHEMA_PREFIX", "dev_")
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    schema = registry.make_schema("experiment", create_tables=False)
    registry.activate("experiment")
    assert schema.database == "dev_experiment"
    assert schema.kwargs["create_tables"] is False


def test_activate_unknown_suffix_raises(registry):
    with pytest.raises(KeyError, match="unknown schema"):
        registry.activate("experiment")


def test_activate_schema_binds_any_schema(monkeypatch):
    monkeypatch.setenv("DJ_SCHEMA_PREFIX", "dev_")
    schema = FakeSchema()
    registry_mod.activate_schema(schema, "experiment", create_tables=False)
    assert schema.database == "dev_experiment"
    assert schema.kwargs["create_tables"] is False


def test_activate_schema_rejects_empty_suffix():
    with pytest.raises(ValueError, match="non-empty"):
        registry_mod.activate_schema(FakeSchema(), "")


def test_activate_all_binds_unbound_only(monkeypatch, registry):
    monkeypatch.setenv("DJ_SCHEMA_PREFIX", "dev_")
    monkeypatch.delenv("AUTO_ACTIVATE", raising=False)
    monkeypatch.setattr(registry_mod.dj, "Schema", FakeSchema)

    a = registry.make_schema("a")
    b = registry.make_schema("b")
    a.database = "already_bound"
    registry.activate_all()
    assert a.calls == 0
    assert b.database == "dev_b"
    assert b.calls == 1


def test_scene_registry_exported():
    assert SCENE_REGISTRY is registry_mod.SCENE_REGISTRY
    assert isinstance(SCENE_REGISTRY, SchemaRegistry)
    assert SCENE_REGISTRY.name == "scene"
