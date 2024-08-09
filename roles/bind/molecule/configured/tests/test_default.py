# coding: utf-8
from __future__ import unicode_literals

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

import json
import pytest
import os

import testinfra.utils.ansible_runner

HOST = 'all'

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


def dig(host, domains):

    local_dns = "@127.0.0.1"

    for d in domains:
        output_msg = ""
        domain = d.get("domain")
        dns_type = d.get("type", "A").upper()
        result = d.get("result")

        if dns_type == "PTR":
            dig_type = "-x"
        else:
            dig_type = f"-t {dns_type}"

        command = f"dig {dig_type} {domain} {local_dns} +short"
        print(f"{command}")
        cmd = host.run(command)

        if cmd.succeeded:
            output = cmd.stdout
            output_arr = sorted(output.splitlines())

            if len(output_arr) == 1:
                output_msg = output.strip()
            if len(output_arr) > 1:
                output_msg = ",".join(output_arr)

            print(f"[{domain} - {dns_type}] => {output_msg}")
            print(f"  {len(output)} - {type(output)}")
            print(f"  {output_msg}")

            return output_msg == result
        else:
            return cmd.failed


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

    file_defaults = read_ansible_yaml(f"{base_dir}/defaults/main", "role_defaults")
    file_vars = read_ansible_yaml(f"{base_dir}/vars/main", "role_vars")
    file_distibution = read_ansible_yaml(f"{base_dir}/vars/{operation_system}", "role_distibution")
    file_molecule = read_ansible_yaml(f"{molecule_dir}/group_vars/all/vars", "test_vars")
    # file_host_molecule = read_ansible_yaml("{}/host_vars/{}/vars".format(base_dir, HOST), "host_vars")

    defaults_vars = host.ansible("include_vars", file_defaults).get("ansible_facts").get("role_defaults")
    vars_vars = host.ansible("include_vars", file_vars).get("ansible_facts").get("role_vars")
    distibution_vars = host.ansible("include_vars", file_distibution).get("ansible_facts").get("role_distibution")
    molecule_vars = host.ansible("include_vars", file_molecule).get("ansible_facts").get("test_vars")
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
    files = [
        get_vars.get("bind_config", "/etc/bind/named.conf")
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_cache_files(host, get_vars):
    """
      created config files
    """
    bind_dir = get_vars.get("bind_dir", "/var/cache/bind")

    files = [
        f"{bind_dir}/0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa",
        f"{bind_dir}/0.11.10.in-addr.arpa",
        f"{bind_dir}/acme-inc.com",
        f"{bind_dir}/124.168.192.in-addr.arpa",
        f"{bind_dir}/cm.local",
    ]

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
    """
    """
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


def test_records_A(host):
    """
    """
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
        #
        {"domain": "cms.cm.local", "type": "A", "result": "192.168.124.21"},
    ]

    assert dig(host, domains)


def test_records_PTR(host):
    """
    """
    domains = [
        # IPv4 Reverse lookups
        {"domain": "10.11.0.1", "type": "PTR", "result": "ns1.acme-inc.com."},
        {"domain": "10.11.0.2", "type": "PTR", "result": "ns2.acme-inc.com."},
        {"domain": "10.11.1.1", "type": "PTR", "result": "srv001.acme-inc.com."},
        {"domain": "10.11.1.2", "type": "PTR", "result": "srv002.acme-inc.com."},
        {"domain": "10.11.2.1", "type": "PTR", "result": "mail001.acme-inc.com."},
        {"domain": "10.11.2.2", "type": "PTR", "result": "mail002.acme-inc.com."},
        {"domain": "10.11.2.3", "type": "PTR", "result": "mail003.acme-inc.com."},
        {"domain": "10.11.0.10", "type": "PTR", "result": "srv010.acme-inc.com."},
        {"domain": "10.11.0.11", "type": "PTR", "result": "srv011.acme-inc.com."},
        {"domain": "10.11.0.12", "type": "PTR", "result": "srv012.acme-inc.com."},
        # # IPv6 Reverse lookups
        {"domain": "2001:db8::1", "type": "PTR", "result": "srv001.acme-inc.com."},
        #
        {"domain": "192.168.124.21", "type": "PTR", "result": "cms.cm.local"},
    ]

    assert dig(host, domains)


def test_records_CNAME(host):
    """
    """
    domains = [
        # IPv4 Alias lookups
        {"domain": "www.acme-inc.com", "type": "CNAME", "result": "srv001.acme-inc.com."},
        {"domain": "mysql.acme-inc.com", "type": "CNAME", "result": "srv002.acme-inc.com."},
        {"domain": "smtp.acme-inc.com", "type": "CNAME", "result": "mail001.acme-inc.com."},
        {"domain": "mail-in.acme-inc.com", "type": "CNAME", "result": "mail001.acme-inc.com."},
        {"domain": "imap.acme-inc.com", "type": "CNAME", "result": "mail003.acme-inc.com."},
        {"domain": "mail-out.acme-inc.com", "type": "CNAME", "result": "mail003.acme-inc.com."},
        #
        {"domain": "cms.cm.local", "type": "CNAME", "result": "192.168.124.21"},
    ]

    assert dig(host, domains)


def test_records_AAAA(host):
    """
    """
    domains = [
        # IPv6 Forward lookups
        {"domain": "srv001.acme-inc.com", "type": "AAAA", "result": "2001:db8::1"},
    ]

    assert dig(host, domains)


def test_records_NS(host):
    """
    """
    domains = [
        # NS records lookup
        {"domain": "acme-inc.com", "type": "NS", "result": "ns1.acme-inc.com.,ns2.acme-inc.com."},
        {"domain": "cm.local", "type": "NS", "result": "dns.cm.local."},
    ]

    assert dig(host, domains)


def test_records_MX(host):
    """
    """
    domains = [
        # MX records lookup
        {"domain": "acme-inc.com", "type": "MX", "result": "10 mail001.acme-inc.com.,20 mail002.acme-inc.com."},
    ]

    assert dig(host, domains)


def test_records_SRV(host):
    """
    """
    domains = [
        # Service records lookup
        {"domain": "_ldap._tcp.acme-inc.com", "type": "SRV", "result": "0 100 88 srv010.acme-inc.com."},
    ]

    assert dig(host, domains)


def test_records_TXT(host):
    """
    """
    domains = [
        # TXT records lookup
        {"domain": "acme-inc.com", "type": "TXT", "result": '"more text","some text"'},
    ]

    assert dig(host, domains)
