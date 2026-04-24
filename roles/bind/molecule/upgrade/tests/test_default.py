# # coding: utf-8
from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.dns_utils import dig_python, extract_error, extract_unique_errors
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="bind")


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


def test_files(host, get_vars):
    """
    created config files
    """
    files = [get_vars.get("bind_config", "/etc/bind/named.conf")]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_service_running_and_enabled(host, get_vars):
    """
    running service
    """
    service_name = get_vars.get("bind_service", "bind9")

    service = host.service(service_name)
    assert service.is_running
    assert service.is_enabled


def test_listening_socket(host, get_vars):
    """ """
    listening = host.socket.get_listening_sockets()

    for i in listening:
        print(i)

    bind_port = "53"
    bind_address = "127.0.0.1"

    listen = []
    listen.append(f"tcp://{bind_address}:{bind_port}")
    listen.append(f"udp://{bind_address}:{bind_port}")

    for spec in listen:
        socket = host.socket(spec)
        assert socket.is_listening
