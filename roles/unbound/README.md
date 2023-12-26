
# Ansible Role:  `unbound`


install and configure [unbound](https://www.nlnetlabs.nl/projects/unbound/about/)


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-unbound/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-unbound)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-unbound)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-unbound/actions
[issues]: https://github.com/bodsch/ansible-unbound/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-unbound/releases
[quality]: https://galaxy.ansible.com/bodsch/unbound


## Requirements & Dependencies


### Operating systems

Tested on

* Debian based
    - Debian 10 / 11
    - Ubuntu 20.10

## Role Variables

```
unbound_user: unbound
unbound_group: unbound

unbound_conf_dir: /etc/unbound
```

### server
```
unbound_config:
  server: {}
```

### forward zone
```
unbound_config:
  forward_zone: {}
```

### remote control
```
unbound_config:
  remote_control: {}
```

## cachedb
```
unbound_config:
  cachedb: {}
```

Role Variables will be merged with [defaults](vars/main.yml) (see below under *default vars*)



## default vars

```
unbound_config_defaults:
  server:
    verbosity: 1
    statistics-interval: 240
    use-syslog: "no"
    log-queries: "yes"
    logfile: /var/log/unbound.log
    num-threads: 1
    directory: "/etc/unbound"
    interface: 0.0.0.0
    do-ip4: 'yes'
    do-ip6: 'no'
    do-udp: 'yes'
    do-tcp: 'yes'
    access-control:
      - '127.0.0.0/8 allow'
    cache-min-ttl: 5
    cache-max-negative-ttl: 60
    root-hints: "/etc/unbound/root.hints"
    hide-identity: 'yes'
    hide-version: 'yes'
    prefetch: 'yes'
    max-udp-size: 4096
    msg-buffer-size: 65552
    unwanted-reply-threshold: 10000
    ipsecmod-enabled: 'no'

  forward_zone:
    name: "."
    # definitely censor free & log free with DNSSEC Support:
    forward_addrs:
      - 84.200.69.80   # DNS Watch
      - 84.200.70.40   # DNS Watch
      - 77.109.148.136 # Xiala.net
      - 77.109.148.137 # Xiala.net
      - 91.239.100.100 # censurfridns.dk
      - 89.233.43.71   # censurfridns.dk

  remote_control:
    server-key-file: "{{ unbound_conf_dir }}/unbound_server.key"
    server-cert-file: "{{ unbound_conf_dir }}/unbound_server.pem"
    control-key-file: "{{ unbound_conf_dir }}/unbound_control.key"
    control-cert-file: "{{ unbound_conf_dir }}/unbound_control.pem"

  certs:
    server:
      key_file: "{{ unbound_conf_dir }}/unbound_server.key"
      cert_file: "{{ unbound_conf_dir }}/unbound_server.pem"
    control:
      key_file: "{{ unbound_conf_dir }}/unbound_control.key"
      cert_file: "{{ unbound_conf_dir }}/unbound_control.pem"

  cachedb: {}
```


---

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
