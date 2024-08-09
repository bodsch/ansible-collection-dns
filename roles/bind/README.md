
# Ansible Role:  `bind`

Ansible role to install and configure bind on various linux systems.


## usage

```yaml
# List of zones for which this name server is authoritative
bind_zones: []

# List of acls.
bind_acls: []

# Key binding for secondary servers
bind_dns_keys: []
#  - name: primary_key
#    algorithm: hmac-sha256
#    secret: "azertyAZERTY123456"

# List of IPv4 address of the network interface(s) to listen on. Set to "any"
# to listen on all interfaces
bind_listen:
  ipv4:
    - port: 53
      addresses:
        - "127.0.0.1"
  ipv6:
    - port: 53
      addresses:
        - "::1"

# List of hosts that are allowed to query this DNS server.
bind_allow_query:
  - "localhost"

# A key-value list mapping server-IPs to TSIG keys for signing requests
bind_key_mapping: {}

# Determines whether recursion should be allowed.
# - If you are building an AUTHORITATIVE DNS server, do NOT enable recursion.
# - If you are building a RECURSIVE (caching) DNS server, you need to enable
#   recursion.
# - If your recursive DNS server has a public IP address, you MUST enable access
#   control to limit queries to your legitimate users. Failing to do so will
#   cause your server to become part of large scale DNS amplification
#   attacks. Implementing BCP38 within your network would greatly
#   reduce such attack surface
# Typically, an authoritative name server should have recursion turned OFF.
bind_recursion: false
bind_allow_recursion:
  - "any"

# Allows BIND to be set up as a caching name server
bind_forward_only: false

# List of name servers to forward DNS requests to.
bind_forwarders: []

# DNS round robin order (random or cyclic)
bind_rrset_order: "random"

# statistics channels configuration
bind_statistics:
  channels: false
  port: 8053
  host: 127.0.0.1
  allow:
    - "127.0.0.1"

# DNSSEC configuration
# NOTE In version 9.16.0 the dnssec-enable option was made obsolete and in 9.18.0 the option was entirely removed.
bind_dnssec:
  enable: true
# dnssec-validation ( yes | no | auto );
  validation: true

bind_extra_include_files: []

# SOA information
bind_zone_soa:
  ttl: "1W"
  time_to_refresh: "1D"
  time_to_retry: "1H"
  time_to_expire: "1W"
  minimum_ttl: "1D"

bind_logging: {}

# File mode for primary zone files (needs to be something like 0660 for dynamic updates)
bind_zone_file_mode: "0640"

# DNS64 support
bind_dns64: false
bind_dns64_clients:
  - "any"
```

### `bind_listen`

```yaml
bind_listen:
  ipv4:
    - port: 53
      addresses:
        - "127.0.0.1"
        - "{{ ansible_default_ipv4.address }}"
    - port: 5353
      addresses:
        - "127.0.1.1"
  ipv6:
    - port: 53
      addresses:
        - "{{ ansible_default_ipv4.address }}"
```


### `bind_logging`

```yaml
bind_logging:
  enable: true
  channels:
  - channel: general
    file: "data/general.log"
    versions: 3
    size: 10M
    print_time: true           # true | false
    print_category: true
    print_severity: true
    severity: dynamic          # critical | error | warning | notice | info | debug [level] | dynamic
  - channel: query
    file: "data/query.log"
    versions: 5
    size: 10M
    print_time: ""          # true | false
    severity: info          #
  - channel: dnssec
    file: "data/dnssec.log"
    versions: 5
    size: 10M
    print_time: ""          # true | false
    severity: info          #
  - channel: notify
    file: "data/notify.log"
    versions: 5
    size: 10M
    print_time: ""          # true | false
    severity: info          #
  - channel: transfers
    file: "data/transfers.log"
    versions: 5
    size: 10M
    print_time: ""          # true | false
    severity: info          #
  - channel: slog
    syslog: security        # kern | user | mail | daemon | auth | syslog | lpr |
                            # news | uucp | cron | authpriv | ftp |
                            # local0 | local1 | local2 | local3 |
                            # local4 | local5 | local6 | local7
    # file: "data/transfers.log"
    #versions: 5
    #size: 10M
    print_time: ""          # true | false
    severity: info          #
  categories:
    "xfer-out":
      - transfers
      - slog
    "xfer-in":
      - transfers
      - slog
    notify:
      - notify
    "lame-servers":
      - general
    config:
      - general
    default:
      - general
    security:
      - general
      - slog
    dnssec:
      - dnssec
    queries:
      - query
```

### `bind_zones`

```yaml
bind_zones:
  - name: 'example.com'
    primaries:
      - 10.11.0.4
    networks:
      - '192.0.2'
    ipv6_networks:
      - '2001:db9::/48'
    name_servers:
      - ns1.acme-inc.com.
      - ns2.acme-inc.com.
    hostmaster_email: admin
    hosts:
      - name: srv001
        ip: 192.0.2.1
        ipv6: '2001:db9::1'
        aliases:
          - www
      - name: srv002
        ip: 192.0.2.2
        ipv6: '2001:db9::2'
      - name: mail001
        ip: 192.0.2.10
        ipv6: '2001:db9::3'
    mail_servers:
      - name: mail001
        preference: 10

  - name: 'acme-inc.com'
    primaries:
      - 10.11.0.4
    networks:
      - '10.11'
    ipv6_networks:
      - '2001:db8::/48'
    name_servers:
      - ns1
      - ns2
    hosts:
      - name: ns1
        ip: 10.11.0.4
      - name: ns2
        ip: 10.11.0.5
      - name: srv001
        ip: 10.11.1.1
        ipv6: 2001:db8::1
        aliases:
          - www
      - name: srv002
        ip: 10.11.1.2
        ipv6: 2001:db8::2
        aliases:
          - mysql
      - name: mail001
        ip: 10.11.2.1
        ipv6: 2001:db8::d:1
        aliases:
          - smtp
          - mail-in
      - name: mail002
        ip: 10.11.2.2
        ipv6: 2001:db8::d:2
      - name: mail003
        ip: 10.11.2.3
        ipv6: 2001:db8::d:3
        aliases:
          - imap
          - mail-out
      - name: srv010
        ip: 10.11.0.10
      - name: srv011
        ip: 10.11.0.11
      - name: srv012
        ip: 10.11.0.12
    mail_servers:
      - name: mail001
        preference: 10
      - name: mail002
        preference: 20
    services:
      - name: _ldap._tcp
        weight: 100
        port: 88
        target: srv010
    text:
      - name: _kerberos
        text: KERBEROS.ACME-INC.COM
      - name: '@'
        text:
          - 'some text'
          - 'more text'
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
