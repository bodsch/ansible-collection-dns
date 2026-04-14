# # coding: utf-8
from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.dns_utils import dig_python, extract_error, extract_unique_errors
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="ns3")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="nextcloud")


def test_directories(host, get_vars):
    """
    used config directory
    """
    directories = [
        get_vars.get("bind_dir"),
        get_vars.get("bind_conf_dir"),
        get_vars.get("bind_zone_dir"),
        get_vars.get("bind_secondary_dir"),
    ]

    for dirs in directories:
        d = host.file(dirs)
        assert d.is_directory


# def test_files(host, get_vars):
#     """
#       created config files
#     """
#     bind_dir = get_vars.get("bind_secondary_dir", "/var/cache/bind/secondary")
#
#     files = [
#         f"{bind_dir}/0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa",
#         f"{bind_dir}/11.10.in-addr.arpa",
#         f"{bind_dir}/acme-inc.local"
#     ]
#
#     for _file in files:
#         f = host.file(_file)
#         assert f.is_file
