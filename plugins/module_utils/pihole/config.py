#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import json
from pathlib import Path
from typing import Any, Dict, Generator, Tuple

import toml
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.pihole import PiHole
from ansible_collections.bodsch.dns.plugins.module_utils.pihole.utils import (
    flatten_config_dict,
    is_equal,
    normalize_value,
)


class ConfigManager(PiHole):
    """ """

    def __init__(self, module: any):
        """ """
        self.module = module

        super().__init__(module)

    def load_toml(self, path: str) -> Dict[str, Any]:
        """ """
        # self.module.log(f"ConfigManager::load_toml(path={path})")

        toml_path = Path(path)
        if not toml_path.exists():
            raise FileNotFoundError(f"TOML configuration file not found: {path}")
            return None

        try:
            with toml_path.open("r", encoding="utf-8") as f:
                config = toml.load(f)
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load TOML config: {e}")
            return None

    def set_config(self, config: dict):
        """
        e.g. /usr/bin/pihole-FTL --config dns.hosts '[ "192.168.0.4 matrix.vpn", "192.168.0.4 matrix.lan" ]'
        """
        # self.module.log("ConfigManager::set_config(config)")
        results = []

        toml = self.load_toml("/etc/pihole/pihole.toml")

        current_gen = flatten_config_dict(toml)
        desired_gen = flatten_config_dict(config)

        diff = self.changed_entries(current_gen, desired_gen)

        if diff:
            for key, val in diff.items():
                res = {}

                changed = self.ensure(key, val)

                res[key] = dict(
                    msg=f"succesfuly to '{val}' changed.",
                    changed=changed,
                )

            results.append(res)
        else:
            changed = False

        return results

    def _config(self, param: str, value: Any):
        """ """
        # self.module.log(f"ConfigManager::set_config(param={param}, value={value})")

        if isinstance(value, bool):
            val = "true" if value else "false"
        elif isinstance(value, (list, dict)):
            val = json.dumps(value)
        else:
            val = str(value)

        cmd = [self.pihole_ftl_bin, "--config", f"{param}", f"{val}"]

        # self.module.log(f"  - {cmd}")

        rc, out, err = self._exec(cmd)
        if rc == 0:
            return True
        else:
            self.module.log("pihole-FTL config failed")
            self.module.log(f"  param={param}")
            self.module.log(f"  value={val}")
            self.module.log(f"  stderr={err}")
            return False

    def ensure(self, param: str, desired: Any):
        changed = self._config(param, desired)
        return changed

    def exit(self):
        return dict(changed=self.changed, results=self.results)

    def changed_entries(
        self,
        current_gen: Generator[Tuple[str, Any], None, None],
        desired_gen: Generator[Tuple[str, Any], None, None],
    ) -> Dict[str, Any]:
        """ """
        # self.module.log("ConfigManager::changed_entries(current_gen, desired_gen)")

        current = dict(current_gen)
        desired = dict(desired_gen)

        changed = {}

        for key, des_val in desired.items():
            cur_val = current.get(key)

            if not is_equal(cur_val, des_val):
                changed[key] = des_val

        return changed

    def changed_entries_older(
        self,
        current_gen: Generator[Tuple[str, Any], None, None],
        desired_gen: Generator[Tuple[str, Any], None, None],
    ) -> Dict[str, Any]:
        """ """
        # self.module.log("ConfigManager::changed_entries(current_gen, desired_gen)")

        current = dict(current_gen)
        desired = dict(desired_gen)

        changed = {}

        # Nur Keys aus der desired Config prüfen und mit current vergleichen
        for key, des_val in desired.items():
            cur_val = current.get(key)

            # Normalisiere Werte vor Vergleich
            norm_cur = normalize_value(cur_val)
            norm_des = normalize_value(des_val)

            if norm_cur != norm_des:
                self.module.log(f" - '{key}' changed from '{norm_cur}' to '{norm_des}'")
                changed[key] = des_val

        return changed
