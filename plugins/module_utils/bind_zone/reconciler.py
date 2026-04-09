"""Reconcile persisted BIND zone files with canonical desired state."""

from __future__ import annotations

import hashlib
import os
import tempfile
# from dataclasses import asdict
from pathlib import Path
from typing import Any

from .cache import ZoneFileCacheStore
from .models import ReconcileResult, ZoneFileChange, ZoneFileSpec
from .reader import ZoneFileReader
from .renderer import ZoneFileRenderer
from .serials import SerialNumberService


class ZoneFileReconcileError(OSError):
    """Raised when a zone file cannot be reconciled."""


class ZoneFileReconciler:
    """Reconcile a batch of managed BIND zone files."""

    def __init__(
        self,
        *,
        zone_directory: str,
        cache_directory: str,
        reader: ZoneFileReader | None = None,
        renderer: ZoneFileRenderer | None = None,
        serial_service: SerialNumberService | None = None,
    ) -> None:
        """Initialize the reconciler."""
        self._zone_directory = Path(zone_directory)
        self._cache_store = ZoneFileCacheStore(cache_directory)
        self._reader = reader or ZoneFileReader()
        self._renderer = renderer or ZoneFileRenderer()
        self._serial_service = serial_service or SerialNumberService()

    def reconcile(
        self,
        zone_files: list[ZoneFileSpec] | tuple[ZoneFileSpec, ...],
        *,
        serial_strategy: str = "unix",
        purge: bool = True,
        check_mode: bool = False,
        file_mode: int | None = None,
        owner_uid: int | None = None,
        owner_gid: int | None = None,
        include_diff: bool = False,
        now: int | None = None,
    ) -> ReconcileResult:
        """Reconcile all desired zone files against persisted state."""
        self._zone_directory.mkdir(parents=True, exist_ok=True)
        self._cache_store.ensure_directory()

        desired_by_key = {zone_file.key: zone_file for zone_file in zone_files}
        cache_entries = self._cache_store.read_all()

        changes: list[ZoneFileChange] = []
        for zone_file in zone_files:
            changes.append(
                self._reconcile_one(
                    zone_file=zone_file,
                    serial_strategy=serial_strategy,
                    check_mode=check_mode,
                    file_mode=file_mode,
                    owner_uid=owner_uid,
                    owner_gid=owner_gid,
                    include_diff=include_diff,
                    now=now,
                )
            )

        if purge:
            stale_keys = sorted(set(cache_entries) - set(desired_by_key))
            for stale_key in stale_keys:
                changes.append(
                    self._purge_stale_entry(
                        stale_key=stale_key,
                        filename=cache_entries[stale_key].filename,
                        check_mode=check_mode,
                    )
                )

        changed = any(item.changed for item in changes)
        return ReconcileResult(changed=changed, changes=tuple(changes))

    def _reconcile_one(
        self,
        *,
        zone_file: ZoneFileSpec,
        serial_strategy: str,
        check_mode: bool,
        file_mode: int | None,
        owner_uid: int | None,
        owner_gid: int | None,
        include_diff: bool,
        now: int | None,
    ) -> ZoneFileChange:
        """Reconcile one desired zone file."""
        target_path = self._zone_directory / zone_file.filename
        current_state = self._reader.read(str(target_path))

        if zone_file.state == "absent":
            removed = False
            if current_state.exists:
                removed = True
                if not check_mode:
                    target_path.unlink()
            cache_removed = (
                self._cache_store.remove(zone_file.key, filename=zone_file.filename)
                if not check_mode
                else self._cache_store.cache_path_for_key(
                    zone_file.key, filename=zone_file.filename
                ).exists()
            )
            changed = removed or bool(cache_removed)
            return ZoneFileChange(
                key=zone_file.key,
                filename=zone_file.filename,
                action="deleted" if changed else "unchanged",
                changed=changed,
                old_serial=current_state.serial,
                new_serial=None,
            )

        rendered_compare = self._renderer.normalize_rendered_content(
            self._renderer.render(zone_file=zone_file)
        )

        if current_state.exists and current_state.content == rendered_compare:
            content_sha256 = hashlib.sha256(
                rendered_compare.encode("utf-8")
            ).hexdigest()
            cache_path = self._cache_store.cache_path_for_key(
                zone_file.key, filename=zone_file.filename
            )
            if not check_mode:
                self._cache_store.write(zone_file, content_sha256=content_sha256)
            cache_missing = not cache_path.exists()
            return ZoneFileChange(
                key=zone_file.key,
                filename=zone_file.filename,
                action="unchanged",
                changed=cache_missing and not check_mode,
                old_serial=current_state.serial,
                new_serial=current_state.serial,
            )

        action = "created" if not current_state.exists else "updated"
        next_serial = self._serial_service.next_serial(
            current_state.serial,
            strategy=serial_strategy,
            now=now,
        )
        rendered_final = self._renderer.normalize_rendered_content(
            self._renderer.render(zone_file=zone_file, serial=next_serial)
        )

        if not check_mode:
            self._atomic_write(
                path=target_path,
                content=rendered_final,
                file_mode=file_mode,
                owner_uid=owner_uid,
                owner_gid=owner_gid,
            )
            self._cache_store.write(
                zone_file,
                content_sha256=hashlib.sha256(
                    rendered_compare.encode("utf-8")
                ).hexdigest(),
            )

        return ZoneFileChange(
            key=zone_file.key,
            filename=zone_file.filename,
            action=action,
            changed=True,
            old_serial=current_state.serial,
            new_serial=next_serial,
            diff_before=current_state.content if include_diff else None,
            diff_after=rendered_compare if include_diff else None,
        )

    def _purge_stale_entry(
        self,
        *,
        stale_key: str,
        filename: str,
        check_mode: bool,
    ) -> ZoneFileChange:
        """Remove a file that is still tracked in cache but no longer desired."""
        target_path = self._zone_directory / filename
        current_state = self._reader.read(str(target_path))
        changed = current_state.exists

        if current_state.exists and not check_mode:
            target_path.unlink()

        cache_path = self._cache_store.cache_path_for_key(stale_key, filename=filename)
        if cache_path.exists():
            changed = True
            if not check_mode:
                cache_path.unlink()

        return ZoneFileChange(
            key=stale_key,
            filename=filename,
            action="deleted" if changed else "unchanged",
            changed=changed,
            old_serial=current_state.serial,
            new_serial=None,
        )

    def _atomic_write(
        self,
        *,
        path: Path,
        content: str,
        file_mode: int | None,
        owner_uid: int | None,
        owner_gid: int | None,
    ) -> None:
        """Write one file atomically."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                delete=False,
            ) as handle:
                handle.write(content)
                temp_file = Path(handle.name)

            if file_mode is not None:
                os.chmod(temp_file, file_mode)
            if owner_uid is not None or owner_gid is not None:
                os.chown(
                    temp_file,
                    -1 if owner_uid is None else owner_uid,
                    -1 if owner_gid is None else owner_gid,
                )

            os.replace(temp_file, path)
        except OSError as exc:
            raise ZoneFileReconcileError(
                f"Failed to write zone file {path!s}: {exc}"
            ) from exc
        finally:
            if temp_file is not None and temp_file.exists():
                temp_file.unlink(missing_ok=True)


def reconcile_zone_files(**kwargs: Any) -> ReconcileResult:
    """Reconcile zone files via the public API."""
    reconciler = ZoneFileReconciler(
        zone_directory=kwargs.pop("zone_directory"),
        cache_directory=kwargs.pop("cache_directory"),
    )
    return reconciler.reconcile(**kwargs)
