#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, print_function)
import re


class PiHole():
    """
    """
    def __init__(self, module):
        self.module = module

        self.pihole_bin = self.module.get_bin_path('pihole', False)

    def import_allow_lists(self, data):
        """
        """
        result_state = []

        args = [self.pihole_bin]
        args.append("allow")

        for domain in data:
            args.append(domain)

        args.append("--comment")
        args.append("allowlist import")

        self.module.log(msg=f"  args_list : '{args}'")

        rc, out, err = self._exec(args)

        """
           - Failed to add 6 domain(s):
        """
        self.module.log(msg=f"  out: '{out}'")
        self.module.log(msg=f"  err: '{err}'")

        # res["allow"][domain] = dict(
        #     msg = out
        # )

        # result_state.append(res)

        return result_state

    def import_deny_lists(self, data):
        """
        """
        result_state = []

        args = [self.pihole_bin]
        args.append("deny")

        for domain in data:
            args.append(domain)

        args.append("--comment")
        args.append("denylist import")

        self.module.log(msg=f"  args_list : '{args}'")

        rc, out, err = self._exec(args)

        self.module.log(msg=f"  out: '{out}'")
        self.module.log(msg=f"  err: '{err}'")

        # res["deny"][domain] = dict(
        #     msg = out
        # )
        #
        # result_state.append(res)

        return result_state


    def set_config(self, config: dict):
        """
            e.g. /usr/bin/pihole-FTL --config dns.hosts '[ "192.168.0.4 matrix.vpn", "192.168.0.4 matrix.lan" ]'
        """
        pass

    def _exec(self, commands: list, check_rc: bool=True):
        """
        """
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)
        self.module.log(msg=f"  rc : '{rc}'")

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err
