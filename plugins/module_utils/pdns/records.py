#

from collections import defaultdict

from ansible_collections.bodsch.dns.plugins.module_utils.pdns.utils import fqdn, build_rrset


def host_records(zone, records, comment=None, account=None):
    """
    """
    rrsets = []

    for record in records:
        # self.module.log(msg=f"  - record: {record})")
        # {'name': 'ns2', 'ip': '10.11.0.2'})
        # {'name': 'srv001', 'ip': '10.11.1.1', 'ipv6': '2001:db8::1', 'aliases': ['www']})

        name = fqdn(zone, record.get("name"))
        ttl = record.get("ttl", 3600)
        ipv4 = record.get("ip", None)
        ipv6 = record.get("ipv6", None)
        aliases = record.get("aliases", None)

        if ipv6:
            rrsets.append(
                build_rrset(
                    name=name,
                    rtype="AAAA",
                    ttl=ttl,
                    records=[ipv6],
                    comment=comment if comment else ""
                )
            )

        if ipv4:
            rrsets.append(
                build_rrset(
                    name=name,
                    rtype="A",
                    ttl=ttl,
                    records=[ipv4],
                    comment=comment if comment else ""
                )
            )

        if aliases:
            for a in aliases:
                rrsets.append(
                    build_rrset(
                        name=fqdn(zone, a),
                        rtype="CNAME",
                        ttl=ttl,
                        records=[name],
                        comment=comment if comment else ""
                    )
                )

    return rrsets


def srv_records(zone, records, comment=None, account=None):
    """
        _service._proto.name.  TTL  IN SRV  priority weight port target
    """
    # self.module.log(msg=f"PowerDNSWebApi::_add_record_srv({zone}, {records}, {comment}, {account})")

    rrsets = []
    # zone_fqdn = zone if zone.endswith('.') else f"{zone}."

    grouped = defaultdict(list)

    for service in records:
        name = service["name"]
        grouped[name].append(service)

    for srv_name, entries in grouped.items():
        srv_records = []
        for entry in entries:
            priority = entry.get("priority", 0)
            weight = entry["weight"]
            port = entry["port"]
            target = fqdn(zone, entry["target"])

            srv_records.append({
                "content": f"{priority} {weight} {port} {target}",
                "disabled": False
            })

        rrsets.append(
            build_rrset(
                name=fqdn(zone, srv_name),
                rtype="SRV",
                ttl=entry.get("ttl", 3600),
                records=srv_records,
                comment=comment if comment else ""
            )
        )

    return rrsets


def mx_records(zone, records, comment=None, account=None):
    """
    """
    # self.module.log(msg=f"PowerDNSWebApi::_add_record_mx({zone}, {records}, {comment}, {account})")

    rrsets = []
    mx_records = []
    zone_fqdn = zone if zone.endswith('.') else f"{zone}."
    ttl = 3600

    for record in records:
        name = record.get("name")
        ttl = record.get("ttl", 3600)
        preference = record.get("preference", 10)

        mx_records.append(
            dict(
                content=fqdn(zone, f"{preference} {name}"),
                disabled=False
            )
        )

    rrsets.append(
        build_rrset(
            name=zone_fqdn,
            rtype="MX",
            ttl=ttl,
            records=mx_records,
            comment=comment if comment else ""
        )
    )

    return rrsets


def txt_records(zone, records, comment=None, account=None):
    """
    """
    # self.module.log(msg=f"PowerDNSWebApi::_add_record_txt({zone}, {records}, {comment}, {account})")

    rrsets = []

    for entry in records:
        name = fqdn(zone, entry.get("name"))
        ttl = entry.get("ttl", 3600)
        txt_data = entry.get("text")

        # Normalisiere: Liste oder einzelner String
        if isinstance(txt_data, str):
            txt_data = [txt_data]

        txt_records = []
        for line in txt_data:
            # PowerDNS erwartet Text in doppelten Anführungszeichen
            quoted = f"\"{line}\""
            txt_records.append({
                "content": quoted,
                "disabled": False
            })

        # fqdn_name = fqdn(zone, name)  # z. B. _kerberos.acme-inc.com.

        rrsets.append(
            build_rrset(
                name=name,
                rtype="TXT",
                ttl=ttl,
                records=txt_records,
                comment=comment or ""
            )
        )

    return rrsets


def ptr_records(zone, records, comment=None, account=None):
    """
    """
    rrsets = []

    # for z in records:
    #     status_code, msg, json_response = create_zone(z, nameservers=[], kind="native", masters=None)
    #
    #     if status_code in [200, 201]:
    #         rrsets = [
    #             build_rrset(z, "SOA", ttl, [soa]),
    #             # self.build_rrset(z, "NS", ttl, [self.fqdn(zone, for x in nameservers])
    #         ]
    #
    #         status_code, msg, json_response = patch_zone(zone, rrsets)

    return rrsets
