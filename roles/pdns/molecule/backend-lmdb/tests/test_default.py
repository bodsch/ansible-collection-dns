# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="pdns")


def test_directories(host, get_vars):
    """
    used config directory
    """
    print(get_vars)

    directories = [
        "/etc/powerdns",
        "/var/lib/powerdns",
        "/var/spool/powerdns",
        get_vars.get("pdns_config_include"),
    ]

    for dirs in directories:
        d = host.file(dirs)
        assert d.is_directory


def test_files(host, get_vars):
    """
    created config files
    """
    files = [
        "/etc/powerdns/pdns.conf",
        "/etc/powerdns/pdns.d/pdns_general.conf",
        "/etc/powerdns/pdns.d/pdns_backends.conf",
        "/etc/powerdns/pdns.d/pdns_webserver.conf",
        "/etc/powerdns/pdns.d/pdns_api.conf",
        "/etc/ansible/facts.d/pdns.fact",
        "/usr/bin/pdnsutil",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_lmbd_files(host, get_vars):
    """ """

    files = [
        "/var/lib/powerdns/pdns.lmdb",
        "/var/lib/powerdns/pdns.lmdb-lock",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_service_running_and_enabled(host, get_vars):
    """
    running service
    """
    service_name = get_vars.get("pdns_service").get("name", None)

    if service_name:
        service = host.service(service_name)
        assert service.is_running
        assert service.is_enabled


def test_listening_socket(host, get_vars):
    """ """
    listening = host.socket.get_listening_sockets()

    for i in listening:
        print(i)

    bind_port = "5300"
    bind_address = "127.0.0.1"

    listen = []
    listen.append(f"tcp://{bind_address}:{bind_port}")
    listen.append(f"udp://{bind_address}:{bind_port}")

    for spec in listen:
        socket = host.socket(spec)
        assert socket.is_listening
