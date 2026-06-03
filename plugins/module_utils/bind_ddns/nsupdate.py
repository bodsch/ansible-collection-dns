"""BIND nsupdate client for DDNS."""

from __future__ import absolute_import, annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.tsig import (
    ensure_base64_secret,
)

try:
    from ansible_collections.bodsch.dns.plugins.module_utils.dns_lookup import (
        zone_soa_serial,
    )

    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False


class NsupdateClient:
    """Execute nsupdate commands for DDNS updates."""

    def __init__(
        self,
        module: AnsibleModule | None = None,
        nsupdate_path: str = "/usr/bin/nsupdate",
        key_name: str | None = None,
        key_secret: str | None = None,
        key_algorithm: str = "HMAC-SHA256",
        server: str | None = None,
        port: int = 53,
    ) -> None:
        """Initialize nsupdate client.

        Args:
            nsupdate_path: Path to nsupdate binary
            key_name: TSIG key name (optional)
            key_secret: TSIG key secret (optional)
            key_algorithm: TSIG algorithm (default: HMAC-SHA256)
            server: Target server to send the update to (optional). If unset,
                nsupdate resolves the zone's primary master from its SOA, which
                for public zone names can send the update to the wrong server.
            port: Target server port (default: 53)
        """
        self.module: AnsibleModule | None = module
        self.module.log("NsupdateClient::__init__()")

        self.nsupdate_path: str = nsupdate_path
        self.key_name: str | None = key_name
        self.key_secret: str | None = key_secret
        self.key_algorithm: str = key_algorithm
        self.server: str | None = server
        self.port: int = port
        # self.last_return_code: None = None
        # self.last_stdout: None = None
        # self.last_stderr: None = None

    def execute(
        self,
        zone: str,
        updates: list[str],
        check: bool = False,
    ) -> dict[str, Any]:
        """Execute nsupdate commands.

        Args:
            zone: Zone name
            updates: List of nsupdate commands
            check: If True, raise exception on non-zero exit code

        Returns:
            Dict with keys: return_code, stdout, stderr, success
        """
        # Build nsupdate input
        nsupdate_input: list[Any] = []

        # Target the explicit server first, otherwise nsupdate derives it from
        # the zone's SOA primary master (wrong for public zone names).
        if self.server:
            nsupdate_input.append(f"server {self.server} {self.port}")

        if self.key_name and self.key_secret:
            # nsupdate expects the hmac name in lower case (e.g. hmac-sha256)
            # and the secret as base64; normalise a plain-text secret.
            secret: str = self._ensure_base64(self.key_secret)
            nsupdate_input.append(
                f"key {self.key_algorithm.lower()}:{self.key_name} {secret}"
            )

        nsupdate_input.append(f"zone {zone}")
        nsupdate_input.extend(updates)
        nsupdate_input.append("send")

        # nsupdate reads its directives from stdin, not from argv.
        cmd_input = "\n".join(nsupdate_input) + "\n"

        # BIND only bumps the SOA serial when a dynamic update actually changes
        # the zone, so comparing the serial before/after tells us whether the
        # update was a no-op - that is what makes this idempotent.
        serial_before = self._zone_serial(zone)

        rc, stdout, stderr = self._exec(cmd_input, check_rc=check)

        if rc != 0:
            raise NsupdateExecutionError(
                "nsupdate command failed",
                return_code=rc,
                stdout=stdout,
                stderr=stderr,
                commands=updates,
            )

        serial_after = self._zone_serial(zone)

        if serial_before is None or serial_after is None:
            # Could not determine the serial; fall back to assuming a change.
            changed = True
        else:
            changed = serial_before != serial_after

        return {
            "return_code": rc,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "success": rc == 0,
            "changed": changed,
            "commands": updates,
        }

    def add_record(
        self,
        zone: str,
        name: str,
        ttl: int,
        rtype: str,
        rdata: str,
    ) -> dict[str, Any]:
        """Add or update a DNS record via DDNS.

        Args:
            zone: Zone name
            name: Record name (FQDN)
            ttl: Time to live
            rtype: Record type (A, AAAA, CNAME, etc.)
            rdata: Record data

        Returns:
            Update result
        """
        self.module.log(
            f"NsupdateClient::add_record(zone: {zone}, name: {name}, ttl: {ttl}, rtype: {rtype}, rdata: {rdata})"
        )

        updates = [
            f"update add {name} {ttl} {rtype} {rdata}",
        ]
        return self.execute(zone, updates)

    def delete_record(
        self,
        zone: str,
        name: str,
        rtype: str,
        rdata: str | None = None,
    ) -> dict[str, Any]:
        """Delete a DNS record via DDNS.

        Args:
            zone: Zone name
            name: Record name (FQDN)
            rtype: Record type
            rdata: Record data (optional; if omitted, deletes all records of type)

        Returns:
            Update result
        """
        self.module.log(
            f"NsupdateClient::delete_record(zone: {zone}, name: {name}, rtype: {rtype}, rdata: {rdata})"
        )

        if rdata:
            updates = [f"update delete {name} {rtype} {rdata}"]
        else:
            updates = [f"update delete {name} {rtype}"]

        return self.execute(zone, updates)

    def _zone_serial(self, zone: str) -> int | None:
        """Return the current SOA serial of a zone, or None if unavailable.

        Uses dnspython (via dns_lookup.zone_soa_serial) to query the same
        server the update is sent to, so the answer reflects the authoritative
        serial rather than a cached one - no external tools required.

        Args:
          zone: Zone name.

        Returns:
          The SOA serial as int, or None when it cannot be determined.
        """
        if not HAS_DNSPYTHON:
            return None

        return zone_soa_serial(zone, nameserver=self.server, port=self.port)

    def _ensure_base64(self, secret: str) -> str:
        """Return the TSIG secret as valid base64.

        nsupdate requires the key secret to be base64 encoded. The same
        normalisation is applied to the named key{} statement via the
        bodsch.dns.tsig_base64 filter so both sides derive identical key bytes.

        Args:
          secret: The TSIG secret as provided by the user.

        Returns:
          A base64 encoded secret accepted by nsupdate.
        """
        normalized = ensure_base64_secret(secret)
        if normalized != secret:
            self.module.log(
                "NsupdateClient::_ensure_base64() - secret was not base64, encoded it"
            )
        return normalized

    def _exec(self, stdin_data: str, check_rc: bool = True) -> tuple[int, str, str]:
        """Run nsupdate, feeding its directives via stdin.

        Args:
          stdin_data: The nsupdate directives (one per line) to pipe to stdin.
          check_rc: If True, Ansible will treat non-zero return codes as fatal.

        Returns:
          A tuple of `(rc, stdout, stderr)`.
        """
        args: list[str] = [self.nsupdate_path]

        self.module.log(f"NsupdateClient::_exec(args: {args}, check_rc: {check_rc})")

        rc, out, err = self.module.run_command(args, data=stdin_data, check_rc=check_rc)

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


class NsupdateError(Exception):
    """Base exception for nsupdate errors."""

    pass


class NsupdateNotFoundError(NsupdateError):
    """Raised when nsupdate binary is not found."""

    pass


class NsupdateExecutionError(NsupdateError):
    """Raised when nsupdate command fails."""

    def __init__(
        self,
        message: str,
        return_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        commands: list[str] | None = None,
    ) -> None:
        """Initialize with command details."""
        super().__init__(message)
        self.return_code: int = return_code
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.commands: list[str] | None = commands or []
