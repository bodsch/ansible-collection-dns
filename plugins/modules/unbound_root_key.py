#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Ansible module: unbound_root_key
=================================

Updates the DNSSEC root trust anchor by invoking the distribution-specific
``unbound`` package helper script
(``/usr/lib/unbound/package-helper`` on Debian/Ubuntu,
``/usr/libexec/unbound-helper`` on other distributions).

The helper is called with the sub-command ``root_trust_anchor_update`` which
performs the same anchor refresh that the package post-install scriptlet does.

Idempotency strategy
--------------------
Before invoking the helper, the module creates a copy of the current anchor
file as a timestamped backup.  After the helper completes, it computes
SHA-256 digests of the pre- and post-run files (skipping comment lines that
carry volatile timestamps) and compares them:

* **Digests differ** → anchor was updated → ``changed=True``, backup removed.
* **Digests equal**  → anchor unchanged   → ``changed=False``, original
  restored from backup.

When ``force`` is ``true`` the digest comparison is skipped and the module
always reports ``changed=True`` on a successful run.

First-run behaviour
-------------------
When the anchor file does not yet exist no backup is created.  After a
successful helper run the new file's digest is compared to ``None``, which
always evaluates to ``changed=True``.

Author: Bodo Schulz <bodo@boone-schulz.de>
"""

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

import datetime
import grp
import os
import pwd
import shutil
from pathlib import Path
from typing import Any, Optional

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.utils import file_sha256

# ---------------------------------------------------------------------------
# Ansible module documentation
# ---------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: unbound_root_key
short_description: Update the DNSSEC root trust anchor via the unbound package helper.
version_added: "1.5.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Invokes the distribution-specific unbound package helper script with the
    C(root_trust_anchor_update) sub-command to refresh the DNSSEC root trust
    anchor file.
  - The helper binary is looked up at C(/usr/lib/unbound/package-helper)
    (Debian/Ubuntu) and C(/usr/libexec/unbound-helper) as a fallback.
  - Idempotent: compares SHA-256 digests of the anchor file before and after
    the helper run (ignoring comment lines) and only reports C(changed=True)
    when the content actually changed.
  - Supports Ansible check mode: the helper is not invoked in check mode.

options:
  anchor_file:
    description:
      - Path to the DNSSEC root trust anchor file managed by the helper
        (the C(auto-trust-anchor-file) value from C(unbound.conf)).
      - Used for pre/post digest comparison (idempotency) and ownership
        enforcement after a successful update.
    required: false
    type: str
    default: /var/lib/unbound/root.key
  owner:
    description:
      - POSIX user that should own the anchor file after an update.
      - Also validated for existence during input checks.
    required: false
    type: str
    default: unbound
  group:
    description:
      - POSIX group that should own the anchor file after an update.
    required: false
    type: str
    default: unbound
  force:
    description:
      - When C(true), skip the digest comparison and always report
        C(changed=True) after a successful helper run.
      - Useful to force downstream handlers to trigger even when the anchor
        content did not change.
    required: false
    type: bool
    default: false
"""

EXAMPLES = r"""
# Update anchor (idempotent via digest comparison)
- name: Update DNSSEC root trust anchor
  unbound_root_key:
    anchor_file: /var/lib/unbound/root.key
    owner: unbound
    group: unbound

# Force update and trigger handlers unconditionally
- name: Force DNSSEC root anchor update
  unbound_root_key:
    anchor_file: /var/lib/unbound/root.key
    force: true
"""

