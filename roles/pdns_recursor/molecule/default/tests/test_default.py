# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="pdns_records")


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


# def test_user(host, get_vars):
#     """
#       created user
#     """
#     shell = '/bin/false'
#
#     distribution = host.system_info.distribution
#
#     if distribution in ['centos', 'redhat', 'ol']:
#         shell = "/sbin/nologin"
#     elif distribution == "arch":
#         shell = "/usr/bin/nologin"
#
#     user_name = "mysql"
#     u = host.user(user_name)
#     g = host.group(user_name)
#
#     assert g.exists
#     assert u.exists
#     assert user_name in u.groups
#     assert u.shell == shell


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
