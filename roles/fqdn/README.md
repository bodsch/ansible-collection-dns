fqdn [![Build Status](https://travis-ci.org/holms/ansible-fqdn.svg?branch=master)](https://travis-ci.org/holms/ansible-fqdn)
====

Sets Fully qualified domain name (FQDN)

Requirements
------------

Ansible version 2.10+

## Platforms

* ArchLinux
* ArtixLinux
* Ubuntu
* Debian
* Centos
* Redhat
* Windows

Role Variables
--------------


| Variable name | Variable value | Default |
|---------------|----------------|---------|
|*hostname*     | hostname (eg. vm1) | `inventory_hostname_short` |
|*fqdn*         | domain name (eg. vm1.test.com) | `inventory_hostname` |
|*ip_address*   | ip address (eg. 192.168.0.20) | `ansible_default_ipv4.address` |

Example
-------

```
- hosts: mx.mydomain.com:mx
  user: root

  roles:
    - role: fqdn
      vars:
        fqdn: "mx.mydomain.com"
        hostname: "mx"
```

License
-------

MIT

Author Information
------------------

Roman Gorodeckij (<holms@holms.lt>)
John Brooker (jb-github@outlook.com)
Bodo Schulz (bodo@boone-schulz.de)
