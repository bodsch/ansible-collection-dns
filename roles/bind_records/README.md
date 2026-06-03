# Ansible Role: `bodsch.dns.bind_records`

Manage BIND DNS records with static zone files and dynamic DDNS updates.

## Overview

The `bodsch.dns.bind_records` role provides flexible DNS record management for BIND:

- **Static zones**: Generate zone files from structured data, write the matching
  `zone { ... }` declarations into a named.conf include, and reload via `rndc`
- **Dynamic zones**: Update records via DDNS (nsupdate) without reloading zone files
- **Hybrid mode**: Combine both approaches (primary zones as files, some records dynamic)
- **Pairs with the `bind` role**: the role generates the zone declarations; the
  `bind` role wires the include into `named.conf` and defines the TSIG keys
  (see [named.conf integration](#namedconf-integration))

## Features

- Idempotent zone file generation with content-based change detection
- Idempotent DDNS updates: change is detected by comparing the SOA serial
  before/after the update (a no-op `update add` does not report `changed`)
- Automatic `zone { ... }` declarations written into a named.conf include
- TSIG-authenticated DDNS updates (HMAC-SHA256, HMAC-SHA512, etc.); plain-text
  secrets are normalised to base64 consistently on client and server
- Dynamic zones are reloaded with `rndc freeze`/`thaw`, newly declared zones
  with `rndc reconfig`, changed static zones with `rndc reload`
- Graceful fallback if rndc or nsupdate unavailable
- Full Ansible check mode support
- Zone state caching for smart reloads (only reload changed zones)

## Requirements

- `bind` installed and running on the managed node
- `rndc` available and working (control channel configured; the `bodsch.dns.bind`
  role sets this up automatically)
- `nsupdate` available (for dynamic zone updates)
- The zone-declaration include (`bind_records_zones_file`) must be referenced by
  `named.conf` — the `bodsch.dns.bind` role does this automatically
- For DDNS: a matching TSIG key defined server-side (`bind_update_keys`) and the
  target zone must allow updates (`allow-update` / `update-policy`)
- `python3-dnspython` on the managed node (used for SOA-based change detection;
  installed by the `bodsch.dns.bind` role)
- Python 3.7+

## Role Variables

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_records_manage_zones` | `true` | Enable zone management |
| `bind_records_mode` | `static` | Mode: `static`, `dynamic`, or `hybrid` |

### Zone File Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_records_zone_dir` | `/etc/bind/zones` | Directory for zone files |
| `bind_records_zones_file` | `/etc/bind/records.zones.conf` | named.conf include the role writes the `zone { ... }` declarations into. Must match `bind_records_zones_file` of the `bind` role (which includes it into named.conf). On Arch the default is `/var/named/records.zones.conf`. |
| `bind_records_zone_owner` | `bind` | Zone file owner |
| `bind_records_zone_group` | `bind` | Zone file group |
| `bind_records_zone_file_mode` | `0640` | Zone file permissions |

### RNDC Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_records_rndc_path` | `/usr/sbin/rndc` | Path to rndc binary |
| `bind_records_rndc_config` | `null` | Path to rndc.conf (uses system default if null) |

### DDNS/nsupdate Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_records_ddns_enabled` | `false` | Enable DDNS updates |
| `bind_records_nsupdate_path` | `/usr/bin/nsupdate` | Path to nsupdate binary |
| `bind_records_nsupdate_server` | `127.0.0.1` | Server the updates are sent to. Without it nsupdate resolves the target from the zone's SOA primary, which for public zone names targets the wrong server. |
| `bind_records_nsupdate_port` | `53` | Port of the target server |
| `bind_records_nsupdate_key` | `null` | TSIG key name (must match a key defined server-side via `bind_update_keys`) |
| `bind_records_nsupdate_key_secret` | `null` | TSIG key secret. Plain text is accepted and normalised to base64; the server-side key must use the **same** secret. |
| `bind_records_nsupdate_key_algorithm` | `HMAC-SHA256` | TSIG algorithm |
| `bind_records_nsupdate_auto_load_keys` | `true` | Auto-load from `bind_update_keys` if available |

### Zone/Record Data

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_records_zones` | `[]` | List of zones to manage (static mode) |
| `bind_records_updates` | `[]` | List of DDNS updates (dynamic mode) |
| `bind_records_cache_directory` | `/var/cache/ansible/bind-records` | Cache for zone state tracking |

## named.conf integration

For static / hybrid zones the role does two things:

1. It writes the zone **data files** into `bind_records_zone_dir`.
2. It writes the matching `zone "..." { ... };` **declarations** into the include
   file `bind_records_zones_file` and then runs `rndc reconfig` so BIND loads any
   newly declared zones.

For BIND to know about these zones, `named.conf` must `include` that file. The
`bodsch.dns.bind` role handles this automatically as long as both roles agree on
the path (`bind_records_zones_file`). Likewise, TSIG keys defined via
`bind_update_keys` / `bind_dns_keys` are written to `auth_update.conf` /
`auth_transfer.conf` and auto-included into `named.conf` by the `bind` role.

How changed zones are reloaded:

| Situation | Action taken |
|-----------|--------------|
| New zone declared | `rndc reconfig` (loads the new zone) |
| Changed static zone | `rndc reload <zone>` |
| Changed dynamic zone (has `update_policy`/`allow-update`) | `rndc freeze` → rewrite file → `rndc thaw` |

> **Hybrid caveat:** when a zone is both file-managed and DDNS-updated, rewriting
> the static file overwrites records that were added dynamically since the last
> run. Treat the static file as the source of truth for the base records.

## Usage Examples

### Example 1: Static Zone Management

Manage zones via zone files (traditional approach):

```yaml
- name: Configure BIND zones
  hosts: ns1.example.com
  vars:
    bind_records_zones:
      - name: example.com
        type: primary
        hosts:
          - name: www
            ip: 192.0.2.10
            aliases:
              - web
              - web.example.com
          - name: mail
            ip: 192.0.2.20
        mail_servers:
          - name: mail.example.com
            preference: 10
        name_servers:
          - ns1.example.com.
          - ns2.example.com.
        networks:
          - 192.0.2.0/24
  roles:
    - bind_records
```

### Example 2: Dynamic DDNS Updates

Update records dynamically without zone file reloads:

```yaml
- name: Add servers dynamically
  hosts: ns1.example.com
  vars:
    bind_records_mode: dynamic
    bind_records_ddns_enabled: true
    bind_records_nsupdate_key: ddns-update-key
    bind_records_nsupdate_key_secret: "your-secret-key-here"
    bind_records_updates:
      - zone: example.com
        updates:
          - "update add srv001.example.com. 300 A 192.0.2.50"
          - "update add srv002.example.com. 300 A 192.0.2.51"
      - zone: ops.example.com
        updates:
          - "update add monitor.ops.example.com. 300 A 10.0.0.100"
  roles:
    - bind_records
```

> **DDNS prerequisites:** the key named in `bind_records_nsupdate_key` must be
> defined server-side (`bind_update_keys`) **and** the target zone must permit
> updates with it (`allow-update` / `update_policy`). See
> [`examples/07-ddns-update-policy.yml`](examples/07-ddns-update-policy.yml) for a
> complete, working setup.

### Example 3: Hybrid Mode

Manage primary zones as files, some records dynamically:

```yaml
- name: Hybrid zone management
  hosts: ns1.example.com
  vars:
    bind_records_mode: hybrid
    
    # Static zones
    bind_records_zones:
      - name: example.com
        type: primary
        hosts:
          - name: ns1
            ip: 192.0.2.1
          - name: ns2
            ip: 192.0.2.2
        name_servers:
          - ns1.example.com.
          - ns2.example.com.
    
    # Dynamic record updates
    bind_records_ddns_enabled: true
    bind_records_nsupdate_key: ddns-key
    bind_records_nsupdate_key_secret: "key-secret"
    bind_records_updates:
      - zone: example.com
        updates:
          - "update add web1.example.com. 300 A 192.0.2.100"
          - "update add web2.example.com. 300 A 192.0.2.101"
  roles:
    - bind_records
```

### Example 4: Secondary Zone with Dynamic Updates

```yaml
- name: Secondary zone with dynamic updates
  hosts: ns2.example.com
  vars:
    bind_records_mode: hybrid
    bind_records_zones:
      - name: example.com
        type: secondary
        primaries:
          - 192.0.2.1    # Primary NS IP
    
    bind_records_ddns_enabled: true
    bind_records_updates:
      - zone: example.com
        updates:
          - "update add staging.example.com. 300 A 10.0.0.50"
  roles:
    - bind_records
```

### Example 5: TSIG-Authenticated DDNS

```yaml
- name: DDNS with TSIG authentication
  hosts: ns1.example.com
  vars:
    bind_records_mode: dynamic
    bind_records_ddns_enabled: true
    
    # TSIG credentials
    bind_records_nsupdate_key: "internal-ddns"
    bind_records_nsupdate_key_secret: "{{ vault_ddns_secret }}"
    bind_records_nsupdate_key_algorithm: HMAC-SHA256
    
    bind_records_updates:
      - zone: internal.example.com
        updates:
          - "update add api.internal.example.com. 300 A 10.0.0.10"
          - "update add db.internal.example.com. 300 A 10.0.0.11"
  roles:
    - bind_records
```

## Advanced Usage

### Auto-Load TSIG Keys from bind Role

If using both `bind` and `bind_records` roles, TSIG keys can auto-load:

```yaml
- name: Configure BIND with auto-loaded DDNS keys
  hosts: ns1.example.com
  vars:
    # From bind role
    bind_update_keys:
      - name: ddns-host1
        algorithm: hmac-sha256
        secret: "secret-key-1"
    
    bind_records_nsupdate_auto_load_keys: true  # Auto-load above
    bind_records_ddns_enabled: true
  roles:
    - bind
    - bind_records
```

### Check Mode

Test zone configuration without applying changes:

```bash
ansible-playbook site.yml --check --diff
```

### Individual Zone Reloads

Only zones with content changes trigger rndc reload (idempotent):

```yaml
- name: Smart zone management
  hosts: ns1.example.com
  vars:
    bind_records_zones:
      - name: zone1.com
        type: primary
        hosts: [...]
      - name: zone2.com
        type: primary
        hosts: [...]  # Modified
  # Result: Only zone2.com triggers rndc reload
  roles:
    - bind_records
```

## Variables Example File

Create `host_vars/ns1.example.com.yml`:

```yaml
---
# Zone storage
bind_records_zone_dir: /etc/bind/zones
bind_records_zone_owner: bind
bind_records_zone_group: bind

# RNDC
bind_records_rndc_path: /usr/sbin/rndc
bind_records_rndc_config: /etc/bind/rndc.conf

# DDNS
bind_records_ddns_enabled: true
bind_records_nsupdate_key: ddns-key
bind_records_nsupdate_key_secret: "{{ vault_nsupdate_secret }}"

# Zones
bind_records_zones:
  - name: example.com
    type: primary
    hosts:
      - name: www
        ip: 192.0.2.10
      - name: mail
        ip: 192.0.2.20
    mail_servers:
      - name: mail.example.com
        preference: 10
    name_servers:
      - ns1.example.com.
      - ns2.example.com.
    networks:
      - 192.0.2.0/24

# Dynamic updates
bind_records_updates:
  - zone: example.com
    updates:
      - "update add staging.example.com. 300 A 10.0.0.50"
```

## Role Dependencies

- No hard role dependency, but designed to **pair with `bodsch.dns.bind`**, which
  provides the working `rndc` control channel, includes `bind_records_zones_file`
  into `named.conf`, and defines/auto-includes the TSIG keys.
- Standalone use is possible if you wire these up yourself: a usable `rndc`,
  `named.conf` including `bind_records_zones_file`, and (for DDNS) a server-side
  TSIG key plus `allow-update`/`update-policy` on the zone.
- Assumes BIND is already installed and `rndc`/`nsupdate`/`dnspython` are available.

## Zone Data Format

Zone definitions follow the same structure as the `bind` role:

```yaml
bind_records_zones:
  - name: example.com                    # Zone name (required)
    type: primary                        # primary|secondary|forward
    
    # Primary zone records
    hosts:
      - name: host1
        ip: 192.0.2.10
        ipv6: 2001:db8::1
        aliases: [www, web]
    
    mail_servers:
      - name: mail.example.com
        preference: 10
    
    services:
      - name: _ldap._tcp
        target: ldap-server
        weight: 100
        port: 389
    
    text:
      - name: _kerberos
        text: [KERBEROS.REALM]
    
    name_servers:
      - ns1.example.com.
      - ns2.example.com.
    
    # Reverse zones
    networks:
      - 192.0.2.0/24
      - 10.0.0.0/16
    
    ipv6_networks:
      - 2001:db8::/32
    
    # Secondary zone settings
    primaries:
      - 192.0.2.1
    
    # Forward zone settings
    forwarders:
      - 8.8.8.8

    # Dynamic updates (makes the zone dynamic -> reloaded via freeze/thaw)
    update_policy:
      mode: rules                      # local | rules
      rules:
        - action: grant                # grant | deny
          identity: ddns-key           # TSIG key name
          ruletype: subdomain          # name | subdomain | zonesub | self | ...
          name: example.com.           # subject (depends on ruletype)
          types: [A, AAAA, TXT]
```

## Troubleshooting

### rndc: connection refused

Ensure:
- BIND is running: `systemctl status bind9`
- rndc.key exists: `/etc/bind/rndc.key`
- rndc permissions: `ls -l /etc/bind/rndc.key`

### rndc: 'reload' failed: dynamic zone

The zone has an `update-policy`/`allow-update` and is therefore dynamic; it cannot
be reloaded with `rndc reload`. The role handles this with `freeze`/`thaw` for
zones it detects as dynamic (those carrying `update_policy`). If you hit this,
make sure the zone's `update_policy` is part of `bind_records_zones`.

### nsupdate: NOTAUTH(BADKEY)

`BADKEY` means the server does **not know the key** (RFC 2845 error 17), not a
secret mismatch. Check:

- The key is defined server-side in `bind_update_keys` with the **same name** as
  `bind_records_nsupdate_key` (e.g. `ddns-key`).
- The key file (`auth_update.conf`) is included in `named.conf` — `rndc tsig-list`
  shows the keys the server actually knows.

### nsupdate: NOTAUTH(BADSIG) / tsig verify failure

The key name is known but the secret does not match. The client and the server
key must use the **same** secret value (`bind_records_nsupdate_key_secret` and the
`bind_update_keys` entry). Plain-text secrets are normalised to base64
identically on both sides, so use the same source value (ideally a vault var).

### nsupdate: update failed (other)

Check:

- DDNS allowed on the zone: `allow-update { key ...; };` or `update-policy { ... };`
- Updates reach the local server: `bind_records_nsupdate_server` (default
  `127.0.0.1`) — without it nsupdate may target a public server via the SOA.
- BIND log: `journalctl -u bind9 -f` (Debian) / `journalctl -u named -f` (Arch)

### Zone file permissions

Ensure bind user owns zone directory:
```bash
chown bind:bind /etc/bind/zones
chmod 0770 /etc/bind/zones
```

## License

Apache License 2.0

## Author

Bodo Schulz (@bodsch)
