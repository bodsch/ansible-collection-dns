#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Ansible module: unbound_anchor
================================

Invokes ``unbound-anchor`` to update the DNSSEC root trust anchor used by
unbound.  Optionally downloads the IANA root-anchor bundle files and verifies
their cryptographic signature before running the update binary.

Workflow (when ``iana_verify: true``)
--------------------------------------
1. Ensure the three IANA anchor files are present in *iana_dir*
   (download missing ones, or all when ``force_download: true``):

   * ``root-anchors.xml``  – the signed root anchor document
   * ``root-anchors.p7s``  – detached PKCS#7/DER signature over the XML
   * ``icannbundle.pem``   – ICANN CA bundle used to verify the signature

2. Verify the signature::

       openssl smime -verify \\
           -in  <iana_dir>/root-anchors.p7s -inform DER \\
           -content <iana_dir>/root-anchors.xml \\
           -CAfile  <iana_dir>/icannbundle.pem

3. Run the anchor update::

       unbound-anchor [-v] [-F] -C <config>

Return-code semantics of ``unbound-anchor``
-------------------------------------------
* **0** – The root anchor was successfully verified or updated.
* **1** – The anchor could not be updated; the existing anchor file (if any)
  was left in place.

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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.dns.plugins.module_utils.utils import file_sha256

# ---------------------------------------------------------------------------
# Ansible module documentation
# ---------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: unbound_anchor
short_description: Update the DNSSEC root trust anchor via unbound-anchor.
version_added: "1.5.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Runs C(unbound-anchor) to verify or force-update the DNSSEC root trust
    anchor required by unbound.
  - When I(iana_verify) is C(true), downloads the IANA root-anchor bundle
    files if they are missing (or always when I(force_download) is C(true))
    and verifies the PKCS#7 signature via C(openssl smime) before invoking
    C(unbound-anchor).
  - Supports Ansible check mode: no binary is invoked and no file is written.

options:
  config:
    description:
      - Path to the unbound configuration file.
      - Passed as C(-C <config>) to C(unbound-anchor).
    required: false
    type: str
    default: /etc/unbound/unbound.conf
  params:
    description:
      - List of additional CLI flags forwarded verbatim to C(unbound-anchor).
      - Inserted between the binary name and the mandatory C(-C) flag.
    required: false
    type: list
    elements: str
    default:
      - -v
      - -F
  owner:
    description: POSIX user validated during input checks.
    required: false
    type: str
    default: unbound
  group:
    description: POSIX group validated during input checks.
    required: false
    type: str
    default: unbound
  iana_verify:
    description:
      - When C(true), download missing IANA anchor files and verify their
        PKCS#7 signature before running C(unbound-anchor).
      - Requires C(openssl) to be present on the target host.
    required: false
    type: bool
    default: false
  iana_dir:
    description:
      - Directory used to store the downloaded IANA anchor files.
      - Defaults to the directory that contains I(config).
    required: false
    type: str
    default: ""
  force_download:
    description:
      - Re-download all IANA anchor files even when they already exist on
        disk.  Only effective when I(iana_verify) is C(true).
    required: false
    type: bool
    default: false
  download_timeout:
    description:
      - HTTP connection and read timeout in seconds for each IANA file
        download.  Only effective when I(iana_verify) is C(true).
    required: false
    type: int
    default: 30
  anchor_file:
    description:
      - Path to the DNSSEC root trust anchor file written by C(unbound-anchor)
        (the C(auto-trust-anchor-file) value from C(unbound.conf)).
      - When provided, the module computes a SHA-256 digest of this file
        before and after invoking C(unbound-anchor) and sets C(changed=True)
        only when the digest differs.  This makes the module fully idempotent.
      - When omitted the module cannot detect whether the anchor file actually
        changed and conservatively reports C(changed=True) on every successful
        run (rc=0).  A warning is emitted in this case.
    required: false
    type: str
    default: ""
"""

EXAMPLES = r"""
# Minimal: replicate the original shell task (changed is always True on success)
- name: Force DNSSEC root anchor update
  unbound_anchor:
    config: /etc/unbound/unbound.conf

# Idempotent: changed=True only when the anchor file actually changed on disk
- name: Force DNSSEC root anchor update (idempotent)
  unbound_anchor:
    config: /etc/unbound/unbound.conf
    anchor_file: /var/lib/unbound/root.key

