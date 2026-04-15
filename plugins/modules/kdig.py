#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function

import hashlib
import json
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: kdig
short_description: Maintain a trusted DNSKEY file (trust anchor) using kdig
version_added: "0.9.0"
author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Queries DNSKEY records for the root zone (C(.)) using C(kdig).
  - Filters DNSKEY records by the configured flag value (typically C(257) for KSK).
  - Writes the matching records to a trust key file in a deterministic order to ensure idempotency.
  - Persists a SHA-256 checksum and only rewrites the trust key file when the checksum changes.
  - If the trust key file already exists and needs to be updated, it is renamed with a timestamp suffix as a backup.

options:
  root_dns:
    description:
      - Root DNS server to query (kdig target after C(@)).
      - Use any root server name or IP (for example C(k.root-servers.net) or C(198.41.0.4)).
    type: str
    required: false
    default: k.root-servers.net

  signing_key:
    description:
      - DNSKEY flag value to select from the response.
      - Typical values are C(257) (KSK) or C(256) (ZSK), depending on your use case.
    type: int
    required: false
    default: 257

  trust_keyfile:
    description:
      - Path to the trusted DNSKEY file to manage.
      - The file content will be replaced atomically when updates are required.
    type: str
    required: false
    default: /etc/trusted-key.key

  parameters:
    description:
      - Additional parameters appended to the C(kdig) invocation.
      - Use this to pass transport and formatting options (for example C(+tcp), C(+timeout=2), C(+retry=3), C(+json)).
      - JSON output (C(+json)) is preferred for robust parsing; if not provided, the module will attempt JSON first and fall back to text parsing.
    type: list
    elements: str
    required: false

notes:
  - Check mode is supported.
  - The checksum file path is fixed to C(/etc/.trusted-key.key.checksum) by the module implementation.
  - Requires the C(kdig) executable on the target host.

requirements:
  - kdig (Knot DNS utilities)
"""

EXAMPLES = r"""
- name: Maintain root trust anchor file using default root server
  bodsch.dns.kdig:
    trust_keyfile: /etc/trusted-key.key

- name: Prefer JSON output and use TCP with custom timeouts
  bodsch.dns.kdig:
    root_dns: k.root-servers.net
    signing_key: 257
    trust_keyfile: /etc/trusted-key.key
    parameters:
      - +json
      - +tcp
      - +timeout=2
      - +retry=3

- name: Use a specific root server IP
  bodsch.dns.kdig:
    root_dns: 198.41.0.4
    trust_keyfile: /etc/trusted-key.key
"""

RETURN = r"""
changed:
  description:
    - Whether the trust key file was updated.
  returned: always
  type: bool

failed:
  description:
    - Indicates failure (for example, kdig is missing, kdig execution failed, or no matching DNSKEY records were found).
  returned: always
  type: bool

msg:
  description:
    - Human readable status or error message.
  returned: always
  type: str
  sample:
    - "/etc/trusted-key.key successfully updated"
    - "/etc/trusted-key.key is up-to-date"
    - "no installed kdig found"
    - "No DNSKEY records with flags 257 found in kdig output."

rc:
  description:
    - Return code when the module fails before running normal processing (for example missing kdig).
  returned: sometimes
  type: int
  sample: 1
