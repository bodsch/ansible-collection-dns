# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="fqdn")


def test_files(host):
    """ """
    files = []
    files.append("/etc/hostname")

    for _file in files:
        f = host.file(_file)
        assert f.is_file
