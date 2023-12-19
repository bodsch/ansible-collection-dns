
# Ansible Role:  `dnsmasq`

Ansible role to install and configure dnsmasq on various linux systems.

[sourcecode](https://thekelleys.org.uk/gitweb/?p=dnsmasq.git;a=summary)


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-dnsmasq/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-dnsmasq)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-dnsmasq)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-dnsmasq/actions
[issues]: https://github.com/bodsch/ansible-dnsmasq/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-dnsmasq/releases
[quality]: https://galaxy.ansible.com/bodsch/dnsmasq


## usage

```yaml
dnsmasq_systemd:
  unit:
    after: []
    wants: []
    requires: []

dnsmasq_global: {}
#   port: 53
#   user: ""
#   group: ""
#   filterwin2k: false
#   resolv_file: ""
#   strict_order: false
#   no_hosts: false
#   no_resolv: false
#   no_poll: false
#   domain_needed: false
#   bogus_priv: false
#   cache_size: 150
#   all_servers: false
#   no_negcache: false
#   conf_file: ""
#   conf_dir: ""

dnsmasq_interfaces:
  listen_address: "127.0.0.1"
  # Define specific interfaces to listen on
  interfaces: []
  #  - "{{ ansible_default_ipv4['interface'] }}"
  #  - eth0
  #  - eth1
  # Define any interface to not listen on
  except_interfaces: []
  #  - eth1
  # Defines if DNSMasq only listens on specific interfaces instead of all interfaces
  bind_only: false

dnsmasq_logging:
  log_queries: false
  log_facility: /var/log/dnsmasq.log
  log_dhcp: false

dnsmasq_addresses: []
# - address: 192.168.202.133
#   name: node1.test.com

dnsmasq_alias: {}

dnsmasq_dhcp:
#   enabled: false
#   dhcp_authoritative: false
#   dhcp_boot: "pxelinux.0,{{ inventory_hostname }},{{ dnsmasq_domain }}"
#   dhcp_hosts: []
#   dhcp_options: []
#   dhcp_options_tagged: []
#   dhcp_range: []

dnsmasq_dnssec: {}
#  enabled: false
#  conf_file: ""
#  dnssec_check_unsigned: false

dnsmasq_domain:
  name: example.org
  custom: []

dnsmasq_ipset: {}

dnsmasq_local: {}

dnsmasq_mx: {}

dnsmasq_nftset: {}

dnsmasq_pxe: {}

dnsmasq_server: {}
#  nameservers: []
#  forwarders: []

dnsmasq_tftp: {}
#   enabled: false
#   tftp_root: ""
#   tftp_no_fail: false
#   tftp_secure: false
#   tftp_no_blocksize: false

dnsmasq_records:
  cname: []
#  - target:
#    cnames:
#      - cname
  ptr: []
  srv: []
  txt: []
```
### `dnsmasq_systemd`

Adds a possibility to make the service dependent on others.

For example, if binding to a VPN network interface is desired and the VPN must be started beforehand.

```yaml
dnsmasq_systemd:
  unit:
    after:
      - ssh.service
    wants: []
    requires: []
```


### `dnsmasq_global`

```yaml
dnsmasq_global:
  port: 53
  user: ""
  group: ""
  filterwin2k: false
  resolv_file: ""
  strict_order: false
  no_hosts: false
  no_resolv: false
  no_poll: false
  domain_needed: false
  bogus_priv: false
  cache_size: 150
  all_servers: false
  no_negcache: false
  conf_file: ""
  conf_dir: ""
```

### `dnsmasq_interfaces`

```yaml
dnsmasq_interfaces:
  listen_address: "127.0.0.1"
  # Define specific interfaces to listen on
  interfaces: []
  #  - "{{ ansible_default_ipv4['interface'] }}"
  #  - eth0
  #  - eth1
  # Define any interface to not listen on
  except_interfaces: []
  #  - eth1
  # Defines if DNSMasq only listens on specific interfaces instead of all interfaces
  bind_only: false
```

### `dnsmasq_logging`

```yaml
dnsmasq_logging:
  log_queries: false
  log_facility: /var/log/dnsmasq.log
  log_dhcp: false
```

### `dnsmasq_address`

```yaml
dnsmasq_address: []
# - address: 192.168.202.133
#   name: node1.test.com
```

### `dnsmasq_alias`

```yaml
dnsmasq_alias: {}
```

### `dnsmasq_dhcp`

```yaml
dnsmasq_dhcp: {}
#   enabled: false
#   dhcp_authoritative: false
#   dhcp_boot: "pxelinux.0,{{ inventory_hostname }},{{ dnsmasq_domain }}"
#   dhcp_hosts: []
#   dhcp_options: []
#   dhcp_options_tagged: []
#   dhcp_range: []
```

### `dnsmasq_dnssec`

```yaml
dnsmasq_dnssec: {}
#  enabled: false
#  conf_file: ""
#  dnssec_check_unsigned: false
```

### `dnsmasq_domain`

```yaml
dnsmasq_domain:
  name: example.org
  # Define custom domains per subnet, ip range, etc.
  custom:
    - domain: "example.local"
      network:
        - 192.168.10.0/24 # Define as range
```

### `dnsmasq_ipset`

```yaml
dnsmasq_ipset: {}
```

### `dnsmasq_local`

```yaml
dnsmasq_local: {}
```

### `dnsmasq_mx`

```yaml
dnsmasq_mx: {}
```

### `dnsmasq_nftset`

```yaml
dnsmasq_nftset: {}
```

### `dnsmasq_pxe`

```yaml
dnsmasq_pxe: {}
```

### `dnsmasq_server`

```yaml
dnsmasq_server: {}
#  nameservers: []
#  forwarders: []
```

### `dnsmasq_tftp`

```yaml
dnsmasq_tftp: {}
#   enabled: false
#   tftp_root: ""
#   tftp_no_fail: false
#   tftp_secure: false
#   tftp_no_blocksize: false
```

### `dnsmasq_records`

```yaml
dnsmasq_records:
  cname: []
#  - target:
#    cnames:
#      - cname
  ptr: []
  srv: []
  txt: []
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-dnsmasq/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
