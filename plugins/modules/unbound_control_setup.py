#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Ansible module: unbound_control_setup
======================================

Invokes ``unbound-control-setup`` to generate the TLS key/certificate pairs
required by unbound's remote-control interface, then enforces correct POSIX
ownership on the generated files.

The module is **idempotent**: if the server key file already exists the
module exits immediately with ``changed=False`` without re-running the
setup binary.

Supports Ansible **check mode**: in check mode the binary is *not* invoked;
the module returns a predictive ``changed=True`` result instead.

Author: Bodo Schulz <bodo@boone-schulz.de>
"""

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

import grp
import os
import pwd
import shutil
from pathlib import Path
from typing import Any, Optional

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------
# Ansible module documentation
# ---------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: unbound_control_setup
short_description: Run unbound-control-setup to create TLS key/cert pairs.
version_added: "1.5.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Invokes C(unbound-control-setup) to generate the server and control
    TLS key/certificate files required by unbound's remote-control interface.
  - Idempotent: skips execution if the server key file already exists.
  - Enforces POSIX ownership on all generated files.
  - Supports Ansible check mode.

options:
  conf_dir:
    description:
      - Path to the unbound configuration directory.
      - Passed as C(-d) to C(unbound-control-setup) and used as the working
        directory during execution.
    required: true
    type: str
  certs:
    description:
      - Dictionary describing expected certificate and key file paths.
      - The module reads C(server.key_file) for idempotency detection and
        applies ownership to both C(server.key_file) and C(server.cert_file)
        after a successful run.
    required: true
    type: dict
    suboptions:
      server:
        description: Paths for the server TLS key and certificate.
        type: dict
        suboptions:
          key_file:
            description: Absolute path to the server private key.
            type: str
          cert_file:
            description: Absolute path to the server certificate.
            type: str
      control:
        description: Paths for the control TLS key and certificate.
        type: dict
        suboptions:
          key_file:
            description: Absolute path to the control private key.
            type: str
          cert_file:
            description: Absolute path to the control certificate.
            type: str
  owner:
    description: POSIX user that should own the generated files.
    required: false
    type: str
    default: unbound
  group:
    description: POSIX group that should own the generated files.
    required: false
    type: str
    default: unbound
"""

EXAMPLES = r"""
- name: Run unbound-control-setup
  unbound_control_setup:
    conf_dir: /etc/unbound
    certs:
      server:
        key_file: /etc/unbound/unbound_server.key
        cert_file: /etc/unbound/unbound_server.pem
      control:
        key_file: /etc/unbound/unbound_control.key
        cert_file: /etc/unbound/unbound_control.pem
    owner: unbound
    group: unbound
"""

RETURN = r"""
failed:
  description: Whether the module encountered a fatal error.
  type: bool
  returned: always
changed:
  description: Whether the module altered system state.
  type: bool
  returned: always
msg:
  description: Human-readable status or error description.
  type: str
  returned: always
rc:
  description: Return code of the invoked subprocess (when applicable).
  type: int
  returned: when the subprocess was executed
"""

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_OWNER: str = "unbound"
_DEFAULT_GROUP: str = "unbound"

# ---------------------------------------------------------------------------
# Main module class
# ---------------------------------------------------------------------------


