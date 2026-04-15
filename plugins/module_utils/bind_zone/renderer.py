"""Deterministic BIND zone file renderer.

This module renders canonical ``ZoneFileSpec`` objects into zone file content
that can later be compared against persisted files independent of the current
SOA serial.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .models import ZoneFileSpec, ZoneRecord

SERIAL_PLACEHOLDER = "__SERIAL__"

_RECORD_TYPE_ORDER: dict[str, int] = {
    "NS": 10,
    "MX": 20,
    "A": 30,
    "AAAA": 40,
    "CNAME": 50,
    "SRV": 60,
    "TXT": 70,
    "PTR": 80,
}


class ZoneRenderError(ValueError):
    """Raised when a zone file spec cannot be rendered."""


class ZoneFileRenderer:
    """Render canonical BIND zone file specifications."""

    def __init__(
        self,
        *,
        refresh: int = 86400,
        retry: int = 7200,
        expire: int = 3600000,
        minimum: int = 86400,
        hostmaster_label: str = "hostmaster",
    ) -> None:
        """Initialize the renderer.

        Args:
            refresh: SOA refresh interval in seconds.
            retry: SOA retry interval in seconds.
            expire: SOA expiry interval in seconds.
            minimum: SOA minimum TTL in seconds.
            hostmaster_label: Left-hand label used for the RNAME mailbox.
        """
        self._refresh = refresh
        self._retry = retry
        self._expire = expire
        self._minimum = minimum
        self._hostmaster_label = hostmaster_label

    def render(
        self,
        zone_file: ZoneFileSpec,
        *,
        serial: int | str = SERIAL_PLACEHOLDER,
    ) -> str:
        """Render one zone file.

        Args:
            zone_file: Canonical zone file spec.
            serial: SOA serial or placeholder.

        Returns:
            Deterministic BIND zone file content.

        Raises:
            ZoneRenderError: If the spec is incomplete.
        """
        if zone_file.state != "present":
            raise ZoneRenderError(
                f"Cannot render zone file {zone_file.filename!r} with state={zone_file.state!r}."
            )

        origin = self._ensure_trailing_dot(zone_file.origin)
        ns_targets = self._collect_apex_ns(zone_file.records)
        if not ns_targets:
            raise ZoneRenderError(
                f"Zone file {zone_file.filename!r} has no apex NS records."
            )

        soa_mname = self._ensure_trailing_dot(ns_targets[0])
        soa_rname = self._ensure_trailing_dot(
            f"{self._hostmaster_label}.{zone_file.source_zone_name}"
        )

        lines: list[str] = [
            f"$ORIGIN {origin}",
            f"$TTL {zone_file.default_ttl}",
            "",
            f"@ IN SOA {soa_mname} {soa_rname} (",
            f"    {serial} ; serial",
            f"    {self._refresh} ; refresh",
            f"    {self._retry} ; retry",
            f"    {self._expire} ; expire",
            f"    {self._minimum} ; minimum",
            ")",
            "",
        ]

        for record in self._sort_records(zone_file.records):
            lines.append(self._render_record(record))

        return "\n".join(lines).rstrip() + "\n"

    def normalize_rendered_content(self, content: str) -> str:
        """Normalize rendered content for stable comparisons.

        Args:
            content: Raw rendered or persisted content.

        Returns:
            A normalized string suitable for content comparison.
        """
        lines = [line.rstrip() for line in content.replace("\r\n", "\n").split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    def _collect_apex_ns(self, records: Sequence[ZoneRecord]) -> list[str]:
        """Collect apex NS record targets in original record order."""
        targets: list[str] = []
        seen: set[str] = set()

        for record in records:
            if record.owner != "@" or record.rtype != "NS":
                continue

            target = self._ensure_trailing_dot(record.value)
            if target in seen:
                continue

            seen.add(target)
            targets.append(target)

        return targets

    def _sort_records(self, records: Sequence[ZoneRecord]) -> list[ZoneRecord]:
        """Return records in deterministic rendering order."""
        return sorted(records, key=self._record_sort_key)

    def _record_sort_key(self, record: ZoneRecord) -> tuple[Any, ...]:
        """Build a stable sort key for one resource record."""
        return (
            self._owner_sort_key(record.owner),
            _RECORD_TYPE_ORDER.get(record.rtype, 999),
            record.owner,
            record.rtype,
            record.priority if record.priority is not None else -1,
            record.weight if record.weight is not None else -1,
            record.port if record.port is not None else -1,
            record.value,
        )

    def _owner_sort_key(self, owner: str) -> tuple[int, tuple[int | str, ...]]:
        """Return a stable owner ordering.

        The apex record owner is rendered first, followed by increasingly
        specific relative names.
        """
        if owner == "@":
            return (0, ())

        labels = owner.split(".")
        reversed_key: list[int | str] = [len(labels)]
        reversed_key.extend(reversed(labels))
        return (1, tuple(reversed_key))

    def _render_record(self, record: ZoneRecord) -> str:
        """Render one canonical record into BIND zone file syntax."""
        owner = record.owner

        if record.rtype in {"A", "AAAA", "NS", "CNAME", "PTR"}:
            return f"{owner} IN {record.rtype} {self._format_rdata_value(record)}"

        if record.rtype == "MX":
            if record.priority is None:
                raise ZoneRenderError(f"MX record {record!r} is missing priority.")
            return (
                f"{owner} IN MX {record.priority} "
                f"{self._format_rdata_value(record)}"
            )

        if record.rtype == "SRV":
            if record.priority is None or record.weight is None or record.port is None:
                raise ZoneRenderError(
                    f"SRV record {record!r} is missing required fields."
                )
            return (
                f"{owner} IN SRV {record.priority} {record.weight} {record.port} "
                f"{self._format_rdata_value(record)}"
            )

        if record.rtype == "TXT":
            return f"{owner} IN TXT {self._quote_txt_value(record.value)}"

        raise ZoneRenderError(f"Unsupported record type: {record.rtype!r}.")

    def _format_rdata_value(self, record: ZoneRecord) -> str:
        """Format the RDATA value for non-TXT records."""
        if record.rtype in {"NS", "CNAME", "PTR"}:
            return self._ensure_trailing_dot(record.value)
        return record.value

    def _quote_txt_value(self, value: str) -> str:
        """Render a TXT record value with BIND-compatible escaping."""
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _ensure_trailing_dot(self, value: str) -> str:
        """Ensure a DNS name ends with a trailing dot."""
        return value if value.endswith(".") else f"{value}."


class ZoneDefinitionRenderer:
    """Render canonical named.conf zone definitions."""

    def __init__(self, update_policy_renderer: Any | None = None) -> None:
        """Initialize the zone definition renderer.

        Args:
            update_policy_renderer: Optional update-policy renderer implementing
                ``render(policy, indent=str, level=int)``.
        """
        if update_policy_renderer is None:
            from .update_policy import UpdatePolicyRenderer

            update_policy_renderer = UpdatePolicyRenderer()

        self._update_policy_renderer = update_policy_renderer

    def render(
        self,
        zone_name: str,
        *,
        zone_type: str,
        filename: str | None,
        primaries: Sequence[str] = (),
        forwarders: Sequence[str] = (),
        update_policy: Any | None = None,
        indent: str = "    ",
    ) -> str:
        """Render one named.conf zone statement."""
        lines = [f'zone "{zone_name}" {{', f"{indent}type {zone_type};"]

        if zone_type == "primary":
            if not filename:
                raise ZoneRenderError(
                    f"Primary zone {zone_name!r} requires a filename for rendering."
                )
            lines.append(f'{indent}file "{filename}";')

        elif zone_type == "secondary":
            if not primaries:
                raise ZoneRenderError(
                    f"Secondary zone {zone_name!r} requires at least one primary."
                )

            lines.append(f"{indent}primaries {{")
            for primary in primaries:
                lines.append(f"{indent}{indent}{primary};")
            lines.append(f"{indent}}};")

            if filename:
                lines.append(f'{indent}file "{filename}";')

        elif zone_type == "forward":
            if not forwarders:
                raise ZoneRenderError(
                    f"Forward zone {zone_name!r} requires at least one forwarder."
                )

            lines.append(f"{indent}forwarders {{")
            for forwarder in forwarders:
                lines.append(f"{indent}{indent}{forwarder};")
            lines.append(f"{indent}}};")

        else:
            raise ZoneRenderError(f"Unsupported zone type: {zone_type!r}.")

        rendered_policy = self._update_policy_renderer.render(
            update_policy,
            indent=indent,
            level=1,
        )
        if rendered_policy:
            lines.append(rendered_policy)

        lines.append("};")
        return "\n".join(lines)

    def render_OLD(
        self,
        zone_name: str,
        *,
        zone_type: str,
        filename: str | None,
        primaries: Sequence[str] = (),
        update_policy: Any | None = None,
        indent: str = "    ",
    ) -> str:
        """Render one named.conf zone statement."""
        lines = [f'zone "{zone_name}" {{', f"{indent}type {zone_type};"]

        if zone_type == "primary":
            if not filename:
                raise ZoneRenderError(
                    f"Primary zone {zone_name!r} requires a filename for rendering."
                )
            lines.append(f'{indent}file "{filename}";')
        elif zone_type in {"secondary", "forward"}:
            if primaries:
                lines.append(f"{indent}primaries {{")
                for primary in primaries:
                    lines.append(f"{indent}{indent}{primary};")
                lines.append(f"{indent}}};")

            if filename:
                lines.append(f'{indent}file "{filename}";')

        rendered_policy = self._update_policy_renderer.render(
            update_policy,
            indent=indent,
            level=1,
        )
        if rendered_policy:
            lines.append(rendered_policy)

        lines.append("};")
        return "\n".join(lines)


def render_zone_file(
    zone_file: ZoneFileSpec, *, serial: int | str = SERIAL_PLACEHOLDER
) -> str:
    """Render one zone file via the public renderer API."""
    renderer = ZoneFileRenderer()
    return renderer.render(zone_file=zone_file, serial=serial)