# Download + verify IANA bundle, then update (idempotent)
- name: Verify IANA bundle and update anchor
  unbound_anchor:
    config: /etc/unbound/unbound.conf
    anchor_file: /var/lib/unbound/root.key
    iana_verify: true
    iana_dir: /etc/unbound/iana
    owner: unbound
    group: unbound

# Force re-download of IANA files (e.g. after suspected tampering)
- name: Force IANA bundle refresh and anchor update
  unbound_anchor:
    config: /etc/unbound/unbound.conf
    anchor_file: /var/lib/unbound/root.key
    iana_verify: true
    force_download: true
"""

RETURN = r"""
failed:
  description: Whether the module encountered a fatal error.
  type: bool
  returned: always
changed:
  description: >
    When I(anchor_file) is provided: C(true) only when the SHA-256 digest of
    the anchor file differs before and after the C(unbound-anchor) run, or
    when at least one IANA file was downloaded.
    When I(anchor_file) is omitted: C(true) on every successful run (rc=0)
    or when at least one IANA file was downloaded (non-idempotent fallback).
  type: bool
  returned: always
msg:
  description: >
    Human-readable status description or, on failure, combined stdout/stderr
    split into lines.
  type: str or list
  returned: always
rc:
  description: Return code of the last subprocess invoked.
  type: int
  returned: when a subprocess was executed
cmd:
  description: Argument vector of the last subprocess invoked.
  type: list
  returned: when a subprocess was executed
downloaded_files:
  description: List of IANA file names that were (re-)downloaded.
  type: list
  returned: when iana_verify is true and at least one file was downloaded
anchor_file_changed:
  description: >
    Whether the anchor file digest changed during the run.
    Only present when I(anchor_file) is provided.
  type: bool
  returned: when anchor_file is provided and unbound-anchor was executed
