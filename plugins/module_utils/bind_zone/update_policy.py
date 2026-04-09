"""Validation and rendering helpers for BIND update-policy clauses."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .models import UpdatePolicy, UpdatePolicyRule

_ALLOWED_MODES: frozenset[str] = frozenset({"local", "rules"})
_ALLOWED_ACTIONS: frozenset[str] = frozenset({"grant", "deny"})
_ALLOWED_RULE_TYPES: frozenset[str] = frozenset(
    {
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
    }
)

_NAME_OMITTED_RULE_TYPES: frozenset[str] = frozenset({"zonesub"})
_NAME_DOT_PLACEHOLDER_RULE_TYPES: frozenset[str] = frozenset(
    {
        "self",
        "selfsub",
        "selfwild",
        "ms-self",
        "ms-selfsub",
        "krb5-self",
        "krb5-selfsub",
        "tcp-self",
        "6to4-self",
    }
)

_RR_TYPE_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9-]*)(?:\((?P<limit>[0-9]+)\))?$"
)
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:*@/\-+$]+$")


class UpdatePolicyValidationError(ValueError):
    """Raised when the update-policy input is invalid."""


class _UpdatePolicyRuleNormalizer:
    """Internal helper that validates and normalizes one update-policy rule."""

    def normalize(self, raw_rule: Any, index: int) -> UpdatePolicyRule:
        """Normalize one raw rule mapping into an UpdatePolicyRule.

        Args:
            raw_rule: Raw rule mapping from Ansible data.
            index: Zero-based rule index for error reporting.

        Returns:
            A normalized update-policy rule.

        Raises:
            UpdatePolicyValidationError: If the rule is invalid.
        """
        if not isinstance(raw_rule, Mapping):
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}] must be a mapping, "
                f"got {type(raw_rule).__name__}."
            )

        action = self._normalize_action(raw_rule.get("action"), index)
        identity = self._require_non_empty_string(
            value=raw_rule.get("identity"),
            field_name=f"update_policy.rules[{index}].identity",
        )
        ruletype = self._normalize_ruletype(raw_rule.get("ruletype"), index)
        name = self._normalize_name(raw_rule.get("name"), ruletype, index)
        types = self._normalize_types(raw_rule.get("types"), index)

        return UpdatePolicyRule(
            action=action,
            identity=identity,
            ruletype=ruletype,
            name=name,
            types=types,
        )

    def _normalize_action(self, value: Any, index: int) -> str:
        """Validate and normalize the rule action."""
        action = self._require_non_empty_string(
            value=value,
            field_name=f"update_policy.rules[{index}].action",
        ).lower()

        if action not in _ALLOWED_ACTIONS:
            allowed = ", ".join(sorted(_ALLOWED_ACTIONS))
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}].action must be one of: {allowed}."
            )

        return action

    def _normalize_ruletype(self, value: Any, index: int) -> str:
        """Validate and normalize the rule type."""
        ruletype = self._require_non_empty_string(
            value=value,
            field_name=f"update_policy.rules[{index}].ruletype",
        ).lower()

        if ruletype not in _ALLOWED_RULE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RULE_TYPES))
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}].ruletype must be one of: {allowed}."
            )

        return ruletype

    def _normalize_name(self, value: Any, ruletype: str, index: int) -> str | None:
        """Validate and normalize the optional rule name."""
        if ruletype in _NAME_OMITTED_RULE_TYPES:
            return None

        if ruletype in _NAME_DOT_PLACEHOLDER_RULE_TYPES:
            return "."

        if ruletype == "external":
            if value is None:
                return "."
            name = str(value).strip()
            return name if name else "."

        return self._require_non_empty_string(
            value=value,
            field_name=f"update_policy.rules[{index}].name",
        )

    def _normalize_types(self, value: Any, index: int) -> tuple[str, ...]:
        """Validate and normalize the RR type list.

        In rule-based update-policy syntax, the RR type list is mandatory.
        """
        if value is None:
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}].types is required."
            )

        if isinstance(value, str):
            items = [value]
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            items = list(value)
        else:
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}].types must be a string or a list of "
                f"strings, got {type(value).__name__}."
            )

        normalized: list[str] = []
        seen: set[str] = set()

        for item in items:
            if item is None:
                continue

            rrtype = self._normalize_rrtype_token(
                token=str(item).strip(),
                field_name=f"update_policy.rules[{index}].types",
            )

            if rrtype not in seen:
                seen.add(rrtype)
                normalized.append(rrtype)

        if not normalized:
            raise UpdatePolicyValidationError(
                f"update_policy.rules[{index}].types must not be empty."
            )

        return tuple(normalized)

    def _normalize_rrtype_token(self, token: str, field_name: str) -> str:
        """Validate one RR type token and normalize it to uppercase."""
        if not token:
            raise UpdatePolicyValidationError(
                f"{field_name} contains an empty RR type token."
            )

        match = _RR_TYPE_PATTERN.match(token)
        if not match:
            raise UpdatePolicyValidationError(
                f"{field_name} contains an invalid RR type token: {token!r}."
            )

        rrtype_name = match.group("name").upper()
        limit = match.group("limit")

        if limit is None:
            return rrtype_name

        return f"{rrtype_name}({limit})"

    def _require_non_empty_string(self, value: Any, field_name: str) -> str:
        """Require a non-empty string-like value."""
        if value is None:
            raise UpdatePolicyValidationError(f"{field_name} is required.")

        text = str(value).strip()
        if not text:
            raise UpdatePolicyValidationError(f"{field_name} must not be empty.")

        return text


class UpdatePolicyValidator:
    """Public validator for raw update-policy data structures."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self._rule_normalizer = _UpdatePolicyRuleNormalizer()

    def normalize(
        self,
        raw_policy: Any,
        *,
        zone_name: str,
        zone_type: str,
        allow_update_present: bool = False,
    ) -> UpdatePolicy | None:
        """Normalize raw update-policy input into a canonical model.

        Args:
            raw_policy: Raw update-policy value from Ansible data.
            zone_name: Zone name for error reporting.
            zone_type: Zone type such as ``primary`` or ``secondary``.
            allow_update_present: Whether ``allow-update`` is also configured.

        Returns:
            A normalized UpdatePolicy object or None.

        Raises:
            UpdatePolicyValidationError: If the input is invalid.
        """
        if raw_policy is None:
            return None

        if not isinstance(raw_policy, Mapping):
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy must be a mapping, "
                f"got {type(raw_policy).__name__}."
            )

        normalized_zone_type = str(zone_type).strip().lower()
        if normalized_zone_type != "primary":
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy is only valid for primary zones."
            )

        if allow_update_present:
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: allow_update and update_policy are mutually "
                f"exclusive."
            )

        mode = self._normalize_mode(raw_policy, zone_name)

        if mode == "local":
            self._validate_local_mode(raw_policy, zone_name)
            return UpdatePolicy(mode="local", rules=())

        return UpdatePolicy(
            mode="rules",
            rules=self._normalize_rules(raw_policy, zone_name),
        )

    def _normalize_mode(self, raw_policy: Mapping[str, Any], zone_name: str) -> str:
        """Normalize the update-policy mode."""
        raw_mode = raw_policy.get("mode")
        if raw_mode is None:
            if "rules" in raw_policy:
                raw_mode = "rules"
            else:
                raise UpdatePolicyValidationError(
                    f"Zone {zone_name!r}: update_policy.mode is required."
                )

        mode = str(raw_mode).strip().lower()
        if mode not in _ALLOWED_MODES:
            allowed = ", ".join(sorted(_ALLOWED_MODES))
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy.mode must be one of: {allowed}."
            )

        return mode

    def _validate_local_mode(
        self,
        raw_policy: Mapping[str, Any],
        zone_name: str,
    ) -> None:
        """Validate local mode constraints."""
        raw_rules = raw_policy.get("rules")
        if raw_rules not in (None, [], (), {}):
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy.rules must be omitted when "
                f"mode=local."
            )

    def _normalize_rules(
        self,
        raw_policy: Mapping[str, Any],
        zone_name: str,
    ) -> tuple[UpdatePolicyRule, ...]:
        """Validate rule-based mode."""
        raw_rules = raw_policy.get("rules")

        if not isinstance(raw_rules, Sequence) or isinstance(
            raw_rules, (str, bytes, bytearray)
        ):
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy.rules must be a list."
            )

        normalized_rules: list[UpdatePolicyRule] = []

        for index, raw_rule in enumerate(raw_rules):
            normalized_rules.append(self._rule_normalizer.normalize(raw_rule, index))

        if not normalized_rules:
            raise UpdatePolicyValidationError(
                f"Zone {zone_name!r}: update_policy.rules must not be empty when "
                f"mode=rules."
            )

        return tuple(normalized_rules)


