# Ansible Role: `bodsch.dns.pdns_records`

Ansible role to configure dns records for powerdns.


## usage

```yaml
pdns_zones:
  - name: 'acme-inc.com'
    type: primary
    create_forward_zones: true
    create_reverse_zones: true
    #primaries:
    #  - 10.11.0.1
    networks:
      - '10.11.0'
    ipv6_networks:
      - '2001:db8::'
    name_servers:
      - ns1
      - ns2

    hosts:
      - name: ns1
        ip: 10.11.0.1
      - name: ns2
        ip: 10.11.0.2
      - name: srv001
        ip: 10.11.1.1
        ipv6: 2001:db8::1
        aliases:
          - www
          - foo

    mail_servers:
      - name: mail001
        preference: 10
      - name: mail002
        preference: 20

    services:
      - name: _ldap._tcp
        weight: 100
        port: 631
        target: srv010
      - name: _ldap._tcp
        weight: 50
        port: 631
        target: srv010
      - name: _imap._tcp
        weight: 50
        port: 143
        target: mail001

    text:
      - name: _kerberos
        text: KERBEROS.ACME-INC.COM
      - name: '@'
        text:
          - 'some text'
          - 'more text'

  - name: 'matrix.vpn'
    type: primary
    name_servers:
      - ns

    hosts:
      - name: ns
        ip: 192.168.0.4
      - name: dunkelzahn
        ip: 192.168.0.4
        aliases:
          - home
          - vpn
```

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
