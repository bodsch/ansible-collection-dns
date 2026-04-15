"""Data models for BIND zone configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

UpdatePolicyMode = Literal["local", "rules"]
UpdatePolicyAction = Literal["grant", "deny"]
UpdatePolicyRuleType = Literal[
    "name",
    "subdomain",
    "zonesub",
    "wildcard",
    "self",
    "selfsub",
    "selfwild",
    "ms-self",
    "ms-selfsub",
    "ms-subdomain",
    "ms-subdomain-self-rhs",
    "krb5-self",
    "krb5-selfsub",
    "krb5-subdomain",
    "krb5-subdomain-self-rhs",
    "tcp-self",
    "6to4-self",
    "external",
]

ZoneType = Literal["primary", "secondary", "forward"]
ZoneState = Literal["present", "absent"]
ZoneFileKind = Literal["forward", "reverse"]
AddressFamily = Literal["none", "ipv4", "ipv6"]
ZoneFileAction = Literal["unchanged", "created", "updated", "deleted"]


@dataclass(frozen=True, slots=True)
class UpdatePolicyRule:
    """Canonical representation of one BIND update-policy rule."""

    action: UpdatePolicyAction
    identity: str
    ruletype: UpdatePolicyRuleType
    types: tuple[str, ...] = field(default_factory=tuple)
    name: str | None = None


@dataclass(frozen=True, slots=True)
class UpdatePolicy:
    """Canonical representation of a BIND update-policy clause."""

    mode: UpdatePolicyMode
    rules: tuple[UpdatePolicyRule, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ZoneDefinitionSpec:
    """Canonical representation of one BIND zone definition.

    This model represents one ``zone { ... }`` statement that will later be
    rendered into named.conf-compatible configuration.
    """

    name: str
    zone_type: ZoneType = "primary"
    state: ZoneState = "present"
    filename: str | None = None
    primaries: tuple[str, ...] = field(default_factory=tuple)
    forwarders: tuple[str, ...] = field(default_factory=tuple)
    update_policy: UpdatePolicy | None = None


@dataclass(frozen=True, slots=True)
class ZoneRecord:
    """Canonical representation of one DNS resource record."""

    owner: str
    rtype: str
    value: str
    ttl: int | None = None
    priority: int | None = None
    weight: int | None = None
    port: int | None = None


@dataclass(frozen=True, slots=True)
class ZoneFileSpec:
    """Canonical desired state for one managed zone file.

    One logical zone can create one forward zone file and multiple reverse zone
    files. This model intentionally represents exactly one concrete file.
    """

    key: str
    source_zone_name: str
    state: ZoneState
    zone_type: ZoneType
    kind: ZoneFileKind
    family: AddressFamily
    filename: str
    origin: str
    network: str | None = None
    default_ttl: int = 86400
    records: tuple[ZoneRecord, ...] = field(default_factory=tuple)

    @property
    def is_forward(self) -> bool:
        """Return True if this spec describes a forward zone file."""
        return self.kind == "forward"

    @property
    def is_reverse(self) -> bool:
        """Return True if this spec describes a reverse zone file."""
        return self.kind == "reverse"


@dataclass(frozen=True, slots=True)
class ZoneFileState:
    """Current persisted state for one managed zone file."""

    filename: str
    exists: bool
    serial: int | None = None
    sha256: str | None = None
    content: str | None = None


@dataclass(frozen=True, slots=True)
class ZoneFileChange:
    """Result model for one reconciled zone file."""

    key: str
    filename: str
    action: ZoneFileAction
    changed: bool
    old_serial: int | None = None
    new_serial: int | None = None
    diff_before: str | None = None
    diff_after: str | None = None


@dataclass(frozen=True, slots=True)
class ZoneFileCacheEntry:
    """Persisted metadata for one managed zone file."""

    key: str
    filename: str
    source_zone_name: str
    state: ZoneState
    kind: ZoneFileKind
    family: AddressFamily
    network: str | None = None
    content_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ZoneBuildResult:
    """Combined result of the canonical BIND zone builder."""

    zone_definitions: tuple[ZoneDefinitionSpec, ...] = field(default_factory=tuple)
    zone_files: tuple[ZoneFileSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """Combined result of the zone file reconciliation process."""

    changed: bool
    changes: tuple[ZoneFileChange, ...] = field(default_factory=tuple)
