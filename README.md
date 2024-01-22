# Ansible Collection - bodsch.dns

A collection of Ansible roles for DNS Stuff.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-collection-dns)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-collection-dns)][releases]

[ci]: https://github.com/bodsch/ansible-collection-dns/actions
[issues]: https://github.com/bodsch/ansible-collection-dns/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-collection-dns/releases


## supported operating systems

* Arch Linux
* Debian based
    - Debian 10 / 11
    - Ubuntu 20.10

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collection-prometheus/tags)!

---

## Roles

| Role                                                        | Build State | Description |
|:----------------------------------------------------------- | :---- | :---- |
| [bodsch.dns.bind](./roles/bind/README.md)                   | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/bind.yml?branch=main)][bind]       | Ansible role to install and configure `bind`. |
| [bodsch.dns.knot](./roles/knot/README.md)                   | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/knot.yml?branch=main)][knot]       | Ansible role to install and configure `knot`. |
| [bodsch.dns.knot_resolver](./roles/knot_resolver/README.md) | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/knot_resolver.yml?branch=main)][knot_resolver] | Ansible role to install and configure `knot-resolver`. |
| [bodsch.dns.dnsmasq](./roles/dnsmasq/README.md)             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/dnsmasq.yml?branch=main)][dnsmasq] | Ansible role to install and configure `dnsmasq`. |
| [bodsch.dns.fqdn](./roles/fqdn/README.md)                   | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/fqdn.yml?branch=main)][fqdn]       | Ansible role to install and configure `fqdn`. |
| [bodsch.dns.hosts](./roles/hosts/README.md)                 | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/hosts.yml?branch=main)][hosts]     | Ansible role to install and configure `hosts`. |
| [bodsch.dns.resolv](./roles/resolv/README.md)               | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/resolv.yml?branch=main)][resolv]   | Ansible role to install and configure `resolv`. |
| [bodsch.dns.unbound](./roles/unbound/README.md)             | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-dns/unbound.yml?branch=main)][unbound] | Ansible role to install and configure `unbound`. |



[bind]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/bind.yml
[knot]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/knot.yml
[knot_resolver]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/knot_resolver.yml
[dnsmasq]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/dnsmasq.yml
[fqdn]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/fqdn.yml
[hosts]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/hosts.yml
[resolv]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/resolv.yml
[unbound]: https://github.com/bodsch/ansible-collection-dns/actions/workflows/unbound.yml
