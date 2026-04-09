"""Canonical BIND zone builder.

This module transforms high-level ``bind_zones`` data into canonical internal
models that can later be rendered into named.conf statements and concrete zone
files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import Any

from .models import (
    ZoneBuildResult,
    ZoneDefinitionSpec,
    ZoneFileSpec,
    ZoneRecord,
)
from .update_policy import UpdatePolicyService


class ZoneBuilderError(ValueError):
    """Raised when raw bind zone input cannot be normalized."""


class ZoneSpecBuilder:
    """Build canonical BIND zone models from raw Ansible data."""

    def __init__(
        self,
        update_policy_service: UpdatePolicyService | None = None,
    ) -> None:
        """Initialize the builder.

        Args:
            update_policy_service: Optional update-policy normalization service.
        """
        self._update_policy_service = update_policy_service or UpdatePolicyService()

    def build(self, raw_zones: Any) -> ZoneBuildResult:
        """Build canonical zone definition and zone file models.

        Args:
            raw_zones: Raw ``bind_zones`` data from Ansible.

        Returns:
            A combined build result with zone definitions and zone files.

        Raises:
            ZoneBuilderError: If the raw input is invalid.
        """
        zones = self._normalize_zone_list(raw_zones)

        zone_definitions: list[ZoneDefinitionSpec] = []
        zone_files: list[ZoneFileSpec] = []

        for index, raw_zone in enumerate(zones):
            definitions, files = self._build_zone(raw_zone=raw_zone, index=index)
            zone_definitions.extend(definitions)
            zone_files.extend(files)

        return ZoneBuildResult(
            zone_definitions=tuple(zone_definitions),
            zone_files=tuple(zone_files),
        )

    def _build_zone(
        self,
        raw_zone: Mapping[str, Any],
        index: int,
    ) -> tuple[list[ZoneDefinitionSpec], list[ZoneFileSpec]]:
        """Build all canonical models for one logical zone."""
        zone_name = self._require_non_empty_string(
            raw_zone.get("name"),
            field_name=f"bind_zones[{index}].name",
        )
        zone_type = self._resolve_zone_type(
            raw_zone=raw_zone,
            field_name=f"bind_zones[{index}].type",
        )
        state = self._normalize_state(
            raw_zone.get("state", "present"),
            field_name=f"bind_zones[{index}].state",
        )
        create_forward_zones = self._normalize_bool(
            raw_zone.get("create_forward_zones", True)
        )
        create_reverse_zones = self._normalize_bool(
            raw_zone.get("create_reverse_zones", True)
        )
        primaries = self._normalize_string_list(raw_zone.get("primaries", ()))
        forwarders = self._normalize_string_list(raw_zone.get("forwarders", ()))

        if zone_type == "secondary" and not primaries:
            raise ZoneBuilderError(
                f"bind_zones[{index}] with type='secondary' requires 'primaries'."
            )

        if zone_type == "forward" and not forwarders:
            raise ZoneBuilderError(
                f"bind_zones[{index}] with type='forward' requires 'forwarders'."
            )

        update_policy = self._update_policy_service.normalize(
            raw_policy=raw_zone.get("update_policy"),
            zone_name=zone_name,
            zone_type=zone_type,
            allow_update_present=bool(raw_zone.get("allow_update")),
        )

        definitions: list[ZoneDefinitionSpec] = []
        files: list[ZoneFileSpec] = []

        if create_forward_zones:
            forward_filename = (
                zone_name if zone_type in {"primary", "secondary"} else None
            )
            definitions.append(
                ZoneDefinitionSpec(
                    name=zone_name,
                    zone_type=zone_type,
                    state=state,
                    filename=forward_filename,
                    primaries=tuple(primaries),
                    forwarders=tuple(forwarders),
                    update_policy=update_policy if zone_type == "primary" else None,
                )
            )

            if zone_type == "primary":
                files.append(
                    self._build_forward_file_spec(
                        raw_zone=raw_zone,
                        zone_name=zone_name,
                        zone_type=zone_type,
                        state=state,
                    )
                )

        if create_reverse_zones:
            for network in self._normalize_ipv4_networks(raw_zone.get("networks", ())):
                reverse_name = self._ipv4_reverse_zone_name(network)
                reverse_filename = (
                    reverse_name if zone_type in {"primary", "secondary"} else None
                )

                definitions.append(
                    ZoneDefinitionSpec(
                        name=reverse_name,
                        zone_type=zone_type,
                        state=state,
                        filename=reverse_filename,
                        primaries=tuple(primaries),
                        forwarders=tuple(forwarders),
                        update_policy=None,
                    )
                )

                if zone_type == "primary":
                    files.append(
                        self._build_reverse_ipv4_file_spec(
                            raw_zone=raw_zone,
                            zone_name=zone_name,
                            zone_type=zone_type,
                            state=state,
                            network=network,
                        )
                    )

            for network in self._normalize_ipv6_networks(
                raw_zone.get("ipv6_networks", ())
            ):
                reverse_name = self._ipv6_reverse_zone_name(network)
                reverse_filename = (
                    reverse_name if zone_type in {"primary", "secondary"} else None
                )

                definitions.append(
                    ZoneDefinitionSpec(
                        name=reverse_name,
                        zone_type=zone_type,
                        state=state,
                        filename=reverse_filename,
                        primaries=tuple(primaries),
                        forwarders=tuple(forwarders),
                        update_policy=None,
                    )
                )

                if zone_type == "primary":
                    files.append(
                        self._build_reverse_ipv6_file_spec(
                            raw_zone=raw_zone,
                            zone_name=zone_name,
                            zone_type=zone_type,
                            state=state,
                            network=network,
                        )
                    )

        return definitions, files

    def _build_zone_OLD(
        self,
        raw_zone: Mapping[str, Any],
        index: int,
    ) -> tuple[list[ZoneDefinitionSpec], list[ZoneFileSpec]]:
        """Build all canonical models for one logical zone."""
        zone_name = self._require_non_empty_string(
            raw_zone.get("name"),
            field_name=f"bind_zones[{index}].name",
        )
        zone_type = self._normalize_zone_type(
            raw_zone.get("type", "primary"),
            field_name=f"bind_zones[{index}].type",
        )
        state = self._normalize_state(
            raw_zone.get("state", "present"),
            field_name=f"bind_zones[{index}].state",
        )
        create_forward_zones = self._normalize_bool(
            raw_zone.get("create_forward_zones", True)
        )
        create_reverse_zones = self._normalize_bool(
            raw_zone.get("create_reverse_zones", True)
        )
        primaries = self._normalize_string_list(raw_zone.get("primaries", ()))
        update_policy = self._update_policy_service.normalize(
            raw_policy=raw_zone.get("update_policy"),
            zone_name=zone_name,
            zone_type=zone_type,
            allow_update_present=bool(raw_zone.get("allow_update")),
        )

        definitions: list[ZoneDefinitionSpec] = []
        files: list[ZoneFileSpec] = []

        if create_forward_zones:
            forward_filename = zone_name
            definitions.append(
                ZoneDefinitionSpec(
                    name=zone_name,
                    zone_type=zone_type,
                    state=state,
                    filename=forward_filename,
                    primaries=tuple(primaries),
                    update_policy=update_policy,
                )
            )

            if zone_type == "primary":
                files.append(
                    self._build_forward_file_spec(
                        raw_zone=raw_zone,
                        zone_name=zone_name,
                        zone_type=zone_type,
                        state=state,
                    )
                )

        if create_reverse_zones and zone_type == "primary":
            for network in self._normalize_ipv4_networks(raw_zone.get("networks", ())):
                reverse_name = self._ipv4_reverse_zone_name(network)
                definitions.append(
                    ZoneDefinitionSpec(
                        name=reverse_name,
                        zone_type=zone_type,
                        state=state,
                        filename=reverse_name,
                        primaries=tuple(primaries),
                        update_policy=None,
                    )
                )
                files.append(
                    self._build_reverse_ipv4_file_spec(
                        raw_zone=raw_zone,
                        zone_name=zone_name,
                        zone_type=zone_type,
                        state=state,
                        network=network,
                    )
                )

            for network in self._normalize_ipv6_networks(
                raw_zone.get("ipv6_networks", ())
            ):
                reverse_name = self._ipv6_reverse_zone_name(network)
                definitions.append(
                    ZoneDefinitionSpec(
                        name=reverse_name,
                        zone_type=zone_type,
                        state=state,
                        filename=reverse_name,
                        primaries=tuple(primaries),
                        update_policy=None,
                    )
                )
                files.append(
                    self._build_reverse_ipv6_file_spec(
                        raw_zone=raw_zone,
                        zone_name=zone_name,
                        zone_type=zone_type,
                        state=state,
                        network=network,
                    )
                )

        return definitions, files

    def _resolve_zone_type(
        self,
        raw_zone: Mapping[str, Any],
        field_name: str,
    ) -> str:
        """Resolve the effective zone type.

        Resolution order:
        1. Explicit ``type``
        2. ``forward`` if forwarders exist
        3. ``primary`` if authoritative content exists
        4. ``secondary`` if primaries exist
        5. fallback to ``primary``
        """
        explicit_type = raw_zone.get("type")
        if explicit_type is not None and str(explicit_type).strip():
            return self._normalize_zone_type(explicit_type, field_name=field_name)

        if self._has_non_empty_value(raw_zone.get("forwarders")):
            return "forward"

        if self._has_authoritative_zone_content(raw_zone):
            return "primary"

        if self._has_non_empty_value(raw_zone.get("primaries")):
            return "secondary"

        return "primary"

    def _build_forward_file_spec(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
        zone_type: str,
        state: str,
    ) -> ZoneFileSpec:
        """Build the canonical forward zone file model."""
        records = ()
        if state == "present":
            records = self._deduplicate_records(
                self._build_forward_records(raw_zone, zone_name)
            )

        return ZoneFileSpec(
            key=f"forward:{zone_name}",
            source_zone_name=zone_name,
            state=state,
            zone_type=zone_type,
            kind="forward",
            family="none",
            filename=zone_name,
            origin=self._ensure_trailing_dot(zone_name),
            records=records,
        )

    def _build_reverse_ipv4_file_spec(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
        zone_type: str,
        state: str,
        network: IPv4Network,
    ) -> ZoneFileSpec:
        """Build one canonical IPv4 reverse zone file model."""
        filename = self._ipv4_reverse_zone_name(network)
        records = ()
        if state == "present":
            records = self._deduplicate_records(
                self._build_reverse_ipv4_records(raw_zone, zone_name, network)
            )

        return ZoneFileSpec(
            key=f"reverse:ipv4:{network.with_prefixlen}",
            source_zone_name=zone_name,
            state=state,
            zone_type=zone_type,
            kind="reverse",
            family="ipv4",
            filename=filename,
            origin=self._ensure_trailing_dot(filename),
            network=network.with_prefixlen,
            records=records,
        )

    def _build_reverse_ipv6_file_spec(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
        zone_type: str,
        state: str,
        network: IPv6Network,
    ) -> ZoneFileSpec:
        """Build one canonical IPv6 reverse zone file model."""
        filename = self._ipv6_reverse_zone_name(network)
        records = ()
        if state == "present":
            records = self._deduplicate_records(
                self._build_reverse_ipv6_records(raw_zone, zone_name, network)
            )

        return ZoneFileSpec(
            key=f"reverse:ipv6:{network.with_prefixlen}",
            source_zone_name=zone_name,
            state=state,
            zone_type=zone_type,
            kind="reverse",
            family="ipv6",
            filename=filename,
            origin=self._ensure_trailing_dot(filename),
            network=network.with_prefixlen,
            records=records,
        )

    def _build_forward_records(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
    ) -> tuple[ZoneRecord, ...]:
        """Build canonical forward-zone resource records."""
        records: list[ZoneRecord] = []

        for name_server in self._normalize_string_list(
            raw_zone.get("name_servers", ())
        ):
            records.append(
                ZoneRecord(
                    owner="@",
                    rtype="NS",
                    value=self._normalize_host_reference(name_server, zone_name),
                )
            )

        for raw_host in self._normalize_mapping_list(raw_zone.get("hosts", ())):
            host_name = self._require_non_empty_string(
                raw_host.get("name"),
                field_name=f"bind_zones[{zone_name}].hosts[].name",
            )
            owner = self._normalize_owner(host_name)
            target_fqdn = self._normalize_host_reference(host_name, zone_name)

            ipv4_value = raw_host.get("ip")
            if ipv4_value is not None:
                records.append(
                    ZoneRecord(
                        owner=owner,
                        rtype="A",
                        value=self._normalize_ipv4_address(ipv4_value).compressed,
                    )
                )

            ipv6_value = raw_host.get("ipv6")
            if ipv6_value is not None:
                records.append(
                    ZoneRecord(
                        owner=owner,
                        rtype="AAAA",
                        value=self._normalize_ipv6_address(ipv6_value).compressed,
                    )
                )

            for alias in self._normalize_string_list(raw_host.get("aliases", ())):
                records.append(
                    ZoneRecord(
                        owner=self._normalize_owner(alias),
                        rtype="CNAME",
                        value=target_fqdn,
                    )
                )

            for host_name_server in self._normalize_string_list(
                raw_host.get("name_servers", ())
            ):
                records.append(
                    ZoneRecord(
                        owner=owner,
                        rtype="NS",
                        value=self._normalize_host_reference(
                            host_name_server, zone_name
                        ),
                    )
                )

        for raw_mail_server in self._normalize_mapping_list(
            raw_zone.get("mail_servers", ())
        ):
            mail_name = self._require_non_empty_string(
                raw_mail_server.get("name"),
                field_name=f"bind_zones[{zone_name}].mail_servers[].name",
            )
            preference = self._normalize_int(
                raw_mail_server.get("preference", 10),
                field_name=f"bind_zones[{zone_name}].mail_servers[].preference",
            )
            records.append(
                ZoneRecord(
                    owner="@",
                    rtype="MX",
                    value=self._normalize_host_reference(mail_name, zone_name),
                    priority=preference,
                )
            )

        for raw_service in self._normalize_mapping_list(raw_zone.get("services", ())):
            service_name = self._require_non_empty_string(
                raw_service.get("name"),
                field_name=f"bind_zones[{zone_name}].services[].name",
            )
            target = self._require_non_empty_string(
                raw_service.get("target"),
                field_name=f"bind_zones[{zone_name}].services[].target",
            )
            priority = self._normalize_int(
                raw_service.get("priority", 0),
                field_name=f"bind_zones[{zone_name}].services[].priority",
            )
            weight = self._normalize_int(
                raw_service.get("weight", 0),
                field_name=f"bind_zones[{zone_name}].services[].weight",
            )
            port = self._normalize_int(
                raw_service.get("port"),
                field_name=f"bind_zones[{zone_name}].services[].port",
            )
            records.append(
                ZoneRecord(
                    owner=self._normalize_owner(service_name),
                    rtype="SRV",
                    value=self._normalize_host_reference(target, zone_name),
                    priority=priority,
                    weight=weight,
                    port=port,
                )
            )

        for raw_text in self._normalize_mapping_list(raw_zone.get("text", ())):
            text_name = self._require_non_empty_string(
                raw_text.get("name"),
                field_name=f"bind_zones[{zone_name}].text[].name",
            )
            for text_value in self._normalize_string_list(raw_text.get("text", ())):
                records.append(
                    ZoneRecord(
                        owner=self._normalize_owner(text_name),
                        rtype="TXT",
                        value=text_value,
                    )
                )

        return tuple(records)

    def _build_reverse_ipv4_records(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
        network: IPv4Network,
    ) -> tuple[ZoneRecord, ...]:
        """Build canonical IPv4 reverse-zone records."""
        records: list[ZoneRecord] = []

        for name_server in self._normalize_string_list(
            raw_zone.get("name_servers", ())
        ):
            records.append(
                ZoneRecord(
                    owner="@",
                    rtype="NS",
                    value=self._normalize_host_reference(name_server, zone_name),
                )
            )

        for raw_host in self._normalize_mapping_list(raw_zone.get("hosts", ())):
            host_name = raw_host.get("name")
            host_ip = raw_host.get("ip")
            if host_name is None or host_ip is None:
                continue

            address = self._normalize_ipv4_address(host_ip)
            if address not in network:
                continue

            owner = self._ipv4_ptr_owner(address, network)
            records.append(
                ZoneRecord(
                    owner=owner,
                    rtype="PTR",
                    value=self._normalize_host_reference(str(host_name), zone_name),
                )
            )

        return tuple(records)

    def _build_reverse_ipv6_records(
        self,
        raw_zone: Mapping[str, Any],
        zone_name: str,
        network: IPv6Network,
    ) -> tuple[ZoneRecord, ...]:
        """Build canonical IPv6 reverse-zone records."""
        records: list[ZoneRecord] = []

        for name_server in self._normalize_string_list(
            raw_zone.get("name_servers", ())
        ):
            records.append(
                ZoneRecord(
                    owner="@",
                    rtype="NS",
                    value=self._normalize_host_reference(name_server, zone_name),
                )
            )

        for raw_host in self._normalize_mapping_list(raw_zone.get("hosts", ())):
            host_name = raw_host.get("name")
            host_ip = raw_host.get("ipv6")
            if host_name is None or host_ip is None:
                continue

            address = self._normalize_ipv6_address(host_ip)
            if address not in network:
                continue

            owner = self._ipv6_ptr_owner(address, network)
            records.append(
                ZoneRecord(
                    owner=owner,
                    rtype="PTR",
                    value=self._normalize_host_reference(str(host_name), zone_name),
                )
            )

        return tuple(records)

    def _normalize_zone_list(self, raw_zones: Any) -> list[Mapping[str, Any]]:
        """Normalize raw bind_zones input into a mapping list."""
        if not isinstance(raw_zones, Sequence) or isinstance(
            raw_zones,
            (str, bytes, bytearray),
        ):
            raise ZoneBuilderError(
                f"bind_zones must be a list of mappings, got {type(raw_zones).__name__}."
            )

        normalized: list[Mapping[str, Any]] = []
        for index, item in enumerate(raw_zones):
            if not isinstance(item, Mapping):
                raise ZoneBuilderError(
                    f"bind_zones[{index}] must be a mapping, got {type(item).__name__}."
                )
            normalized.append(item)

        return normalized

    def _normalize_mapping_list(self, value: Any) -> list[Mapping[str, Any]]:
        """Normalize a raw list of mapping objects."""
        if value is None:
            return []

        if not isinstance(value, Sequence) or isinstance(
            value, (str, bytes, bytearray)
        ):
            raise ZoneBuilderError(
                f"Expected a list of mappings, got {type(value).__name__}."
            )

        normalized: list[Mapping[str, Any]] = []
        for item in value:
            if not isinstance(item, Mapping):
                raise ZoneBuilderError(
                    f"Expected a mapping item, got {type(item).__name__}."
                )
            normalized.append(item)

        return normalized

    def _normalize_string_list(self, value: Any) -> list[str]:
        """Normalize a string or a sequence of strings into a string list."""
        if value is None:
            return []

        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []

        if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
            raise ZoneBuilderError(
                f"Expected a string or list of strings, got {type(value).__name__}."
            )

        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                normalized.append(text)

        return normalized

    def _normalize_zone_type(self, value: Any, field_name: str) -> str:
        """Normalize the zone type."""
        zone_type = self._require_non_empty_string(value, field_name=field_name).lower()
        if zone_type not in {"primary", "secondary", "forward"}:
            raise ZoneBuilderError(
                f"{field_name} must be one of: forward, primary, secondary."
            )
        return zone_type

    def _normalize_state(self, value: Any, field_name: str) -> str:
        """Normalize the desired zone state."""
        state = self._require_non_empty_string(value, field_name=field_name).lower()
        if state not in {"present", "absent"}:
            raise ZoneBuilderError(f"{field_name} must be one of: present, absent.")
        return state

    def _normalize_bool(self, value: Any) -> bool:
        """Normalize a boolean-like value."""
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "on", "1"}:
                return True
            if normalized in {"false", "no", "off", "0"}:
                return False

        return bool(value)

    def _normalize_int(self, value: Any, field_name: str) -> int:
        """Normalize an integer value."""
        if value is None:
            raise ZoneBuilderError(f"{field_name} is required.")

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ZoneBuilderError(f"{field_name} must be an integer.") from exc

    def _normalize_ipv4_networks(self, value: Any) -> tuple[IPv4Network, ...]:
        """Normalize IPv4 reverse network definitions."""
        networks: list[IPv4Network] = []
        seen: set[str] = set()

        for item in self._normalize_string_list(value):
            network = self._parse_ipv4_reverse_network(item)
            key = network.with_prefixlen
            if key not in seen:
                seen.add(key)
                networks.append(network)

        return tuple(networks)

    def _normalize_ipv6_networks(self, value: Any) -> tuple[IPv6Network, ...]:
        """Normalize IPv6 reverse network definitions."""
        networks: list[IPv6Network] = []
        seen: set[str] = set()

        for item in self._normalize_string_list(value):
            try:
                network = ip_network(item, strict=False)
            except ValueError as exc:
                raise ZoneBuilderError(
                    f"Invalid IPv6 reverse network: {item!r}."
                ) from exc

            if not isinstance(network, IPv6Network):
                raise ZoneBuilderError(f"Invalid IPv6 reverse network: {item!r}.")

            if network.prefixlen % 4 != 0:
                raise ZoneBuilderError(
                    f"IPv6 reverse networks must use a nibble boundary prefix length: {item!r}."
                )

            key = network.with_prefixlen
            if key not in seen:
                seen.add(key)
                networks.append(network)

        return tuple(networks)

    def _parse_ipv4_reverse_network(self, value: str) -> IPv4Network:
        """Parse compact IPv4 reverse network notation.

        Supported shorthand notations are ``10``, ``10.11``, ``10.11.0`` and full
        CIDR notation such as ``10.11.0.0/24``.
        """
        if "/" in value:
            try:
                network = ip_network(value, strict=False)
            except ValueError as exc:
                raise ZoneBuilderError(
                    f"Invalid IPv4 reverse network: {value!r}."
                ) from exc

            if not isinstance(network, IPv4Network):
                raise ZoneBuilderError(f"Invalid IPv4 reverse network: {value!r}.")
        else:
            octets = value.split(".")
            if not 1 <= len(octets) <= 4:
                raise ZoneBuilderError(f"Invalid IPv4 reverse network: {value!r}.")

            try:
                octet_values = [int(octet) for octet in octets]
            except ValueError as exc:
                raise ZoneBuilderError(
                    f"Invalid IPv4 reverse network: {value!r}."
                ) from exc

            if any(octet < 0 or octet > 255 for octet in octet_values):
                raise ZoneBuilderError(f"Invalid IPv4 reverse network: {value!r}.")

            prefixlen = len(octet_values) * 8
            padded = octet_values + [0] * (4 - len(octet_values))
            network = IPv4Network(
                f"{padded[0]}.{padded[1]}.{padded[2]}.{padded[3]}/{prefixlen}",
                strict=False,
            )

        if network.prefixlen % 8 != 0:
            raise ZoneBuilderError(
                f"IPv4 reverse networks must use an octet boundary prefix length: {value!r}."
            )

        return network

    def _normalize_ipv4_address(self, value: Any) -> IPv4Address:
        """Normalize an IPv4 address."""
        try:
            address = ip_address(str(value).strip())
        except ValueError as exc:
            raise ZoneBuilderError(f"Invalid IPv4 address: {value!r}.") from exc

        if not isinstance(address, IPv4Address):
            raise ZoneBuilderError(f"Invalid IPv4 address: {value!r}.")

        return address

    def _normalize_ipv6_address(self, value: Any) -> IPv6Address:
        """Normalize an IPv6 address."""
        try:
            address = ip_address(str(value).strip())
        except ValueError as exc:
            raise ZoneBuilderError(f"Invalid IPv6 address: {value!r}.") from exc

        if not isinstance(address, IPv6Address):
            raise ZoneBuilderError(f"Invalid IPv6 address: {value!r}.")

        return address

    def _normalize_owner(self, value: str) -> str:
        """Normalize a record owner name to a relative owner token."""
        owner = value.strip()
        return "@" if owner == "@" else owner.rstrip(".")

    def _normalize_host_reference(self, value: str, zone_name: str) -> str:
        """Normalize a host reference into a fully-qualified domain name."""
        text = value.strip()
        if text == "@":
            return self._ensure_trailing_dot(zone_name)
        if text.endswith("."):
            return text
        return f"{text}.{zone_name}."

    def _ensure_trailing_dot(self, value: str) -> str:
        """Ensure a DNS name ends with a trailing dot."""
        return value if value.endswith(".") else f"{value}."

    def _ipv4_reverse_zone_name(self, network: IPv4Network) -> str:
        """Return the IPv4 reverse zone name for one reverse network."""
        octet_count = network.prefixlen // 8
        octets = network.network_address.exploded.split(".")[:octet_count]
        return ".".join(reversed(octets)) + ".in-addr.arpa"

    def _ipv6_reverse_zone_name(self, network: IPv6Network) -> str:
        """Return the IPv6 reverse zone name for one reverse network."""
        nibble_count = network.prefixlen // 4
        hex_nibbles = network.network_address.exploded.replace(":", "")[:nibble_count]
        return ".".join(reversed(list(hex_nibbles))) + ".ip6.arpa"

    def _ipv4_ptr_owner(self, address: IPv4Address, network: IPv4Network) -> str:
        """Return the relative PTR owner inside an IPv4 reverse zone."""
        zone_labels = self._ipv4_reverse_zone_name(network).split(".")[:-2]
        full_labels = address.reverse_pointer.split(".")[:-2]
        owner_labels = full_labels[: len(full_labels) - len(zone_labels)]
        return ".".join(owner_labels) if owner_labels else "@"

    def _ipv6_ptr_owner(self, address: IPv6Address, network: IPv6Network) -> str:
        """Return the relative PTR owner inside an IPv6 reverse zone."""
        zone_labels = self._ipv6_reverse_zone_name(network).split(".")[:-2]
        full_labels = address.reverse_pointer.split(".")[:-2]
        owner_labels = full_labels[: len(full_labels) - len(zone_labels)]
        return ".".join(owner_labels) if owner_labels else "@"

    def _deduplicate_records(
        self, records: Sequence[ZoneRecord]
    ) -> tuple[ZoneRecord, ...]:
        """Remove duplicate records while preserving the original order."""
        deduplicated: list[ZoneRecord] = []
        seen: set[tuple[Any, ...]] = set()

        for record in records:
            key = (
                record.owner,
                record.rtype,
                record.value,
                record.ttl,
                record.priority,
                record.weight,
                record.port,
            )
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(record)

        return tuple(deduplicated)

    def _require_non_empty_string(self, value: Any, field_name: str) -> str:
        """Require a non-empty string-like value."""
        if value is None:
            raise ZoneBuilderError(f"{field_name} is required.")

        text = str(value).strip()
        if not text:
            raise ZoneBuilderError(f"{field_name} must not be empty.")

        return text

    def _has_authoritative_zone_content(self, raw_zone: Mapping[str, Any]) -> bool:
        """Return True if the zone contains authoritative record data."""
        authoritative_fields = (
            "name_servers",
            "hosts",
            "mail_servers",
            "services",
            "text",
            "update_policy",
        )

        return any(
            self._has_non_empty_value(raw_zone.get(field))
            for field in authoritative_fields
        )

    def _has_non_empty_value(self, value: Any) -> bool:
        """Return True if a raw value is semantically non-empty."""
        if value is None:
            return False

        if isinstance(value, str):
            return bool(value.strip())

        if isinstance(value, Mapping):
            return bool(value)

        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            return len(value) > 0

        return bool(value)


def build_zone_specs(raw_zones: Any) -> ZoneBuildResult:
    """Build canonical zone specs via the public service API."""
    builder = ZoneSpecBuilder()
    return builder.build(raw_zones)
