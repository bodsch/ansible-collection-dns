# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="knot_resolver")


def test_packages(host):
    """ """
    distribution = host.system_info.distribution
    release = host.system_info.release

    print(f"distribution: {distribution}")
    print(f"release     : {release}")

    packages = []
    packages.append("knot-resolver")

    # artix ist not supported
    if not distribution == "artix":
        for package in packages:
            p = host.package(package)
            assert p.is_installed


@pytest.mark.parametrize("dirs", ["/etc/knot-resolver", "/usr/lib/knot-resolver"])
def test_directories(host, dirs):
    distribution = host.system_info.distribution
    # release = host.system_info.release

    if distribution in ["redhat", "ol", "centos", "rocky", "almalinux"]:
        dirs = dirs.replace("/lib/", "/lib64/")

    d = host.file(dirs)
    assert d.is_directory


# def test_service_running_and_enabled(host):
#
#     service = host.service('docker')
#     assert service.is_running
#     assert service.is_enabled
