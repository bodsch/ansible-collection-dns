# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="knot")


def test_packages(host):
    """ """
    distribution = host.system_info.distribution
    release = host.system_info.release

    print(f"distribution: {distribution}")
    print(f"release     : {release}")

    packages = []
    packages.append("knot")

    # artix ist not supported
    if not distribution == "artix":
        for package in packages:
            p = host.package(package)
            assert p.is_installed


@pytest.mark.parametrize("dirs", ["/etc/knot", "/var/lib/knot"])
def test_directories(host, dirs):

    d = host.file(dirs)
    assert d.is_directory


def test_service_running_and_enabled(host):
    service = host.service("knot")
    assert service.is_running
    assert service.is_enabled


def test_listening_socket(host, get_vars):
    """ """
    listening = host.socket.get_listening_sockets()

    for i in listening:
        print(i)

    bind_address = "127.0.0.1"
    bind_port = 53

    listen = []
    listen.append(f"tcp://{bind_address}:{bind_port}")

    for spec in listen:
        socket = host.socket(spec)
        assert socket.is_listening
