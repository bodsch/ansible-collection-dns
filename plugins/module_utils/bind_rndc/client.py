"""BIND rndc command client."""

from __future__ import absolute_import, annotations

from typing import Any

from ansible.module_utils.basic import AnsibleModule


class RndcClient:
    """Execute rndc commands safely."""

    def __init__(
        self,
        module: AnsibleModule | None = None,
        rndc_path: str = "/usr/sbin/rndc",
        rndc_config: str | None = None,
    ) -> None:
        """Initialize rndc client.

        Args:
            rndc_path: Path to rndc binary
            rndc_config: Path to rndc.conf (optional, uses system default if None)
        """
        self.module: AnsibleModule | None = module
        self.module.log("RndcClient::__init__()")

        self.rndc_path: str = rndc_path
        self.rndc_config: str | None = rndc_config
        self.last_return_code: None = None
        self.last_stdout: None = None
        self.last_stderr: None = None

    def execute(self, *args: str, check: bool = False) -> dict[str, Any]:
        """Execute rndc command.

        Args:
            *args: rndc command arguments (e.g., 'reload', 'status', 'reload zonename')
            check: If True, raise exception on non-zero exit code

        Returns:
            Dict with keys: return_code, stdout, stderr, success
        """
        self.module.log(f"RndcClient::execute(args: {args}, check: {check})")

        cmd: list[str] = [self.rndc_path]

        if self.rndc_config:
            cmd.extend(["-c", self.rndc_config])

        cmd.extend(args)

        rc, stdout, stderr = self._exec(cmd)

        if rc != 0:
            raise RndcExecutionError(
                f"rndc command failed: {' '.join(cmd)}",
                return_code=rc,
                stdout=stdout,
                stderr=stderr,
            )

        return {
            "return_code": rc,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "success": rc == 0,
        }

    def status(self, zone: str | None = None) -> dict[str, Any]:
        """Get BIND status via rndc status.

        Args:
            zone: Optional zone name to check specific zone status

        Returns:
            Dict with status information
        """
        self.module.log(f"RndcClient::status(zone: {zone})")

        args = ["status"]
        if zone:
            args.append(zone)

        result = self.execute(*args)
        return result

    def reload(self, *zones: str) -> dict[str, Any]:
        """Reload zones via rndc reload.

        C(rndc reload) accepts only a single zone per call (further arguments
        are interpreted as class/view), so each zone is reloaded individually.

        Args:
            *zones: Zone names to reload. If empty, reloads all zones.

        Returns:
            Dict with reload result
        """
        self.module.log(f"RndcClient::reload(zones: {zones})")

        if not zones:
            return self.execute("reload")

        stdout_parts: list[str] = []
        for zone in zones:
            result = self.execute("reload", zone)
            stdout_parts.append(f"{zone}: {result['stdout']}")

        return {
            "return_code": 0,
            "stdout": "\n".join(stdout_parts),
            "stderr": "",
            "success": True,
        }

    def freeze(self, *zones: str) -> dict[str, Any]:
        """Suspend updates to dynamic zones via rndc freeze.

        Syncs each zone's journal into its master file and suspends dynamic
        updates so the file can be rewritten safely. C(rndc freeze) takes a
        single zone per call, so each zone is frozen individually.

        Args:
            *zones: Zone names to freeze. If empty, freezes all zones.

        Returns:
            Dict with freeze result
        """
        self.module.log(f"RndcClient::freeze(zones: {zones})")

        if not zones:
            return self.execute("freeze")

        stdout_parts: list[str] = []
        for zone in zones:
            result = self.execute("freeze", zone)
            stdout_parts.append(f"{zone}: {result['stdout']}")

        return {
            "return_code": 0,
            "stdout": "\n".join(stdout_parts),
            "stderr": "",
            "success": True,
        }

    def thaw(self, *zones: str) -> dict[str, Any]:
        """Re-enable updates to frozen zones via rndc thaw.

        Reloads each zone from its (rewritten) master file and re-enables
        dynamic updates. C(rndc thaw) takes a single zone per call, so each
        zone is thawed individually.

        Args:
            *zones: Zone names to thaw. If empty, thaws all zones.

        Returns:
            Dict with thaw result
        """
        self.module.log(f"RndcClient::thaw(zones: {zones})")

        if not zones:
            return self.execute("thaw")

        stdout_parts: list[str] = []
        for zone in zones:
            result = self.execute("thaw", zone)
            stdout_parts.append(f"{zone}: {result['stdout']}")

        return {
            "return_code": 0,
            "stdout": "\n".join(stdout_parts),
            "stderr": "",
            "success": True,
        }

    def reconfig(self) -> dict[str, Any]:
        """Reload the config and load newly added zones via rndc reconfig.

        Unlike C(reload), this picks up zones that were newly declared in
        named.conf (or removes vanished ones). It does not reload the data of
        zones that already existed, so changed zone files still need reload().

        Returns:
            Dict with reconfig result
        """
        self.module.log("RndcClient::reconfig()")

        return self.execute("reconfig")

    def is_available(self) -> bool:
        """Check if rndc is available and working.

        Returns:
            True if rndc status succeeds, False otherwise
        """
        self.module.log("RndcClient::is_available()")

        try:
            result = self.status()
            return result["success"]
        except (RndcNotFoundError, RndcExecutionError):
            return False

    def _exec(self, commands: list[str], check_rc: bool = True) -> tuple[int, str, str]:
        """Execute a command via Ansible's `run_command()`.

        Args:
          commands: The fully prepared argument vector.
          check_rc: If True, Ansible will treat non-zero return codes as fatal.

        Returns:
          A tuple of `(rc, stdout, stderr)`.
        """
        self.module.log(
            f"RndcClient::_exec(commands: {commands}, check_rc: {check_rc})"
        )

        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


class RndcError(Exception):
    """Base exception for rndc errors."""

    pass


class RndcNotFoundError(RndcError):
    """Raised when rndc binary is not found."""

    pass


class RndcExecutionError(RndcError):
    """Raised when rndc command fails."""

    def __init__(
        self,
        message: str,
        return_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        """Initialize with command details."""
        super().__init__(message)
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
