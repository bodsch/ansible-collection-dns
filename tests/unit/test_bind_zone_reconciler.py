"""Unit tests for bind_zone dynamic/static reconciliation behavior."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_bind_zone_module(module_name: str):
    """Load a bind_zone module from this workspace without installation."""
    repo_root = Path(__file__).resolve().parents[2]
    bind_zone_dir = repo_root / "plugins" / "module_utils" / "bind_zone"

    package_name = "bind_zone"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(bind_zone_dir)]
        sys.modules[package_name] = package

    full_name = f"{package_name}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = bind_zone_dir / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_marks_dynamic_zone_files() -> None:
    builder_mod = _load_bind_zone_module("builder")

    builder = builder_mod.ZoneSpecBuilder()
    result = builder.build(
        [
            {
                "name": "dynamic.example",
                "type": "primary",
                "allow_updates": ["10.0.1.2"],
                "name_servers": ["ns1.dynamic.example."],
                "hosts": [{"name": "ns1", "ip": "10.0.1.10"}],
            },
            {
                "name": "static.example",
                "type": "primary",
                "name_servers": ["ns1.static.example."],
                "hosts": [{"name": "ns1", "ip": "10.0.2.10"}],
            },
        ]
    )

    zone_by_name = {item.source_zone_name: item for item in result.zone_files}
    assert zone_by_name["dynamic.example"].dynamic_updates is True
    assert zone_by_name["static.example"].dynamic_updates is False


def test_builder_marks_update_policy_zone_files_as_dynamic() -> None:
    builder_mod = _load_bind_zone_module("builder")

    result = builder_mod.ZoneSpecBuilder().build(
        [
            {
                "name": "dynamic.example",
                "type": "primary",
                "update_policy": {"mode": "local"},
                "name_servers": ["ns1.dynamic.example."],
                "hosts": [{"name": "ns1", "ip": "10.0.1.10"}],
            }
        ]
    )

    assert all(zone_file.dynamic_updates for zone_file in result.zone_files)


def test_reconciler_keeps_existing_dynamic_zone_file(tmp_path: Path) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    zone_file = zone_dir / "dynamic.example"
    original_content = "ORIGINAL_DYNAMIC_CONTENT\n"
    zone_file.write_text(original_content, encoding="utf-8")

    spec = models_mod.ZoneFileSpec(
        key="forward:dynamic.example",
        source_zone_name="dynamic.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="dynamic.example",
        origin="dynamic.example.",
        dynamic_updates=True,
        records=(),
    )

    reconciler = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    )

    first = reconciler.reconcile((spec,))
    assert first.changes[0].action == "unchanged"
    assert zone_file.read_text(encoding="utf-8") == original_content

    second = reconciler.reconcile((spec,))
    assert second.changed is False
    assert second.changes[0].action == "unchanged"
    assert zone_file.read_text(encoding="utf-8") == original_content


def test_reconciler_creates_missing_dynamic_zone_file(tmp_path: Path) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    spec = models_mod.ZoneFileSpec(
        key="forward:dynamic.example",
        source_zone_name="dynamic.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="dynamic.example",
        origin="dynamic.example.",
        dynamic_updates=True,
        records=(
            models_mod.ZoneRecord(
                owner="@",
                rtype="NS",
                value="ns1.dynamic.example.",
            ),
        ),
    )

    reconciler = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    )

    result = reconciler.reconcile((spec,))
    assert result.changed is True
    assert result.changes[0].action == "created"
    assert (zone_dir / "dynamic.example").exists()


def test_reconciler_does_not_manage_journal_files(tmp_path: Path) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    zone_file = zone_dir / "static.example"
    journal_file = zone_dir / "static.example.jnl"
    zone_file.write_text("OLD STATIC CONTENT\n", encoding="utf-8")
    journal_file.write_text("BIND-OWNED JOURNAL\n", encoding="utf-8")

    spec = models_mod.ZoneFileSpec(
        key="forward:static.example",
        source_zone_name="static.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="static.example",
        origin="static.example.",
        records=(
            models_mod.ZoneRecord(
                owner="@",
                rtype="NS",
                value="ns1.static.example.",
            ),
        ),
    )

    result = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    ).reconcile((spec,))

    assert result.changes[0].action == "updated"
    assert journal_file.read_text(encoding="utf-8") == "BIND-OWNED JOURNAL\n"


def test_reconciler_drops_ddns_records_when_zone_becomes_static(
    tmp_path: Path,
) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    zone_file = zone_dir / "transition.example"
    journal_file = zone_dir / "transition.example.jnl"
    zone_file.write_text(
        "DECLARED AND DDNS RECORDS\n",
        encoding="utf-8",
    )
    journal_file.write_text("DDNS JOURNAL\n", encoding="utf-8")

    dynamic_spec = models_mod.ZoneFileSpec(
        key="forward:transition.example",
        source_zone_name="transition.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="transition.example",
        origin="transition.example.",
        dynamic_updates=True,
        records=(),
    )
    static_spec = models_mod.ZoneFileSpec(
        key="forward:transition.example",
        source_zone_name="transition.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="transition.example",
        origin="transition.example.",
        records=(
            models_mod.ZoneRecord(
                owner="@",
                rtype="NS",
                value="ns1.transition.example.",
            ),
            models_mod.ZoneRecord(
                owner="ns1",
                rtype="A",
                value="192.0.2.53",
            ),
        ),
    )

    reconciler = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    )
    reconciler.reconcile((dynamic_spec,))

    plan = reconciler.reconcile((static_spec,), check_mode=True)
    assert plan.dynamic_to_static_zones == ("transition.example",)
    assert journal_file.exists() is True

    result = reconciler.reconcile((static_spec,))

    rendered = zone_file.read_text(encoding="utf-8")
    assert result.dynamic_to_static_zones == ("transition.example",)
    assert result.changes[0].action == "updated"
    assert "DECLARED AND DDNS RECORDS" not in rendered
    assert "192.0.2.53" in rendered
    assert journal_file.exists() is False


def test_reconciler_does_not_transition_reassigned_reverse_zone(
    tmp_path: Path,
) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    zone_file = zone_dir / "3.168.192.in-addr.arpa"
    journal_file = zone_dir / "3.168.192.in-addr.arpa.jnl"
    zone_file.write_text("EXISTING REVERSE ZONE\n", encoding="utf-8")
    journal_file.write_text("JOURNAL FROM UNKNOWN LIVE STATE\n", encoding="utf-8")

    cached_dynamic_spec = models_mod.ZoneFileSpec(
        key="reverse:ipv4:192.168.3.0/24",
        source_zone_name="ddns.example",
        state="present",
        zone_type="primary",
        kind="reverse",
        family="ipv4",
        filename="3.168.192.in-addr.arpa",
        origin="3.168.192.in-addr.arpa.",
        network="192.168.3.0/24",
        dynamic_updates=True,
        records=(),
    )
    desired_static_spec = models_mod.ZoneFileSpec(
        key="reverse:ipv4:192.168.3.0/24",
        source_zone_name="infra.example",
        state="present",
        zone_type="primary",
        kind="reverse",
        family="ipv4",
        filename="3.168.192.in-addr.arpa",
        origin="3.168.192.in-addr.arpa.",
        network="192.168.3.0/24",
        records=(
            models_mod.ZoneRecord(
                owner="@",
                rtype="NS",
                value="ns1.infra.example.",
            ),
            models_mod.ZoneRecord(
                owner="1",
                rtype="PTR",
                value="router.infra.example.",
            ),
        ),
    )

    reconciler = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    )
    reconciler.reconcile((cached_dynamic_spec,))

    plan = reconciler.reconcile((desired_static_spec,), check_mode=True)

    assert plan.dynamic_to_static_zones == ()
    assert journal_file.read_text(encoding="utf-8") == (
        "JOURNAL FROM UNKNOWN LIVE STATE\n"
    )


def test_reconciler_keeps_journal_for_dynamic_zone(tmp_path: Path) -> None:
    models_mod = _load_bind_zone_module("models")
    reconciler_mod = _load_bind_zone_module("reconciler")

    zone_dir = tmp_path / "zones"
    cache_dir = tmp_path / "cache"
    zone_dir.mkdir()
    cache_dir.mkdir()

    zone_file = zone_dir / "dynamic.example"
    journal_file = zone_dir / "dynamic.example.jnl"
    zone_file.write_text("DYNAMIC\n", encoding="utf-8")
    journal_file.write_text("journal", encoding="utf-8")

    spec = models_mod.ZoneFileSpec(
        key="forward:dynamic.example",
        source_zone_name="dynamic.example",
        state="present",
        zone_type="primary",
        kind="forward",
        family="none",
        filename="dynamic.example",
        origin="dynamic.example.",
        dynamic_updates=True,
        records=(),
    )

    reconciler = reconciler_mod.ZoneFileReconciler(
        zone_directory=str(zone_dir),
        cache_directory=str(cache_dir),
    )

    result = reconciler.reconcile((spec,))
    assert result.changes[0].action == "unchanged"
    assert journal_file.exists() is True
