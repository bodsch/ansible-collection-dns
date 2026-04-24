# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="unbound")


@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/unbound",
        "/etc/unbound/unbound.conf.d",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory
    assert d.exists


@pytest.mark.parametrize(
    "files",
    [
        "/etc/unbound/unbound.conf",
        "/etc/unbound/unbound.conf.d/server.conf",
        "/etc/unbound/unbound.conf.d/forward_zone.conf",
        "/etc/unbound/unbound.conf.d/remote_control.conf",
        "/etc/unbound/unbound.conf.d/cache_db.conf",
    ],
)
def test_files(host, files):
    f = host.file(files)
    assert f.exists
    assert f.is_file


def test_user(host):
    """
    test service user
    """
    shell = "/usr/sbin/nologin"
    home = "/var/lib/unbound"

    distribution = host.system_info.distribution
    release = host.system_info.release

    print(distribution)

    if distribution == "debian" and release.startswith("9"):
        shell = "/bin/false"

    if distribution in ["arch"]:
        home = "/etc/unbound"

    assert host.group("unbound").exists
    assert host.user("unbound").exists
    assert "unbound" in host.user("unbound").groups
    assert host.user("unbound").shell == shell
    assert host.user("unbound").home == home


def test_service(host):
    service = host.service("unbound")
    assert service.is_enabled
    assert service.is_running


@pytest.mark.parametrize(
    "ports",
    [
        "0.0.0.0:53",
    ],
)
def test_open_port(host, ports):

    for i in host.socket.get_listening_sockets():
        print(i)

    application = host.socket(f"tcp://{ports}")
    assert application.is_listening
