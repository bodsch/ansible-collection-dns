#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)

import os
import glob

class PowerDNSConfigLoader:
    """
    Lädt PowerDNS-Konfigurationen aus Haupt- und Include-Dateien
    und extrahiert Backends samt zugehöriger Einstellungen.
    """

    def __init__(self, module):
        self.module = module
        self.config = {}
        self.backends = []
        self.backend_configs = {}

    def load(self, main_config="/etc/powerdns/pdns.conf"):
        """
        Lädt die Hauptkonfigurationsdatei sowie alle Dateien im include-dir.
        """
        self._load_file(main_config)

        include_dir = self.config.get("include-dir")
        if include_dir and os.path.isdir(include_dir):
            for file_path in sorted(glob.glob(os.path.join(include_dir, "*.conf"))):
                self._load_file(file_path)

        # Finalisiere die Backends
        backend_list = []
        for backend in self.backends:
            backend_entry = {"name": backend}
            for key, value in self.backend_configs.get(backend, {}).items():
                backend_entry[key] = value
            backend_list.append(backend_entry)

        self.config["backends"] = backend_list
        return self.config

    def _load_file(self, file_path):
        """
        Liest eine Konfigurationsdatei ein und verarbeitet sie.
        """
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, value = map(str.strip, line.split("=", 1))
                lowered_key = key.lower()
                self.module.log(msg=f"  - {lowered_key} = {value}")

                if lowered_key == "launch":
                    self.backends.clear()
                    if value:
                        self.backends.extend([v.strip() for v in value.split(",") if v.strip()])
                elif lowered_key.startswith("launch+"):
                    if value:
                        self.backends.append(value.strip())
                else:
                    is_backend_key = False
                    for backend in self.backends:
                        # z. B. backend = gsqlite3 → prefix = sqlite
                        prefix = backend.lstrip("g")
                        if lowered_key.startswith(f"{prefix}-"):
                            self.backend_configs.setdefault(backend, {})[key] = self._convert_value(value)
                            is_backend_key = True
                            break

                    if not is_backend_key:
                        self.config[key] = self._convert_value(value)

    def _convert_value(self, value):
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


class PowerDNSConfigLoaderOLD:
    """
    """
    def __init__(self, module):
        self.module = module
        self.config = {}

        # self.backends = []
        # self.backend_configs = {}

    def load(self, main_config="/etc/powerdns/pdns.conf"):
        """
        """
        self._load_file(main_config)

        # Verarbeite das Include-Verzeichnis
        include_dir = self.config.get("include-dir")
        if include_dir and os.path.isdir(include_dir):
            for file_path in sorted(glob.glob(os.path.join(include_dir, "*.conf"))):
                self._load_file(file_path)

        # Füge die Backend-Infos zur Hauptkonfiguration hinzu
        # self.config["launch_backends"] = self.backends
        # self.config["backend_configs"] = self.backend_configs
        return self.config

    def _load_file(self, file_path):
        """
        """
        with open(file_path, "r") as f:
            current_backend = None

            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = map(str.strip, line.split("=", 1))
                    lowered_key = key.lower()

                    self.module.log(msg=f"  - {lowered_key}")

                    if lowered_key == "launch":
                        continue
                        # self.backends.clear()
                        # current_backend = None

                    # TODO backend parsing
                    elif lowered_key.startswith("launch+"):
                        continue

                        # self.module.log(msg=f"  - backend {value}")
                        #
                        # # Beispiel: launch+gmysql → extrahiere "gmysql"
                        # backend = lowered_key.split("+", 1)[1]
                        # if backend not in self.backends:
                        #     self.backends.append(backend)
                        # current_backend = backend

                    else:
                        self.config[key] = self._convert_value(value)
                    #     # prüfe, ob der Key zu einem der bekannten Backends gehört
                    #     for backend in self.backends:
                    #         if key.lower().startswith(backend):
                    #             if backend not in self.backend_configs:
                    #                 self.backend_configs[backend] = {}
                    #             self.backend_configs[backend][key] = self._convert_value(value)
                    #             break  # sobald ein Backend gematcht wurde, abbrechen

    def _convert_value(self, value):
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
            return value  # Fallback zu string

# # Beispielaufruf:
# if __name__ == "__main__":
#     loader = PowerDNSConfigLoader()
#     config = loader.load()
#     print("Backends:", config["launch_backends"])
#     print("Backend configs:", config["backend_configs"])
#     print("Full config:", config)