class UpdatePolicyRenderer:
    """Render canonical update-policy models into named.conf syntax."""

    def render(
        self,
        policy: UpdatePolicy | None,
        *,
        indent: str = "    ",
        level: int = 1,
    ) -> str:
        """Render one update-policy clause.

        Args:
            policy: Canonical policy model.
            indent: One indentation unit.
            level: Base indentation level.

        Returns:
            Rendered update-policy clause or an empty string.
        """
        if policy is None:
            return ""

        base_indent = indent * level
        child_indent = indent * (level + 1)

        if policy.mode == "local":
            return f"{base_indent}update-policy local;"

        lines = [f"{base_indent}update-policy {{"]
        for rule in policy.rules:
            lines.append(f"{child_indent}{self._render_rule(rule)}")
        lines.append(f"{base_indent}}};")

        return "\n".join(lines)

    def _render_rule(self, rule: UpdatePolicyRule) -> str:
        """Render one normalized rule line."""
        tokens: list[str] = [
            rule.action,
            self._render_string_token(rule.identity),
            rule.ruletype,
        ]

        if rule.name is not None:
            tokens.append(self._render_string_token(rule.name))

        tokens.extend(rule.types)

        return f"{' '.join(tokens)};"

    def _render_string_token(self, value: str) -> str:
        """Render a BIND token with minimal quoting."""
        if value == ".":
            return value

        if _SAFE_TOKEN_PATTERN.match(value):
            return value

        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'


