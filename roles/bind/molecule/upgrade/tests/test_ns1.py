# coding: utf-8
from __future__ import unicode_literals

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

import json
import pytest
import os

import testinfra.utils.ansible_runner

HOST = 'ns1'

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts(HOST)


def pp_json(json_thing, sort=True, indents=2):
    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))
    return None


def base_directory():
    """
    """
    cwd = os.getcwd()

    if 'group_vars' in os.listdir(cwd):
        directory = "../.."
        molecule_directory = "."
    else:
        directory = "."
        molecule_directory = f"molecule/{os.environ.get('MOLECULE_SCENARIO_NAME')}"

    return directory, molecule_directory


def read_ansible_yaml(file_name, role_name):
    """
    """
    read_file = None

    for e in ["yml", "yaml"]:
        test_file = f"{file_name}.{e}"
        if os.path.isfile(test_file):
            read_file = test_file
            break

    return f"file={read_file} name={role_name}"


@pytest.fixture()
def get_vars(host):
    """
        parse ansible variables
        - defaults/main.yml
        - vars/main.yml
        - vars/${DISTRIBUTION}.yaml
        - molecule/${MOLECULE_SCENARIO_NAME}/group_vars/all/vars.yml
    """
    base_dir, molecule_dir = base_directory()
    distribution = host.system_info.distribution
    operation_system = None

    if distribution in ['debian', 'ubuntu']:
        operation_system = "debian"
    elif distribution in ['redhat', 'ol', 'centos', 'rocky', 'almalinux']:
        operation_system = "redhat"
    elif distribution in ['arch', 'artix']:
        operation_system = f"{distribution}linux"

    # print(" -> {} / {}".format(distribution, os))
    # print(" -> {}".format(base_dir))

    file_defaults = read_ansible_yaml(
        f"{base_dir}/defaults/main", "role_defaults")
    file_vars = read_ansible_yaml(f"{base_dir}/vars/main", "role_vars")
    file_distibution = read_ansible_yaml(
        f"{base_dir}/vars/{operation_system}", "role_distibution")
    file_molecule = read_ansible_yaml(
        f"{molecule_dir}/group_vars/all/vars", "test_vars")
    # file_host_molecule = read_ansible_yaml("{}/host_vars/{}/vars".format(base_dir, HOST), "host_vars")

    defaults_vars = host.ansible("include_vars", file_defaults).get(
        "ansible_facts").get("role_defaults")
    vars_vars = host.ansible("include_vars", file_vars).get(
        "ansible_facts").get("role_vars")
    distibution_vars = host.ansible("include_vars", file_distibution).get(
        "ansible_facts").get("role_distibution")
    molecule_vars = host.ansible("include_vars", file_molecule).get(
        "ansible_facts").get("test_vars")
    # host_vars          = host.ansible("include_vars", file_host_molecule).get("ansible_facts").get("host_vars")

    ansible_vars = defaults_vars
    ansible_vars.update(vars_vars)
    ansible_vars.update(distibution_vars)
    ansible_vars.update(molecule_vars)
    # ansible_vars.update(host_vars)

    templar = Templar(loader=DataLoader(), variables=ansible_vars)
    result = templar.template(ansible_vars, fail_on_undefined=False)

    return result


def test_directories(host, get_vars):
    """
      used config directory
    """
    pp_json(get_vars)

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
    bind_dir = get_vars.get("bind_dir", "/var/cache/bind")

    files = [
        f"{bind_dir}/0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa",
        f"{bind_dir}/11.10.in-addr.arpa",
        f"{bind_dir}/acme-inc.com"
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_command(host):
    """
    """
    local_dns = "@127.0.0.1"
    domains = [
        {"domain": "ns1.acme-inc.com", "type": "A", "result": "10.11.0.1"},
        {"domain": "ns2.acme-inc.com", "type": "A", "result": "10.11.0.2"},
        {"domain": "srv001.acme-inc.com", "type": "A", "result": "10.11.1.1"},
        {"domain": "srv002.acme-inc.com", "type": "A", "result": "10.11.1.2"},
        {"domain": "mail001.acme-inc.com", "type": "A", "result": "10.11.2.1"},
        {"domain": "mail002.acme-inc.com", "type": "A", "result": "10.11.2.2"},
        {"domain": "mail003.acme-inc.com", "type": "A", "result": "10.11.2.3"},
        {"domain": "srv010.acme-inc.com", "type": "A", "result": "10.11.0.10"},
        {"domain": "srv011.acme-inc.com", "type": "A", "result": "10.11.0.11"},
        {"domain": "srv012.acme-inc.com", "type": "A", "result": "10.11.0.12"},
        # { "domain": "srv001.example.com"  ,                "result": "192.0.2.1" },
        # { "domain": "srv002.example.com"  ,                "result": "192.0.2.2" },
        # { "domain": "mail001.example.com" ,                "result": "192.0.2.10" },
        # IPv4 Reverse lookups
        # { "domain": "10.11.0.1"           , "type": "PTR", "result": "ns1.acme-inc.com."}
    ]
    for d in domains:
        domain = d.get("domain")
        type = d.get("type", "A")
        result = d.get("result")

        cmd = host.run(f"dig -t {type} {domain} {local_dns} +short")

        print(f"[{domain}] {cmd.rc} => {cmd.stdout}")
        assert cmd.stdout.strip() == result