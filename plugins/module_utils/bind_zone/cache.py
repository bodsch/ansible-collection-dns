"""JSON cache helpers for managed BIND zone files."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ZoneFileCacheEntry, ZoneFileSpec

_CACHE_FILE_VERSION = 1
_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class ZoneFileCacheError(OSError):
    """Raised when a zone cache entry cannot be read or written."""


class ZoneFileCacheStore:
    """Persist and discover zone file cache entries."""

    def __init__(self, cache_directory: str) -> None:
        """Initialize the cache store."""
        self._cache_directory = Path(cache_directory)

    @property
    def cache_directory(self) -> Path:
        """Return the configured cache directory."""
        return self._cache_directory

    def ensure_directory(self) -> None:
        """Ensure the cache directory exists."""
        self._cache_directory.mkdir(parents=True, exist_ok=True)

    def write(self, spec: ZoneFileSpec, *, content_sha256: str | None = None) -> Path:
        """Write one cache entry for a managed zone file."""
        self.ensure_directory()
        entry = ZoneFileCacheEntry(
            key=spec.key,
            filename=spec.filename,
            source_zone_name=spec.source_zone_name,
            state=spec.state,
            kind=spec.kind,
            family=spec.family,
            network=spec.network,
            content_sha256=content_sha256,
        )
        payload = {
            "version": _CACHE_FILE_VERSION,
            "entry": asdict(entry),
        }
        path = self.cache_path_for_key(spec.key, filename=spec.filename)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    def remove(self, key: str, *, filename: str | None = None) -> bool:
        """Remove the cache file for one key."""
        path = self.cache_path_for_key(key, filename=filename)
        if not path.exists():
            return False
        path.unlink()
        return True

    def read_all(self) -> dict[str, ZoneFileCacheEntry]:
        """Read all valid cache entries keyed by logical zone key."""
        if not self._cache_directory.exists():
            return {}

        entries: dict[str, ZoneFileCacheEntry] = {}
        for path in sorted(self._cache_directory.glob("*.json")):
            payload = self._read_payload(path)
            if payload is None:
                continue
            entry_payload = payload.get("entry", {})
            try:
                entry = ZoneFileCacheEntry(**entry_payload)
            except TypeError as exc:
                raise ZoneFileCacheError(
                    f"Invalid cache payload in {path!s}: {exc}"
                ) from exc
            entries[entry.key] = entry
        return entries

    def cache_path_for_key(self, key: str, *, filename: str | None = None) -> Path:
        """Return the deterministic cache file path for one logical key."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        slug_source = filename or key
        slug = _SAFE_FILENAME_PATTERN.sub("_", slug_source).strip("._") or "zone"
        return self._cache_directory / f"{slug}-{digest}.json"

    def _read_payload(self, path: Path) -> dict[str, Any] | None:
        """Read one cache payload or return None for unreadable JSON files."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ZoneFileCacheError(
                f"Invalid JSON cache file {path!s}: {exc}"
            ) from exc
        except OSError as exc:
            raise ZoneFileCacheError(
                f"Failed to read cache file {path!s}: {exc}"
            ) from exc
