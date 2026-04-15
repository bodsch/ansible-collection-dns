"""Reader helpers for persisted BIND zone files."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Final

from .models import ZoneFileState
from .renderer import SERIAL_PLACEHOLDER

_SOA_SERIAL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?is)(\bSOA\b.*?\()(\s*)(?P<serial>[0-9]+)(\s*;\s*serial)"
)


class ZoneFileReadError(OSError):
    """Raised when a persisted zone file cannot be read or parsed."""


class ZoneFileReader:
    """Read persisted BIND zone files and normalize them for comparison."""

    def read(self, file_name: str) -> ZoneFileState:
        """Read one persisted zone file.

        Args:
            file_name: Absolute path to the zone file.

        Returns:
            The current persisted zone file state.

        Raises:
            ZoneFileReadError: If the file exists but cannot be read.
        """
        if not os.path.exists(file_name):
            return ZoneFileState(filename=file_name, exists=False)

        try:
            with open(file_name, "r", encoding="utf-8") as file_handle:
                content = file_handle.read()
        except OSError as exc:
            raise ZoneFileReadError(
                f"Failed to read zone file {file_name!r}: {exc}"
            ) from exc

        normalized_content = self.normalize_for_compare(content)
        serial = self.extract_serial(content)

        return ZoneFileState(
            filename=file_name,
            exists=True,
            serial=serial,
            sha256=self.sha256(normalized_content),
            content=normalized_content,
        )

    def extract_serial(self, content: str) -> int | None:
        """Extract the SOA serial from zone file content.

        Args:
            content: Raw zone file content.

        Returns:
            The parsed serial number or ``None`` if no SOA serial exists.
        """
        match = _SOA_SERIAL_PATTERN.search(content)
        if not match:
            return None

        return int(match.group("serial"))

    def normalize_for_compare(self, content: str) -> str:
        """Normalize zone file content for stable comparisons.

        The SOA serial is replaced with a placeholder so that content-based
        idempotence does not depend on the current serial value.
        """
        unix_newlines = content.replace("\r\n", "\n")
        normalized = _SOA_SERIAL_PATTERN.sub(
            rf"\1\2{SERIAL_PLACEHOLDER}\4",
            unix_newlines,
            count=1,
        )
        lines = [line.rstrip() for line in normalized.split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    def sha256(self, content: str) -> str:
        """Return the SHA-256 digest for normalized text content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_zone_file(file_name: str) -> ZoneFileState:
    """Read one zone file via the public reader API."""
    reader = ZoneFileReader()
    return reader.read(file_name)
