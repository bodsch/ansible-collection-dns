
# Ansible Role:  `knot`

This role will fully configure and install [knot](https://github.com/CZ-NIC/knot).

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-knot/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-knot)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-knot)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-knot/actions
[issues]: https://github.com/bodsch/ansible-knot/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-knot/releases
[quality]: https://galaxy.ansible.com/bodsch/knot


## Requirements & Dependencies

not known

### Operating systems

Tested on

* ArchLinux
* Debian based
    - Debian 10 / 11
    - Ubuntu 20.04

## configuration

### default

```yaml
knot_user: knot
knot_group: knot

knot_config: {}

knot_zones: {}
```

### knot config

```yaml
knot_config:
  server:
    listen:
      - '127.0.0.1@5353'

  log:
    syslog:
      any: debug

  database:
    storage: "{{ knot_database }}"

  template:
    default:
      storage: "{{ knot_database }}"
      file: "%s.zone"

  zone:
    molecule.local: {}
```

### knot zones

```yaml
knot_zones:
  state: present
  molecule.local:
    ttl: 3600
    soa:
      primary_dns: 'dns.molecule.local'
      hostmaster: 'hostmaster.molecule.local'
      refresh: 6h
      retry: 1h
      expire: 1w
      minimum: 1d
    name_servers:
      dns.molecule.local:
        ip: '{{ ansible_default_ipv4.address }}'
    records:
      router.molecule.local:
        type: 'A'
        ip: '{{ ansible_default_ipv4.address }}'

      ldap.molecule.local:
        type: 'CNAME'
        target: 'router.molecule.local'
```


### `knotc` CLI

```bash
knotc conf-begin
knotc conf-set zone.domain molecule.local
knotc conf-commit

knotc zone-begin molecule.local
knotc zone-set molecule.local @ 7200 SOA dns hostmaster 1 86400 900 691200 3600
knotc zone-set molecule.local dns 3600 A 172.17.0.2
knotc zone-set molecule.local router 3600 A 172.17.0.2
knotc zone-set molecule.local www 3600 A 172.17.0.5
knotc zone-set molecule.local ldap 3600 CNAME router
knotc zone-set molecule.local _https._tcp 3600 SRV "10 20 433 www"
knotc zone-commit molecule.local
```

more under [knot operation doku](https://www.knot-dns.cz/docs/3.1/html/operation.html)

## Author and License

- Bodo Schulz

## License

[Apache](LICENSE)

`FREE SOFTWARE, HELL YEAH!`