"""

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: str = "/etc/unbound/unbound.conf"
_DEFAULT_OWNER: str = "unbound"
_DEFAULT_GROUP: str = "unbound"
_DEFAULT_PARAMS: list[str] = ["-v", "-F"]
_DEFAULT_TIMEOUT: int = 30
_DEFAULT_ANCHOR_FILE: str = ""

_IANA_BASE_URL: str = "https://data.iana.org/root-anchors"

# Ordered: XML and PEM must be present before the .p7s verification step.
_IANA_FILES: dict[str, str] = {
    "root-anchors.xml": f"{_IANA_BASE_URL}/root-anchors.xml",
    "root-anchors.p7s": f"{_IANA_BASE_URL}/root-anchors.p7s",
    "icannbundle.pem": f"{_IANA_BASE_URL}/icannbundle.pem",
}

# ---------------------------------------------------------------------------
# Main module class
# ---------------------------------------------------------------------------


class UnboundAnchor:
    """Manages the invocation of ``unbound-anchor``.

    Optionally downloads and verifies the IANA root-anchor bundle before
    running the update binary.

    Attributes:
        module:           The active :class:`AnsibleModule` instance.
        config:           Absolute path to the unbound configuration file.
        params:           Extra CLI flags for ``unbound-anchor``.
        owner:            POSIX user name validated during input checks.
        group:            POSIX group name validated during input checks.
        iana_verify:      Whether to download and verify the IANA bundle.
        iana_dir:         Directory for IANA anchor files.
        force_download:   Re-download files even when already present.
        download_timeout: Per-file HTTP timeout in seconds.
        anchor_file:      Path to the trust anchor file written by
                          ``unbound-anchor`` (``auto-trust-anchor-file`` in
                          ``unbound.conf``).  Empty string when not provided.
        unbound_bin:      Resolved path to ``unbound-anchor``, or ``None``.
        openssl_bin:      Resolved path to ``openssl``, or ``None``.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """Initialise the anchor handler from an :class:`AnsibleModule` instance.

        Reads all parameters from *module* and resolves the paths to the
        ``unbound-anchor`` and ``openssl`` binaries.

        Args:
            module: Fully initialised :class:`AnsibleModule`.
        """
        self.module: AnsibleModule = module

        self.config: str = module.params["config"]
        self.params: list[str] = module.params["params"] or []
        self.owner: str = module.params["owner"]
        self.group: str = module.params["group"]
        self.iana_verify: bool = module.params["iana_verify"]
        self.force_download: bool = module.params["force_download"]
        self.download_timeout: int = module.params["download_timeout"]
        self.anchor_file: str = module.params.get("anchor_file") or ""

        # Resolve iana_dir: explicit value or fall back to dirname(config).
        iana_dir_param: str = module.params.get("iana_dir") or ""
        self.iana_dir: Path = (
            Path(iana_dir_param) if iana_dir_param else Path(self.config).parent
        )

        self.unbound_bin: Optional[str] = module.get_bin_path("unbound-anchor", False)
        self.openssl_bin: Optional[str] = module.get_bin_path("openssl", False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the full anchor update workflow.

        Steps:

        1. Validate all inputs via :meth:`_validate_inputs`.
        2. Abort if ``unbound-anchor`` binary is missing.
        3. Return predictive check-mode result without executing anything.
        4. If ``iana_verify`` is enabled:

           a. :meth:`_download_iana_files` – fetch missing (or all) IANA files.
           b. :meth:`_verify_iana_bundle`  – verify PKCS#7 signature via openssl.

        5. Build and invoke ``unbound-anchor``.
        6. Map rc=0 → ``changed=True``, rc≠0 → ``failed=True``.

        Returns:
            Dictionary with at minimum:

            * ``failed``           (bool)
            * ``changed``          (bool)
            * ``msg``              (str | list[str])
            * ``rc``               (int)   – when a subprocess ran
            * ``cmd``              (list)  – when a subprocess ran
            * ``downloaded_files`` (list)  – when files were downloaded
        """
        self._validate_inputs()

        if not self.unbound_bin:
            return dict(
                rc=1,
                failed=True,
                changed=False,
                msg="'unbound-anchor' binary not found on $PATH.",
            )

        # Predictive exit: do not mutate system state in check mode.
        if self.module.check_mode:
            return dict(
                rc=0,
                failed=False,
                changed=True,
                msg="Check mode: 'unbound-anchor' would be executed.",
                cmd=[self.unbound_bin] + self.params + ["-C", self.config],
            )

        # Accumulate downloaded file names across both helper calls so the
        # list is always complete in the final result dict, even on error.
        downloaded_files: list[str] = []

        if self.iana_verify:
            # Step 1: ensure all IANA anchor files are present.
            dl_result = self._download_iana_files(self.iana_dir, downloaded_files)
            if dl_result is not None:
                return dl_result

            # Step 2: cryptographically verify the bundle before trusting it.
            verify_result = self._verify_iana_bundle(self.iana_dir)
            if verify_result is not None:
                return verify_result

        # Step 3: capture anchor file digest BEFORE the run for idempotency.
        anchor_path: Optional[Path] = (
            Path(self.anchor_file) if self.anchor_file else None
        )
        digest_before: Optional[str] = file_sha256(anchor_path) if anchor_path else None

        if anchor_path is None:
            self.module.warn(
                "unbound_anchor: 'anchor_file' is not set. "
                "The module cannot detect whether the anchor actually changed "
                "and will report changed=True on every successful run. "
                "Set 'anchor_file' to the 'auto-trust-anchor-file' value "
                "from unbound.conf for fully idempotent behaviour."
            )

        # Step 4: run unbound-anchor.
        cmd: list[str] = [self.unbound_bin] + self.params + ["-C", self.config]
        self.module.log(f"UnboundAnchor: running {cmd}")

        rc, out, err = self._exec(cmd)

        self.module.log(f" rc: {rc}")

        output_lines: list[str] = []
        for stream in (out, err):
            if stream:
                output_lines.extend(stream.splitlines())

        self.module.log(f"UnboundAnchor: rc={rc}, output={output_lines}")

        # Exit-code semantics of unbound-anchor (empirically verified):
        #   rc=0 – anchor is already valid, no update was necessary
        #   rc=1 – anchor was successfully updated (e.g. via -F or RFC 5011)
        #   rc>1 – a genuine error occurred (network failure, parse error, …)
        if rc > 1:
            result: dict[str, Any] = dict(
                rc=rc,
                failed=True,
                changed=bool(downloaded_files),
                msg=output_lines,
                cmd=cmd,
            )

            if downloaded_files:
                result["downloaded_files"] = downloaded_files

            return result

        # Step 5: determine changed via digest comparison (or fallback).
        if anchor_path is not None:
            digest_after: Optional[str] = file_sha256(anchor_path)
            anchor_file_changed: bool = digest_before != digest_after
            changed: bool = anchor_file_changed or bool(downloaded_files)
        else:
            # No anchor_file given — fall back to conservative changed=True.
            anchor_file_changed = True
            changed = True

        msg: str = (
            "DNSSEC root anchor successfully updated."
            if anchor_file_changed
            else "DNSSEC root anchor already up-to-date."
        )

        result = dict(
            rc=rc,
            failed=False,
            changed=changed,
            msg=msg,
            cmd=cmd,
            anchor_file_changed=anchor_file_changed,
        )
        if downloaded_files:
            result["downloaded_files"] = downloaded_files
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> None:
        """Validate all module inputs before any mutating operations.

        Checks:

        * ``config``      – if it exists on disk it must be a regular file.
        * ``anchor_file`` – if provided, its parent directory must exist, be a
          directory, and be writable by the current process.  This catches the
          common misconfiguration where ``unbound-anchor`` silently exits with
          rc=0 but never writes the file because the target directory does not
          exist.
        * ``iana_dir``    – if ``iana_verify`` is enabled the path must not
          exist as a non-directory inode.
        * ``openssl``     – binary must be found when ``iana_verify`` is enabled.
        * ``owner`` / ``group`` – must resolve to known POSIX entities.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` on
            the first error encountered.
        """
        self.module.log("UnboundAnchor::_validate_inputs()")

        config_path = Path(self.config)
        if config_path.exists() and not config_path.is_file():
            self.module.fail_json(
                msg=(
                    f"config '{self.config}' already exists but is not "
                    "a regular file."
                )
            )

        if config_path.is_file():
            try:
                self.module.log(
                    f"'{config_path}' is owned by "
                    f"{config_path.owner()}:{config_path.group()}"
                )
            except (KeyError, PermissionError) as exc:
                self.module.log(
                    f"Could not determine ownership of '{config_path}': {exc}"
                )

        # Validate anchor_file parent directory when the parameter is set.
        if self.anchor_file:
            anchor_parent = Path(self.anchor_file).parent

            if not anchor_parent.exists():
                self.module.fail_json(
                    msg=(
                        f"anchor_file parent directory '{anchor_parent}' does "
                        "not exist. Create it and ensure 'unbound' owns it "
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
                        f"anchor_file parent directory '{anchor_parent}' is "
                        "not writable by the current process. "
                        f"Check ownership and permissions: "
                        f"{oct(anchor_parent.stat().st_mode)}"
                    )
                )

            self.module.log(
                f"anchor_file parent '{anchor_parent}' exists and is writable."
            )

        if self.iana_verify:
            if self.iana_dir.exists() and not self.iana_dir.is_dir():
                self.module.fail_json(
                    msg=(
                        f"iana_dir '{self.iana_dir}' already exists but is "
                        "not a directory."
                    )
                )
            if not self.openssl_bin:
                self.module.fail_json(
                    msg=(
                        "'openssl' binary not found on $PATH. "
                        "It is required when iana_verify is true."
                    )
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

    def _download_iana_files(
        self,
        anchor_dir: Path,
        downloaded: list[str],
    ) -> Optional[dict[str, Any]]:
        """Download missing (or all) IANA root-anchor files.

        Downloads the three files required for bundle verification:

        * ``root-anchors.xml``
        * ``root-anchors.p7s``
        * ``icannbundle.pem``

        Each file is fetched only when it is absent from *anchor_dir*, unless
        ``force_download`` is ``True``.  Downloads are written atomically: the
        content is first saved to a ``.tmp`` sibling file and renamed to the
        final name only on success, so a failed transfer never leaves a
        truncated file in place.

        Args:
            anchor_dir:  Directory in which to store the downloaded files.
                         Created (including parents) if it does not exist.
            downloaded:  Mutable list that receives the name of every file
                         that was actually (re-)downloaded.  Modified in-place
                         so :meth:`run` can include the list in the result
                         dict even when an error occurs mid-way.

        Returns:
            ``None`` when all required files are present.
            A result dictionary (``failed=True``) on any download or I/O
            error; :meth:`run` should return this dict immediately.
        """
        self.module.log(f"UnboundAnchor: checking IANA files in '{anchor_dir}'")

        try:
            anchor_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return dict(
                failed=True,
                changed=False,
                msg=f"Cannot create iana_dir '{anchor_dir}': {exc}",
            )

        for filename, url in _IANA_FILES.items():
            dest = anchor_dir / filename

            if dest.exists() and not self.force_download:
                self.module.log(
                    f"UnboundAnchor: '{filename}' already present, skipping."
                )
                continue

            self.module.log(f"UnboundAnchor: downloading '{url}' → '{dest}'")
            tmp = dest.with_suffix(dest.suffix + ".tmp")

            try:
                with urllib.request.urlopen(
                    url, timeout=self.download_timeout
                ) as response:
                    tmp.write_bytes(response.read())

                tmp.replace(dest)
                downloaded.append(filename)
                self.module.log(f"UnboundAnchor: '{filename}' downloaded successfully.")

            except urllib.error.URLError as exc:
                tmp.unlink(missing_ok=True)
                return dict(
                    failed=True,
                    changed=bool(downloaded),
                    msg=f"Failed to download '{url}': {exc}",
                    downloaded_files=downloaded,
                )
            except OSError as exc:
                tmp.unlink(missing_ok=True)
                return dict(
                    failed=True,
                    changed=bool(downloaded),
                    msg=f"I/O error writing '{dest}': {exc}",
                    downloaded_files=downloaded,
                )

        return None

    def _verify_iana_bundle(self, anchor_dir: Path) -> Optional[dict[str, Any]]:
        """Verify the IANA root-anchor PKCS#7 signature via ``openssl smime``.

        Runs::

            openssl smime -verify \\
                -in      <anchor_dir>/root-anchors.p7s  -inform DER \\
                -content <anchor_dir>/root-anchors.xml \\
                -CAfile  <anchor_dir>/icannbundle.pem

        This confirms that ``root-anchors.p7s`` is a valid DER-encoded PKCS#7
        signature over ``root-anchors.xml`` made by a certificate whose chain
        of trust is rooted in ``icannbundle.pem``.

        Args:
            anchor_dir: Directory containing the three IANA anchor files.

        Returns:
            ``None`` when verification succeeds (openssl rc=0).
            A result dictionary (``failed=True``) when verification fails or
            when the subprocess cannot be started.
        """
        p7s = anchor_dir / "root-anchors.p7s"
        xml = anchor_dir / "root-anchors.xml"
        pem = anchor_dir / "icannbundle.pem"

        cmd: list[str] = [
            self.openssl_bin,
            "smime",
            "-verify",
            "-in",
            str(p7s),
            "-inform",
            "DER",
            "-content",
            str(xml),
            "-CAfile",
            str(pem),
        ]

        self.module.log(f"UnboundAnchor: verifying IANA bundle: {cmd}")
        rc, out, err = self._exec(cmd)

        output_lines: list[str] = []
        for stream in (out, err):
            if stream:
                output_lines.extend(stream.splitlines())

        if rc != 0:
            self.module.log(
                f"UnboundAnchor: bundle verification failed (rc={rc}): "
                f"{output_lines}"
            )
            return dict(
                rc=rc,
                failed=True,
                changed=False,
                msg=["IANA bundle verification failed."] + output_lines,
                cmd=cmd,
            )

        self.module.log("UnboundAnchor: IANA bundle verified successfully.")
        return None

    def _ensure_ownership(self, path: Path) -> None:
        """Apply POSIX ownership (``chown``) to a single path.

        Args:
            path: Filesystem path whose ownership should be updated to
                  ``self.owner``/``self.group``.

        Raises:
            Does not raise Python exceptions.  Calls
            :meth:`~ansible.module_utils.basic.AnsibleModule.fail_json` if
            :func:`shutil.chown` raises :exc:`OSError`.

        Note:
            Retained for potential use by subclasses or future extensions
            (e.g. fixing ownership of downloaded IANA files).
        """
        try:
            shutil.chown(str(path), self.owner, self.group)
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to set ownership on '{path}': {exc}")

    def _exec(self, commands: list[str]) -> tuple[int, str, str]:
        """Run an external command through the Ansible module subprocess wrapper.

        Uses ``check_rc=False`` so non-zero exit codes are handled by the
        caller.

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
    """Define the module argument spec and dispatch to :class:`UnboundAnchor`.

    This function is the canonical Ansible module entry point and is also
    invoked when the file is executed directly (``__name__ == "__main__"``).
    """
    argument_spec: dict[str, Any] = dict(
        config=dict(
            required=False,
            type="str",
            default=_DEFAULT_CONFIG,
        ),
        params=dict(
            required=False,
            type="list",
            elements="str",
            default=_DEFAULT_PARAMS,
        ),
        owner=dict(required=False, type="str", default=_DEFAULT_OWNER),
        group=dict(required=False, type="str", default=_DEFAULT_GROUP),
        iana_verify=dict(required=False, type="bool", default=False),
        iana_dir=dict(required=False, type="str", default=""),
        force_download=dict(required=False, type="bool", default=False),
        download_timeout=dict(required=False, type="int", default=_DEFAULT_TIMEOUT),
        anchor_file=dict(required=False, type="str", default=_DEFAULT_ANCHOR_FILE),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    handler = UnboundAnchor(module)
    result = handler.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
