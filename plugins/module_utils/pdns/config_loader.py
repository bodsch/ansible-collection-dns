#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import glob
import os
from typing import Any, Dict, List, Union


class PowerDNSConfigLoader:
    """
    Load and normalize PowerDNS configuration from a main config file plus optional include files.

    This loader reads a PowerDNS-style key/value configuration (e.g. ``pdns.conf``) and:
      - Parses the main configuration file.
      - If ``include-dir`` is set and points to a directory, reads all ``*.conf`` files in that directory.
      - Detects backends via ``launch=...`` and ``launch+...`` directives.
      - Collects backend-specific settings (keys prefixed with ``<backend>-``) into a structured list.

    Output format:
      - ``config``: A dictionary containing global settings plus the key ``"backends"``.
      - ``config["backends"]``: A list of dictionaries; each element has at least ``{"name": "<backend>"}``
        and may include additional backend-specific keys.

    The class is designed to be used in an Ansible context: ``module`` is expected to provide
    ``module.log(...)`` for debug logging.

    Attributes:
        module: Ansible-like module object, used for logging.
        config: Aggregated global configuration values.
        backends: Detected backend names in the effective launch order.
        backend_configs: Per-backend configuration mapping, keyed by backend name.
    """

    def __init__(self, module: Any) -> None:
        """
        Create a new config loader instance.

        Args:
            module: An Ansible-like module object providing a ``log(...)`` method.

        Returns:
            None
        """
        self.module = module
        self.config: Dict[str, Any] = {}
        self.backends: List[str] = []
        self.backend_configs: Dict[str, Dict[str, Any]] = {}

        self.module.log("PowerDNSConfigLoader::__init__()")

    def load(self, main_config: str = "/etc/powerdns/pdns.conf") -> Dict[str, Any]:
        """
        Load the main configuration file and all include files, then return the normalized config.

        Processing rules:
          - Reads `main_config`.
          - If the config contains ``include-dir`` and it is an existing directory, loads all
            ``*.conf`` files from that directory in sorted order.
          - Builds ``config["backends"]`` from the detected backend list and collected
            backend-specific key/value pairs.

        Args:
            main_config: Path to the primary PowerDNS configuration file.

        Returns:
            dict[str, Any]: Normalized configuration dictionary with:
              - global keys (as found in config files)
              - ``"backends"`` list containing backend dictionaries

        Raises:
            FileNotFoundError: If `main_config` (or any included file) does not exist.
            OSError: If a config file cannot be read.
        """
        self.module.log(f"PowerDNSConfigLoader::load(main_config={main_config})")

        self._load_file(main_config)

        include_dir = self.config.get("include-dir")
        if include_dir and os.path.isdir(include_dir):
            for file_path in sorted(glob.glob(os.path.join(include_dir, "*.conf"))):
                self._load_file(file_path)

        # Finalize backend list with associated settings.
        backend_list: List[Dict[str, Any]] = []
        for backend in self.backends:
            backend_entry = {"name": backend}
            for key, value in self.backend_configs.get(backend, {}).items():
                backend_entry[key] = value
            backend_list.append(backend_entry)

        self.config["backends"] = backend_list

        return self.config

    def _load_file(self, file_path: str) -> None:
        """
        Read and process a single PowerDNS configuration file.

        Supported directives and behavior:
          - Ignores empty lines and comments starting with ``#``.
          - Expects ``key=value`` pairs; other lines are ignored.
          - ``launch=<csv>``:
              Clears the current backend list and replaces it with the comma-separated values.
          - ``launch+<anything>=<backend>``:
              Appends the backend name from the value to the backend list (if non-empty).
          - ``<backend>-<setting>=...``:
              If `<backend>` is in the current backend list, stores the key/value in `backend_configs[backend]`.
          - Any other keys are treated as global config and stored in `self.config`.

        Values are normalized via :meth:`_convert_value` (bool/int/float where possible).

        Args:
            file_path: Path to the configuration file to read.

        Returns:
            None

        Raises:
            FileNotFoundError: If `file_path` does not exist.
            OSError: If the file cannot be opened/read.
        """
        self.module.log(f"PowerDNSConfigLoader::_load_file(file_path={file_path})")

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, value = map(str.strip, line.split("=", 1))
                lowered_key = key.lower()

                if lowered_key == "launch":
                    self.backends.clear()
                    if value:
                        self.backends.extend(
                            [v.strip() for v in value.split(",") if v.strip()]
                        )

                elif lowered_key.startswith("launch+"):
                    if value:
                        self.backends.append(value.strip())

                else:
                    is_backend_key = False
                    for backend in self.backends:
                        # Example: backend = gsqlite3 -> keys like "gsqlite3-database=..."
                        if lowered_key.startswith(f"{backend}-"):
                            self.backend_configs.setdefault(backend, {})[key] = (
                                self._convert_value(value)
                            )
                            is_backend_key = True
                            break

                    if not is_backend_key:
                        self.config[key] = self._convert_value(value)

    def _convert_value(self, value: str) -> Union[bool, int, float, str]:
        """
        Convert a configuration value to a more specific Python type when possible.

        Conversion rules (in order):
          - "yes"/"true"  -> True
          - "no"/"false"  -> False
          - digits only   -> int
          - parseable float -> float
          - otherwise returns the original string

        Args:
            value: Raw string value from the config file.

        Returns:
            bool | int | float | str: Converted value.
        """
        lowered = value.lower()
        if lowered in ("yes", "true"):
            return True
        if lowered in ("no", "false"):
            return False
        if lowered.isdigit():
            return int(value)
        try:
            return float(value)
        except ValueError:
            return value