"""


# ---------------------------------------------------------------------------------------


class AnsibleModuleLike(Protocol):
    """Typing contract for the minimal AnsibleModule API used by this helper.

    The real AnsibleModule provides a much larger surface. This protocol intentionally
    declares only the attributes and methods that are accessed by this module, to
    improve static type checking without coupling to Ansible internals.
    """

    params: Mapping[str, Any]
    check_mode: bool

    def get_bin_path(self, arg: str, required: bool = False) -> Optional[str]:
        pass

    def run_command(
        self, args: Sequence[str], check_rc: bool = True
    ) -> Tuple[int, str, str]:
        pass

    def log(self, msg: str = "", **kwargs: Any) -> None:
        pass


class Kdig(object):
    """Maintain a trusted DNSKEY file using `kdig`.

    The module queries DNSKEY records (typically for the root zone) from a configured
    root server, selects the records matching `signing_key` (e.g. 257 for KSK), and
    writes them to `trust_keyfile` in a canonical, deterministic order.

    To support idempotent Ansible runs, a SHA-256 checksum of the canonical content is
    persisted in `trust_keyfile_checksum` and compared on subsequent runs.

    JSON output (`+json`) is preferred when available because it allows robust parsing.
    The implementation falls back to parsing textual `+answer` output for older kdig
    builds that do not support JSON.
    """

    module = None

    def __init__(self, module: AnsibleModuleLike):
        """Initialize helper state from Ansible module parameters.

        Args:
          module: The Ansible module instance (or a compatible object) providing
            parameter access, logging, and command execution.
        """
        self.module = module

        self.module.log("Kdig::__init__()")

        self._kdig_bin = module.get_bin_path("kdig", True)

        self.root_dns = module.params.get("root_dns")
        self.signing_key = module.params.get("signing_key")
        self.trust_keyfile = module.params.get("trust_keyfile")
        self.parameters = module.params.get("parameters")

        self.trust_keyfile_checksum = "/etc/.trusted-key.key.checksum"

    def run(self) -> Dict[str, Any]:
        """Execute the DNSKEY query and update trust files if required.

        Workflow:
          1. Read the previously stored checksum (if present).
          2. Query DNSKEY records using `kdig` (prefer JSON mode).
          3. Extract and canonically sort all DNSKEY records with the configured
             `signing_key`.
          4. Compute a SHA-256 checksum over the canonical content.
          5. If the checksum differs, back up the previous trust file and atomically
             write the new trust file and checksum.

        Returns:
          An Ansible-style result dictionary suitable for `exit_json()`.
        """
        self.module.log("Kdig::run()")

        result: Dict[str, Any] = dict(failed=True, ansible_module_results="failed")

        _checksum = ""
        _old_checksum = ""

        if not self._kdig_bin:
            return dict(rc=1, failed=True, msg="no installed kdig found")

        if os.path.isfile(self.trust_keyfile_checksum):
            with open(self.trust_keyfile_checksum, "r", encoding="utf-8") as fp:
                # Normalize to avoid newline-related false positives.
                _old_checksum = fp.readline().strip()

        self.module.log(f"  - _old_checksum: {_old_checksum}")

        args: List[str] = []
        args.append(self._kdig_bin)
        args.append("DNSKEY")
        args.append(".")
        args.append(f"@{self.root_dns}")
        args.append("+noall")
        args.append("+answer")

        params: List[str] = (
            [str(x) for x in self.parameters]
            if isinstance(self.parameters, list)
            else []
        )
        has_json = "+json" in params

        # Preferred execution: JSON output (deterministic parsing + sorting).
        json_args = args + (params if has_json else (["+json"] + params))

        # Fallback execution: plain +answer output (older kdig versions may not support +json).
        text_args = args + ([p for p in params if p != "+json"] if has_json else params)

        rc, out, err = self._exec(json_args)
        if rc != 0 and json_args != text_args:
            self.module.log(
                msg=f"  - kdig JSON mode failed, retrying without +json: {err}"
            )
            rc, out, err = self._exec(text_args)

        if rc == 0:
            # Prefer JSON parsing. If JSON is not available (older kdig) or parsing fails,
            # fall back to the textual regex approach.
            matches = self._extract_dnskeys(out)

            if not matches:
                return dict(
                    failed=True,
                    changed=False,
                    msg=f"No DNSKEY records with flags {self.signing_key} found in kdig output.",
                )

            # Canonical representation for stable checksums and file content.
            dnskey = "\n".join(matches) + "\n"

            _checksum = self.__checksum(dnskey)

            self.module.log(f"  - _checksum: {_checksum}")

            if _old_checksum != _checksum:
                """
                rename old trust file
                """
                self.module.log("  - changed ...")

                if self.module.check_mode:
                    return dict(
                        failed=False,
                        changed=True,
                        msg=f"{self.trust_keyfile} would be updated (check mode).",
                    )

                if os.path.isfile(self.trust_keyfile):
                    date_string = time.strftime("%Y%m%d%H%M%S")
                    _trust_keyfile_backup = f"{self.trust_keyfile}_{date_string}"

                    os.rename(self.trust_keyfile, _trust_keyfile_backup)

                self._atomic_write(self.trust_keyfile, dnskey)

                """
                  persist checksum
                """
                self._atomic_write(self.trust_keyfile_checksum, _checksum + "\n")

                result = dict(
                    failed=False,
                    changed=True,
                    msg=f"{self.trust_keyfile} successfully updated",
                )
            else:
                result = dict(
                    failed=False,
                    changed=False,
                    msg=f"{self.trust_keyfile} is up-to-date",
                )

        else:
            result = dict(
                failed=True,
                changed=False,
                msg=err or "kdig execution failed",
            )

        return result

    def _extract_dnskeys(self, out: str) -> List[str]:
        """Extract matching DNSKEY records from kdig output.

        The function prefers kdig's JSON output (+json) and falls back to parsing the
        textual +answer output for older kdig versions.

        Returns:
          A canonical, deterministic list of DNSKEY record lines.
        """
        obj = self._parse_kdig_json(out)
        if obj is not None:
            records = self._dnskeys_from_json(obj)
            if records:
                return records
        return self._dnskeys_from_text(out)

    def _parse_kdig_json(self, out: str) -> Optional[Dict[str, Any]]:
        """Parse kdig JSON output.

        kdig typically prints a single JSON object. Some builds may include non-JSON
        noise; therefore we extract the first '{' .. last '}' block and parse it.
        """
        start = out.find("{")
        end = out.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        payload = out[start : end + 1]
        try:
            parsed = json.loads(payload)
        except Exception:
            return None

        return parsed if isinstance(parsed, dict) else None

    def _dnskeys_from_json(self, obj: Dict[str, Any]) -> List[str]:
        """Extract matching DNSKEY records from a parsed kdig JSON object."""
        answers = obj.get("answerRRs")
        if not isinstance(answers, list):
            return []

        extracted: List[Tuple[int, int, int, str, str]] = []
        # tuple: (flags, protocol, algorithm, key, rendered_line)

        for rr in answers:
            if not isinstance(rr, dict):
                continue

            if rr.get("TYPEname") != "DNSKEY":
                continue

            rdata = rr.get("rdataDNSKEY")
            if not isinstance(rdata, str):
                continue

            parts = rdata.split()
            if len(parts) < 4:
                continue

            try:
                flags = int(parts[0])
                protocol = int(parts[1])
                algorithm = int(parts[2])
            except ValueError:
                continue

            if flags != int(self.signing_key):
                continue

            name = rr.get("NAME") or "."
            ttl = rr.get("TTL")
            class_name = rr.get("CLASSname") or "IN"
            type_name = rr.get("TYPEname") or "DNSKEY"

            ttl_str = str(ttl) if isinstance(ttl, int) else "0"
            line = f"{name} {ttl_str} {class_name} {type_name} {rdata}".rstrip()
            key = " ".join(parts[3:])

            extracted.append((flags, protocol, algorithm, key, line))

        # Deterministic order independent from server output order.
        extracted.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
        return [t[4] for t in extracted]

    def _dnskeys_from_text(self, out: str) -> List[str]:
        """Extract matching DNSKEY records from textual kdig +answer output."""
        pattern = re.compile(
            r"(?P<key>^.*\sDNSKEY\s+{}\s+.*$)".format(self.signing_key), re.MULTILINE
        )
        matches = [m.group("key").rstrip() for m in re.finditer(pattern, out)]
        matches.sort()
        return matches

    def _atomic_write(self, path: str, data: str) -> None:
        """Atomically write text data to a file.

        The content is written to a temporary file in the target directory and then
        moved into place via `os.replace()`, ensuring readers never observe partial
        writes.

        Args:
          path: Destination file path.
          data: Text content to write.
        """
        self.module.log(f"Kdig::_atomic_write(path: {path}, data: {data})")

        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w", delete=False, dir=parent, encoding="utf-8"
        ) as tf:
            tf.write(data)
            tmp_name = tf.name

        os.replace(tmp_name, path)
        os.chmod(path, 0o644)

    def _exec(self, commands: List[str], check_rc: bool = True) -> Tuple[int, str, str]:
        """Execute a command via Ansible's `run_command()`.

        Args:
          commands: The fully prepared argument vector.
          check_rc: If True, Ansible will treat non-zero return codes as fatal.

        Returns:
          A tuple of `(rc, stdout, stderr)`.
        """
        self.module.log(f"Kdig::_exec(commands: {commands}, check_rc: {check_rc})")

        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err

    def __checksum(self, plaintext: str) -> str:
        """Compute a SHA-256 checksum for the provided text.

        Args:
          plaintext: Canonical DNSKEY text representation.

        Returns:
          The hex-encoded SHA-256 digest.
        """
        self.module.log(f"Kdig::__checksum(plaintext: {plaintext})")

        _bytes = plaintext.encode("utf-8")
        _hash = hashlib.sha256(_bytes)
        checksum = _hash.hexdigest()

        return checksum


def main():
    """Ansible module entry point.

    Parses module arguments, executes the helper, and returns the result via
    `exit_json()`.
    """
    module = AnsibleModule(
        argument_spec=dict(
            root_dns=dict(required=False, default="k.root-servers.net", type="str"),
            signing_key=dict(required=False, default=257, type="int"),
            trust_keyfile=dict(
                required=False, default="/etc/trusted-key.key", type="str"
            ),
            parameters=dict(required=False, type="list"),
        ),
        supports_check_mode=True,
    )

    c = Kdig(module)
    result = c.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
