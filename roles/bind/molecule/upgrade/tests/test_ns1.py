# # coding: utf-8
from __future__ import annotations, unicode_literals

from helper.dns_utils import dig_python, extract_error, extract_unique_errors
from helper.molecule import get_vars, infra_hosts

testinfra_hosts = infra_hosts(host_name="ns1")

# --- tests -----------------------------------------------------------------


def _exec_dns_test(host, get_vars, domains):

    has_failed, failed = dig_python(host=host, get_vars=get_vars, domains=domains)

    if has_failed:
        print(failed)
        unique_errors = extract_unique_errors(failed)
        error = extract_error(failed)
        print("\n".join(error))
        print("\n".join(unique_errors))
        assert False


# def dig(host, domains):
#
#     local_dns = "@127.0.0.1"
#     for d in domains:
#         domain = d.get("domain")
#         dns_type = d.get("type", "A").upper()
#         result = d.get("result")
#
#         if dns_type == "PTR":
#             dig_type = "-x"
#         else:
#             dig_type = f"-t {dns_type}"
#
#         command = f"dig {dig_type} {domain} {local_dns} +short"
#         # print(f"{command}")
#         cmd = host.run(command)
#
#         if cmd.succeeded:
#             output = cmd.stdout
#             output_arr = sorted(output.splitlines())
#
#             if len(output_arr) == 1:
#                 output_msg = output.strip()
#             if len(output_arr) > 1:
#                 output_msg = ",".join(output_arr)
#
#             # print(f"[{domain} - {dns_type}] => {output_msg}")
#             # print(f"  {len(output)} - {type(output)}")
#             # print(f"  {output_msg}")
#
#             return output_msg == result
#         else:
#             return cmd.failed


def test_records_A(host, get_vars):
    """ """
    domains = [
        {"domain": "ns1.acme-inc.local", "type": "A", "result": "10.11.0.1"},
        {"domain": "ns2.acme-inc.local", "type": "A", "result": "10.11.0.2"},
        {"domain": "srv001.acme-inc.local", "type": "A", "result": "10.11.1.1"},
        {"domain": "srv002.acme-inc.local", "type": "A", "result": "10.11.1.2"},
        {"domain": "mail001.acme-inc.local", "type": "A", "result": "10.11.2.1"},
        {"domain": "mail002.acme-inc.local", "type": "A", "result": "10.11.2.2"},
        {"domain": "mail003.acme-inc.local", "type": "A", "result": "10.11.2.3"},
        {"domain": "srv010.acme-inc.local", "type": "A", "result": "10.11.0.10"},
        {"domain": "srv011.acme-inc.local", "type": "A", "result": "10.11.0.11"},
        {"domain": "srv012.acme-inc.local", "type": "A", "result": "10.11.0.12"},
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_PTR(host, get_vars):
    """ """
    domains = [
        # IPv4 Reverse lookups
        {"domain": "10.11.0.1", "type": "PTR", "result": "ns1.acme-inc.local."},
        {"domain": "10.11.0.2", "type": "PTR", "result": "ns2.acme-inc.local."},
        {"domain": "10.11.1.1", "type": "PTR", "result": "srv001.acme-inc.local."},
        {"domain": "10.11.1.2", "type": "PTR", "result": "srv002.acme-inc.local."},
        {"domain": "10.11.2.1", "type": "PTR", "result": "mail001.acme-inc.local."},
        {"domain": "10.11.2.2", "type": "PTR", "result": "mail002.acme-inc.local."},
        {"domain": "10.11.2.3", "type": "PTR", "result": "mail003.acme-inc.local."},
        {"domain": "10.11.0.10", "type": "PTR", "result": "srv010.acme-inc.local."},
        {"domain": "10.11.0.11", "type": "PTR", "result": "srv011.acme-inc.local."},
        {"domain": "10.11.0.12", "type": "PTR", "result": "srv012.acme-inc.local."},
        # # IPv6 Reverse lookups
        {"domain": "2001:db8::1", "type": "PTR", "result": "srv001.acme-inc.local."},
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_CNAME(host, get_vars):
    """ """
    domains = [
        # IPv4 Alias lookups
        {
            "domain": "www.acme-inc.local",
            "type": "CNAME",
            "result": "srv001.acme-inc.local.",
        },
        {
            "domain": "mysql.acme-inc.local",
            "type": "CNAME",
            "result": "srv002.acme-inc.local.",
        },
        {
            "domain": "smtp.acme-inc.local",
            "type": "CNAME",
            "result": "mail001.acme-inc.local.",
        },
        {
            "domain": "mail-in.acme-inc.local",
            "type": "CNAME",
            "result": "mail001.acme-inc.local.",
        },
        {
            "domain": "imap.acme-inc.local",
            "type": "CNAME",
            "result": "mail003.acme-inc.local.",
        },
        {
            "domain": "mail-out.acme-inc.local",
            "type": "CNAME",
            "result": "mail003.acme-inc.local.",
        },
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_AAAA(host, get_vars):
    """ """
    domains = [
        # IPv6 Forward lookups
        {"domain": "srv001.acme-inc.local", "type": "AAAA", "result": "2001:db8::1"},
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_NS(host, get_vars):
    """ """
    domains = [
        # NS records lookup
        {
            "domain": "acme-inc.local",
            "type": "NS",
            "result": "ns1.acme-inc.local.,ns2.acme-inc.local.",
        },
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_MX(host, get_vars):
    """ """
    domains = [
        # MX records lookup
        {
            "domain": "acme-inc.local",
            "type": "MX",
            "result": "10 mail001.acme-inc.local.,20 mail002.acme-inc.local.",
        },
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_SRV(host, get_vars):
    """ """
    domains = [
        # Service records lookup
        {
            "domain": "_ldap._tcp.acme-inc.local",
            "type": "SRV",
            "result": "0 100 88 srv010.acme-inc.local.",
        },
    ]

    _exec_dns_test(host, get_vars, domains)


def test_records_TXT(host, get_vars):
    """ """
    domains = [
        # TXT records lookup
        {
            "domain": "acme-inc.local",
            "type": "TXT",
            "result": '"more text","some text"',
        },
    ]

    _exec_dns_test(host, get_vars, domains)