class UnboundControlSetup:
    """Manages the execution of ``unbound-control-setup``.

    Encapsulates input validation, idempotency checking, subprocess execution,
    and post-run file-ownership enforcement for the ``unbound_control_setup``
    Ansible module.

    Attributes:
        module:      The active :class:`AnsibleModule` instance.
        conf_dir:    Absolute path to the unbound configuration directory.
        certs:       Mapping of certificate categories to their key/cert paths.
        owner:       POSIX user name that should own the generated files.
        group:       POSIX group name that should own the generated files.
        unbound_bin: Resolved path to ``unbound-control-setup``, or ``None``
                     if the binary is not found on ``$PATH``.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """Initialise the setup handler from an :class:`AnsibleModule` instance.

        Reads all relevant parameters from *module* and resolves the path to
        the ``unbound-control-setup`` binary via the module's ``get_bin_path``
        helper.

        Args:
            module: Fully initialised :class:`AnsibleModule`.
                    Expected parameters: ``conf_dir``, ``certs``, ``owner``,
                    ``group``.

        Example expected *certs* structure::

            {
                "server": {
                    "key_file":  "/etc/unbound/unbound_server.key",
                    "cert_file": "/etc/unbound/unbound_server.pem",
                },
                "control": {
                    "key_file":  "/etc/unbound/unbound_control.key",
                    "cert_file": "/etc/unbound/unbound_control.pem",
                },
            }
        """
        self.module: AnsibleModule = module

        self.conf_dir: str = module.params["conf_dir"]
        self.certs: dict[str, Any] = module.params["certs"]
        self.owner: str = module.params["owner"]
        self.group: str = module.params["group"]
        self.unbound_bin: Optional[str] = module.get_bin_path(
            "unbound-control-setup", False
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the full setup workflow and return an Ansible result dict.

        The method performs the following steps in order:

        1. Validate all inputs via :meth:`_validate_inputs`.
        2. Abort with a descriptive error if the setup binary is missing.
        3. Return early (idempotent, ``changed=False``) if the server key
           file already exists on disk.
        4. Return a predictive result without executing anything if Ansible
           is running in *check mode*.
        5. Change the working directory to *conf_dir* and invoke
           ``unbound-control-setup -d <conf_dir>``.
        6. On success, enforce POSIX ownership on the server key and cert.

        Returns:
            A dictionary that always contains:

            * ``failed``  (bool)  – ``True`` on any error.
            * ``changed`` (bool)  – ``True`` if files were created.
            * ``msg``     (str | list[str]) – Status or error description.
            * ``rc``      (int)   – Subprocess return code (when applicable).
        """
        self._validate_inputs()

        if not self.unbound_bin:
            return dict(
                rc=1,
                failed=True,
                changed=False,
                msg="'unbound-control-setup' binary not found on $PATH.",
            )

        server_key_file = Path(self.certs.get("server", {}).get("key_file", ""))

        if server_key_file.exists():
            return dict(
                rc=0,
                failed=False,
                changed=False,
                msg="Server key file already exists – nothing to do.",
            )

        # Predictive exit: do not mutate the system in check mode.
        if self.module.check_mode:
            return dict(
                rc=0,
                failed=False,
                changed=True,
                msg="Check mode: 'unbound-control-setup' would be executed.",
            )

        cmd: list[str] = [self.unbound_bin, "-d", self.conf_dir]

        os.chdir(self.conf_dir)
        rc, out, err = self._exec(cmd)

        if rc != 0:
            output_lines: list[str] = []
            for stream in (out, err):
                if stream:
                    output_lines.extend(stream.splitlines())

            self.module.log(f"unbound-control-setup failed: {output_lines}")
            return dict(
                rc=rc,
                failed=True,
                changed=False,
                msg=output_lines,
            )

        self.module.log(f"unbound-control-setup stdout: {out.strip()}")

        server_cert: dict[str, str] = self.certs.get("server", {})
        for file_path in (
            server_cert.get("key_file", ""),
            server_cert.get("cert_file", ""),
        ):
            if file_path:
                self._ensure_ownership(Path(file_path))

        return dict(
            rc=0,
            failed=False,
            changed=True,
            msg=(
                "Setup successful. Certificates created. "
                "Enable remote-control in unbound.conf to activate them."
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> None:
        """Validate all module inputs before any mutating operations.

        Performs the following checks in order:

        * ``conf_dir`` – if it already exists on disk, it must be a directory
          (not a regular file or other inode type).
        * ``owner`` – must resolve to an existing POSIX user via
          :func:`pwd.getpwnam`.
        * ``group`` – must resolve to an existing POSIX group via
          :func:`grp.getgrnam`.

        When ``conf_dir`` exists, the current owner and group of the directory
        are logged at module debug level for observability.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` on
            the first validation error encountered, which terminates the
            module immediately.
        """
        self.module.log("UnboundControlSetup::_validate_inputs()")

        config_path = Path(self.conf_dir)

        # If the path already exists it must be a directory, not a file.
        if config_path.exists() and not config_path.is_dir():
            self.module.fail_json(
                msg=(
                    f"conf_dir '{self.conf_dir}' already exists but is not "
                    "a directory."
                )
            )

        # Log the existing directory's ownership for observability.
        # Guard against the path not yet existing or unresolvable UID/GIDs.
        if config_path.is_dir():
            try:
                self.module.log(
                    f"'{config_path}' is owned by "
                    f"{config_path.owner()}:{config_path.group()}"
                )
            except (KeyError, PermissionError) as exc:
                self.module.log(
                    f"Could not determine ownership of '{config_path}': {exc}"
                )

        try:
            pwd.getpwnam(self.owner)
        except KeyError:
            self.module.fail_json(
                msg=f"owner '{self.owner}' does not exist on the target system."
            )

        try:
            grp.getgrnam(self.group)
        except KeyError:
            self.module.fail_json(
                msg=f"group '{self.group}' does not exist on the target system."
            )

    def _ensure_ownership(self, path: Path) -> None:
        """Apply POSIX ownership (``chown``) to a single path.

        Uses :func:`shutil.chown` which accepts user/group names directly,
        avoiding the need to resolve UIDs/GIDs manually.

        Args:
            path: Filesystem path whose ownership should be updated to
                  ``self.owner``/``self.group``.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` if
            :func:`shutil.chown` raises :exc:`OSError` (e.g. insufficient
            privileges).
        """
        try:
            shutil.chown(str(path), self.owner, self.group)
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to set ownership on '{path}': {exc}")

    def _exec(self, commands: list[str]) -> tuple[int, str, str]:
        """Run an external command through the Ansible module subprocess wrapper.

        Delegates to :meth:`~ansible.module_utils.basic.AnsibleModule.run_command`
        with ``check_rc=False`` so that non-zero exit codes are handled by the
        caller rather than raising an exception here.

        Args:
            commands: Argument vector where ``commands[0]`` is the absolute
                      path to the executable.

        Returns:
            A three-tuple ``(return_code, stdout, stderr)`` where *stdout*
            and *stderr* are decoded strings (empty string when there is no
            output).
        """
        rc, out, err = self.module.run_command(commands, check_rc=False)
        return rc, out, err


# ---------------------------------------------------------------------------
# Backward-compatibility alias (preserves the original typo as an alias so
# that any external code referencing the old name continues to work)
# ---------------------------------------------------------------------------

UnboundControllSetup = UnboundControlSetup  # noqa: N816

# ---------------------------------------------------------------------------
# Ansible entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Define the module argument spec and dispatch to :class:`UnboundControlSetup`.

    Constructs the :class:`AnsibleModule`, delegates all logic to
    :class:`UnboundControlSetup`, and forwards the result dict to
    :func:`~ansible.module_utils.basic.AnsibleModule.exit_json`.

    This function is the canonical Ansible module entry point and is also
    invoked when the file is executed directly (``__name__ == "__main__"``).
    """
    argument_spec: dict[str, Any] = dict(
        conf_dir=dict(required=True, type="str"),
        certs=dict(required=True, type="dict"),
        owner=dict(required=False, type="str", default=_DEFAULT_OWNER),
        group=dict(required=False, type="str", default=_DEFAULT_GROUP),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    handler = UnboundControlSetup(module)
    result = handler.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
