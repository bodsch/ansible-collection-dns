"""Serial number helpers for BIND zone reconciliation."""

from __future__ import annotations

import time
from typing import Literal

SerialStrategy = Literal["unix", "increment"]


class SerialStrategyError(ValueError):
    """Raised when a serial strategy is invalid."""


class SerialNumberService:
    """Compute the next SOA serial number for a zone file."""

    def next_serial(
        self,
        old_serial: int | None,
        *,
        strategy: SerialStrategy = "unix",
        now: int | None = None,
    ) -> int:
        """Return the next serial number.

        Args:
            old_serial: Current persisted serial number.
            strategy: Serial strategy name.
            now: Optional fixed current unix timestamp for testing.

        Returns:
            The next serial number.

        Raises:
            SerialStrategyError: If the strategy is invalid.
        """
        normalized_strategy = str(strategy).strip().lower()
        if normalized_strategy == "unix":
            return self._next_unix_serial(old_serial=old_serial, now=now)
        if normalized_strategy == "increment":
            return self._next_increment_serial(old_serial=old_serial)

        raise SerialStrategyError(
            f"Unsupported serial strategy: {strategy!r}. Allowed values are 'unix' and 'increment'."
        )

    def _next_unix_serial(self, old_serial: int | None, now: int | None = None) -> int:
        """Return a monotonic unix timestamp serial."""
        current = int(time.time()) if now is None else int(now)
        if old_serial is None:
            return current
        return max(current, old_serial + 1)

    def _next_increment_serial(self, old_serial: int | None) -> int:
        """Return a strictly incremented serial."""
        if old_serial is None:
            return 1
        return int(old_serial) + 1
