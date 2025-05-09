# coding: utf-8
from __future__ import unicode_literals

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

import json
import pytest
import os

import testinfra.utils.ansible_runner

HOST = 'instance'

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


def test_directories(host):
    """
      used config directory
    """
    directories = [
        "/etc/powerdns",
        "/etc/powerdns/pdns.d",
        "/var/lib/powerdns",
    ]

    for dirs in directories:
        d = host.file(dirs)
        assert d.is_directory


def test_files(host):
    """
      created config files
    """
    files = [
        "/etc/powerdns/pdns.conf",
        "/etc/powerdns/pdns.d/pdns_api.conf",
        "/etc/powerdns/pdns.d/pdns_backends.conf",
        "/etc/powerdns/pdns.d/pdns_general.conf",
        "/etc/powerdns/pdns.d/pdns_webserver.conf",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_service_running_and_enabled(host):
    """
      running service
    """
    service_name = "pdns"

    service = host.service(service_name)
    assert service.is_running
    assert service.is_enabled


def test_listening_socket(host):
    """
    """
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
