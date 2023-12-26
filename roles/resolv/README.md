# Ansible role `resolv`

An Ansible role to configure /etc/resolv.conf

## defaults

| Variable Name       | Required  | Default Value | Type   | Description  |
| :---                | :---:     | :---:         | :---:  | :---         |
| `resolv_nameservers`| **yes**   | []            | list   | A list of up to 3 nameserver IP addresses |
| `resolv_domain`     | no        | ""            | string | Local domain name                         |
| `resolv_search`     | no        | []            | list   | List of up to 6 domains to search for host-name lookup |
| `resolv_sortlist`   | no        | []            | list   | List of IP-address and netmask pairs to sort addresses returned by gethostbyname. |
| `resolv_options`    | no        | []            | list   | List of options to modify certain internal resolver variables. |