class UpdatePolicyService:
    """High-level public API for update-policy normalization and rendering."""

    def __init__(
        self,
        validator: UpdatePolicyValidator | None = None,
        renderer: UpdatePolicyRenderer | None = None,
    ) -> None:
        """Initialize the service."""
        self._validator = validator or UpdatePolicyValidator()
        self._renderer = renderer or UpdatePolicyRenderer()

    def normalize(
        self,
        raw_policy: Any,
        *,
        zone_name: str,
        zone_type: str,
        allow_update_present: bool = False,
    ) -> UpdatePolicy | None:
        """Normalize raw update-policy data into a canonical model."""
        return self._validator.normalize(
            raw_policy=raw_policy,
            zone_name=zone_name,
            zone_type=zone_type,
            allow_update_present=allow_update_present,
        )

    def render(
        self,
        policy: UpdatePolicy | None,
        *,
        indent: str = "    ",
        level: int = 1,
    ) -> str:
        """Render a canonical update-policy model."""
        return self._renderer.render(
            policy=policy,
            indent=indent,
            level=level,
        )

    def normalize_and_render(
        self,
        raw_policy: Any,
        *,
        zone_name: str,
        zone_type: str,
        allow_update_present: bool = False,
        indent: str = "    ",
        level: int = 1,
    ) -> str:
        """Normalize raw input and render it immediately."""
        policy = self.normalize(
            raw_policy=raw_policy,
            zone_name=zone_name,
            zone_type=zone_type,
            allow_update_present=allow_update_present,
        )
        return self.render(
            policy=policy,
            indent=indent,
            level=level,
        )


def normalize_update_policy(
    raw_policy: Any,
    *,
    zone_name: str,
    zone_type: str,
    allow_update_present: bool = False,
) -> UpdatePolicy | None:
    """Normalize raw update-policy data."""
    service = UpdatePolicyService()
    return service.normalize(
        raw_policy=raw_policy,
        zone_name=zone_name,
        zone_type=zone_type,
        allow_update_present=allow_update_present,
    )


def render_update_policy(
    raw_policy: Any,
    *,
    zone_name: str,
    zone_type: str,
    allow_update_present: bool = False,
    indent: str = "    ",
    level: int = 1,
) -> str:
    """Normalize and render raw update-policy data."""
    service = UpdatePolicyService()
    return service.normalize_and_render(
        raw_policy=raw_policy,
        zone_name=zone_name,
        zone_type=zone_type,
        allow_update_present=allow_update_present,
        indent=indent,
        level=level,
    )