RETURN = r"""
failed:
  description: Whether the module encountered a fatal error.
  type: bool
  returned: always
changed:
  description: >
    True when the SHA-256 digest of the anchor file (ignoring comment lines)
    differs before and after the helper run, or when I(force) is C(true) and
    the helper succeeded.  False when digests are equal and I(force) is
    C(false).
  type: bool
  returned: always
msg:
  description: Human-readable status description or error message.
  type: str
  returned: always
rc:
  description: Return code of the helper subprocess.
  type: int
  returned: when the helper was executed
cmd:
  description: Argument vector that was executed.
  type: list
  returned: when the helper was executed
backup_file:
  description: >
    Path to the timestamped backup of the anchor file created before the
    helper run.  Present only when a backup was created and the anchor was
    not changed (i.e. it has been restored to this path).
  type: str
  returned: when a backup was created and the anchor was not changed
"""

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_ANCHOR_FILE: str = "/var/lib/unbound/root.key"
_DEFAULT_OWNER: str = "unbound"
_DEFAULT_GROUP: str = "unbound"

# Candidate helper binaries in preference order.
_HELPER_CANDIDATES: tuple[str, ...] = (
    "/usr/lib/unbound/package-helper",
    "/usr/libexec/unbound-helper",
)
_HELPER_SUBCOMMAND: str = "root_trust_anchor_update"

# ---------------------------------------------------------------------------
# Main module class
# ---------------------------------------------------------------------------


