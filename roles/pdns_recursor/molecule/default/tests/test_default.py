# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="pdns_recursor")

def test_user(host, get_vars):
    """
        archlinux:
            pdns-recursor:x:968:968:PowerDNS Recursor:/:/usr/bin/nologin
        debian:13
            pdns:x:100:102:PowerDNS:/var/spool/powerdns:/bin/false
    """
    shell = '/bin/false'

    user = get_vars.get("pdns_recursor_owner", "pdns-recursor")
    group = get_vars.get("pdns_recursor_group", "pdns-recursor")

    distribution = host.system_info.distribution

    if distribution == "arch":
        shell = "/usr/bin/nologin"

    u = host.user(user)
    g = host.group(group)

    assert g.exists
    assert u.exists
    assert user in u.groups
    assert u.shell == shell


def test_directories(host, get_vars):
    """
    used config directory
    """
    print(get_vars)

    directories = [
        "/etc/powerdns/recursor.d",
        "/var/cache/ansible/pdns_recursor",
    ]

    for dirs in directories:
        d = host.file(dirs)
        assert d.is_directory


def test_files(host, get_vars):
    """
    created config files
    """
    files = [
        "/etc/powerdns/recursor.conf",
        "/usr/lib/systemd/system/pdns-recursor.service",
        "/usr/sbin/pdns_recursor",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_powerdns_directory(host, get_vars):
    """ """
    config_dir = get_vars.get("pdns_recursor_recursor", {}).get("config_dir", "/etc/powerdns")

    user = "root"
    group = "root"

    print(config_dir)

    if config_dir:
        directory = host.file(config_dir)
        assert directory.is_directory

        assert directory.user == user
        assert directory.group == group
        assert directory.mode == 0o755


def test_recursor_files(host, get_vars):
    """ """
    config_dir = get_vars.get("pdns_recursor_recursor", {}).get("config_dir", "/etc/powerdns")

    user = get_vars.get("pdns_recursor_owner", "pdns-recursor")
    group = get_vars.get("pdns_recursor_group", "pdns-recursor")

    print(config_dir)

    if config_dir:

        recursor_config = f"{config_dir}/recursor.yml"

        _file = host.file(recursor_config)
        assert _file.is_file

        assert _file.user == user
        assert _file.group == group
        assert _file.mode == 0o644


def test_recursor_direcory(host, get_vars):
    """ """
    include_dir = get_vars.get("pdns_recursor_recursor", {}).get("include_dir", "/etc/powerdns/recursor.d")

    user = get_vars.get("pdns_recursor_owner", "pdns-recursor")
    group = get_vars.get("pdns_recursor_group", "pdns-recursor")

    print(include_dir)

    if include_dir:
        directory = host.file(include_dir)
        assert directory.is_directory

        assert directory.user == user
        assert directory.group == group
        assert directory.mode == 0o755


def test_service_running_and_enabled(host, get_vars):
    """
    running service
    """
    service_name = "pdns-recursor"

    service = host.service(service_name)
    assert service.is_running
    assert service.is_enabled


def test_listening_socket(host, get_vars):
    """ """
    listening = host.socket.get_listening_sockets()

    for i in listening:
        print(i)

    listen = []
    listen.append(f"tcp://127.0.0.1:53")
    listen.append(f"udp://127.0.0.1:53")

    for spec in listen:
        socket = host.socket(spec)
        assert socket.is_listening
