# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="pihole")


def test_files(host, get_vars):
    """ """
    files = ["/etc/pihole/pihole.toml", "/opt/pihole/api.sh", "/usr/local/bin/pihole"]

    for file in files:
        f = host.file(file)
        assert f.exists
        assert f.is_file


def test_user(host, get_vars):
    """ """
    user = "pihole"
    group = "pihole"

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups


def test_service(host, get_vars):
    """ """
    service = host.service("pihole-FTL")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host, get_vars):
    """ """
    # version = local_facts(host).get("major_version")

    for i in host.socket.get_listening_sockets():
        print(i)

    service = host.socket("udp://0.0.0.0:53")
    assert service.is_listening

    # service = host.socket("tcp://0.0.0.0:80")
    # assert service.is_listening