class UnboundRootKey:
    """Manages the invocation of the unbound package helper for anchor updates.

    Wraps the distribution-specific ``unbound`` package helper script and
    adds idempotency via pre/post SHA-256 digest comparison of the anchor
    file, safe timestamped backups, and POSIX ownership enforcement.

    Attributes:
        module:               The active :class:`AnsibleModule` instance.
        anchor_file:          Path to the DNSSEC root trust anchor file.
        owner:                POSIX user name for ownership enforcement.
        group:                POSIX group name for ownership enforcement.
        force:                Skip digest comparison when ``True``.
        unbound_helper_bin:   Resolved absolute path to the helper binary,
                              or ``None`` when neither candidate is found.
        unbound_helper_params: Sub-command string passed to the helper.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """Initialise the handler from an :class:`AnsibleModule` instance.

        Reads all parameters from *module* and resolves the path to the
        distribution-specific unbound helper binary by checking each entry
        in :data:`_HELPER_CANDIDATES` in order.

        Args:
            module: Fully initialised :class:`AnsibleModule`.
        """
        self.module: AnsibleModule = module

        self.anchor_file: str = module.params["anchor_file"]
        self.owner: str = module.params["owner"]
        self.group: str = module.params["group"]
        self.force: bool = module.params["force"]

        self.unbound_helper_bin: Optional[str] = self._resolve_helper()
        self.unbound_helper_params: str = _HELPER_SUBCOMMAND

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the anchor update workflow and return an Ansible result dict.

        Steps:

        1. Validate all inputs via :meth:`_validate_inputs`.
        2. Abort if no helper binary is found.
        3. Return a predictive check-mode result without executing anything.
        4. Create a timestamped backup of the existing anchor file, if any.
        5. Compute the SHA-256 digest of the anchor file before the run.
        6. Invoke the helper: ``<helper_bin> root_trust_anchor_update``.
        7. On helper failure: restore the backup and return ``failed=True``.
        8. Compare pre/post digests (unless ``force`` is ``True``):

           * Digests differ  → keep new file, remove backup, ``changed=True``.
           * Digests equal   → restore backup, ``changed=False``.

        Returns:
            A dictionary that always contains:

            * ``failed``      (bool)       – ``True`` on any error.
            * ``changed``     (bool)       – ``True`` when anchor was updated.
            * ``msg``         (str)        – Status or error description.
            * ``rc``          (int)        – Helper return code (when run).
            * ``cmd``         (list[str])  – Executed argument vector (when run).
            * ``backup_file`` (str)        – Backup path when unchanged (when applicable).
        """
        self._validate_inputs()

        if not self.unbound_helper_bin:
            return dict(
                rc=1,
                failed=True,
                changed=False,
                msg=(
                    "No unbound helper binary found. Checked: "
                    + ", ".join(_HELPER_CANDIDATES)
                ),
            )

        # Predictive exit: do not mutate system state in check mode.
        if self.module.check_mode:
            return dict(
                rc=0,
                failed=False,
                changed=True,
                msg="Check mode: helper would be executed.",
                cmd=[self.unbound_helper_bin, self.unbound_helper_params],
            )

        # Step 4/5: backup + pre-run digest.
        anchor_path = Path(self.anchor_file)
        backup_path: Optional[str] = self._create_backup(self.anchor_file)
        digest_before: Optional[str] = (
            file_sha256(Path(backup_path)) if backup_path else None
        )

        # Step 6: invoke the helper.
        cmd: list[str] = [self.unbound_helper_bin, self.unbound_helper_params]
        self.module.log(f"UnboundRootKey: running {cmd}")
        rc, out, err = self._exec(cmd)

        output_lines: list[str] = []
        for stream in (out, err):
            if stream:
                output_lines.extend(stream.splitlines())

        self.module.log(f"UnboundRootKey: rc={rc}, output={output_lines}")

        # Step 7: on failure, restore backup and abort.
        if rc != 0:
            if backup_path:
                self._restore_backup(backup_path, self.anchor_file)
            return dict(
                rc=rc,
                failed=True,
                changed=False,
                msg=output_lines,
                cmd=cmd,
            )

        # Step 8: digest comparison (skipped when force=True).
        digest_after: Optional[str] = file_sha256(anchor_path)

        if self.force:
            changed = True
        else:
            changed = digest_before != digest_after

        if changed:
            # New anchor file is good — remove backup, fix ownership.
            if backup_path:
                self._remove_backup(backup_path)
            self._ensure_ownership(anchor_path)
        else:
            # Anchor unchanged — restore original from backup.
            if backup_path:
                self._restore_backup(backup_path, self.anchor_file)

        msg: str = (
            "DNSSEC root anchor successfully updated."
            if changed
            else "DNSSEC root anchor already up-to-date."
        )

        result: dict[str, Any] = dict(
            rc=rc,
            failed=False,
            changed=changed,
            msg=msg,
            cmd=cmd,
        )
        if not changed and backup_path:
            result["backup_file"] = backup_path
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_helper(self) -> Optional[str]:
        """Locate the unbound package helper binary.

        Checks each path in :data:`_HELPER_CANDIDATES` in order and returns
        the first one that exists and is executable by the current process.

        Returns:
            Absolute path to the helper binary, or ``None`` when no candidate
            is found.
        """
        for candidate in _HELPER_CANDIDATES:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                self.module.log(f"UnboundRootKey: using helper '{candidate}'")
                return candidate
        return None

    def _create_backup(self, key_file: str) -> Optional[str]:
        """Create a timestamped copy of the anchor file.

        Copies *key_file* to a sibling path of the form
        ``<basename>_YYYYMMDD_HHMMSS<ext>`` using :func:`shutil.copy2` so
        that the original file remains in place and accessible to a
        concurrently starting unbound process.

        When *key_file* does not yet exist (first-run scenario) no backup is
        created and ``None`` is returned.

        Args:
            key_file: Absolute path to the anchor file to back up.

        Returns:
            Absolute path to the backup file on success, or ``None`` when
            the source file does not exist.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` if
            :func:`shutil.copy2` raises :exc:`OSError`.
        """
        src = Path(key_file)
        if not src.exists():
            self.module.log(
                f"UnboundRootKey: '{key_file}' does not exist, skipping backup."
            )
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        basename, ext = os.path.splitext(key_file)
        backup = f"{basename}_{timestamp}{ext}"

        try:
            shutil.copy2(key_file, backup)
            self.module.log(f"UnboundRootKey: backup created at '{backup}'")
            return backup
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to create backup of '{key_file}': {exc}")

    def _restore_backup(self, backup_path: str, target: str) -> None:
        """Restore an anchor file from its backup.

        Moves *backup_path* back to *target*, replacing any file that the
        helper may have written there.  Used both on helper failure and when
        the digest comparison shows no change.

        Args:
            backup_path: Absolute path to the backup file.
            target:      Absolute path to restore the file to.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` if
            :func:`shutil.move` raises :exc:`OSError`.
        """
        try:
            shutil.move(backup_path, target)
            self.module.log(f"UnboundRootKey: restored '{backup_path}' → '{target}'")
        except OSError as exc:
            self.module.fail_json(
                msg=f"Failed to restore backup '{backup_path}' to '{target}': {exc}"
            )

    def _remove_backup(self, backup_path: str) -> None:
        """Delete a backup file after a successful anchor update.

        Called when the anchor content has changed and the new file has been
        accepted — the backup is no longer needed.

        Args:
            backup_path: Absolute path to the backup file to delete.

        Raises:
            Does not raise Python exceptions.  Logs a warning if the file
            cannot be removed but does not abort the module.
        """
        try:
            os.unlink(backup_path)
            self.module.log(f"UnboundRootKey: backup '{backup_path}' removed.")
        except OSError as exc:
            self.module.warn(f"Could not remove backup file '{backup_path}': {exc}")

    def _validate_inputs(self) -> None:
        """Validate all module inputs before any mutating operations.

        Checks:

        * ``anchor_file`` – its parent directory must exist, be a directory,
          and be writable by the current process.  This catches the common
          misconfiguration where the helper exits successfully but cannot
          write the anchor file because the target directory is missing.
        * ``owner`` – must resolve to an existing POSIX user via
          :func:`pwd.getpwnam`.
        * ``group`` – must resolve to an existing POSIX group via
          :func:`grp.getgrnam`.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` on
            the first error encountered, which terminates the module
            immediately.
        """
        self.module.log("UnboundRootKey::_validate_inputs()")

        anchor_parent = Path(self.anchor_file).parent

        if not anchor_parent.exists():
            self.module.fail_json(
                msg=(
                    f"anchor_file parent directory '{anchor_parent}' does not "
                    "exist. Create it and ensure the unbound user owns it "
                    "before running this module."
                )
            )

        if not anchor_parent.is_dir():
            self.module.fail_json(
                msg=(
                    f"anchor_file parent '{anchor_parent}' exists but is "
                    "not a directory."
                )
            )

        if not os.access(anchor_parent, os.W_OK):
            self.module.fail_json(
                msg=(
                    f"anchor_file parent directory '{anchor_parent}' is not "
                    "writable by the current process. "
                    f"Check ownership and permissions: "
                    f"{oct(anchor_parent.stat().st_mode)}"
                )
            )

        self.module.log(f"anchor_file parent '{anchor_parent}' exists and is writable.")

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
            :func:`shutil.chown` raises :exc:`OSError`.
        """
        try:
            shutil.chown(str(path), self.owner, self.group)
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to set ownership on '{path}': {exc}")

    def _exec(self, commands: list[str]) -> tuple[int, str, str]:
        """Run an external command through the Ansible module subprocess wrapper.

        Uses ``check_rc=False`` so non-zero exit codes are handled by the
        caller rather than raising an exception here.

        Args:
            commands: Argument vector; ``commands[0]`` must be an absolute
                      path to an executable.

        Returns:
            Three-tuple ``(return_code, stdout, stderr)`` – both output
            strings may be empty but are never ``None``.
        """
        rc, out, err = self.module.run_command(commands, check_rc=False)
        return rc, out, err


# ---------------------------------------------------------------------------
# Ansible entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Define the module argument spec and dispatch to :class:`UnboundRootKey`.

    This function is the canonical Ansible module entry point and is also
    invoked when the file is executed directly (``__name__ == "__main__"``).
    """
    argument_spec: dict[str, Any] = dict(
        anchor_file=dict(required=False, type="str", default=_DEFAULT_ANCHOR_FILE),
        owner=dict(required=False, type="str", default=_DEFAULT_OWNER),
        group=dict(required=False, type="str", default=_DEFAULT_GROUP),
        force=dict(required=False, type="bool", default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    handler = UnboundRootKey(module)
    result = handler.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
