
# Ansible Role:  `bodsch.dns.hosts`

ansible role for configuring entries in the /etc/hosts file.


## usage

```yaml
hosts_add_default_ipv4: true
hosts_add_basic_ipv6: false

hosts_add_ansible_managed_hosts: false
hosts_add_ansible_managed_hosts_groups:
  - 'all'

hosts_cloud_template_location: "/etc/cloud/templates/hosts.{{ ansible_os_family | lower }}.tmpl"

hosts_ip_protocol: 'ipv4'

hosts_network_interface: "{{ ansible_default_ipv4.interface }}"

host_file_backup: false

# Custom hosts entries to be added
hosts_entries: []

# Custom host file snippets to be added
hosts_file_snippets: []
```

### `hosts_entries`

```yaml
hosts_entries:
  - ip: 192.168.11.1
    name: test.molecule.local
    aliases:
      - test
      - foo-test.molecule.local
```

### `hosts_file_snippets`

```yaml
```

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
