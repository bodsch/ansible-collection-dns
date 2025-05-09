# -*- coding: utf-8 -*-
# Copyright 2023-2024 Bodo Schulz <bodo@boone-schulz.de>


# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re

from ansible.plugins.test.core import version_compare
from ansible.utils.display import Display

# ---------------------------------------------------------------------------------------

display = Display()


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'pdns_backend_types': self.backend_types,
            'pdns_backend_packages': self.backend_packages,
            'pdns_backend_data': self.backend_data,
            'pdns_config_upgrades': self.config_upgrades,
        }

    def backend_types(self, data, version):
        """
            input:
                ```
                backend_types:
                  - name: 'gmysql:one'
                    user: powerdns
                    host: localhost
                    password: "{{ vault__pdns.database_pdns }}"
                    dbname: pdns
                    credentials: {}

                  - name: 'gmysql:two'
                    user: pdns_user
                    host: 192.0.2.15
                    port: 3307
                    password: my_password
                    dbname: dns
                    credentials: {}

                  - name: bind
                    config: '/etc/named/named.conf'
                    hybrid:  true
                    dnssec-db: '{{ pdns_config_dir }}/dnssec.db'

                  - name: gsqlite3
                    database: /var/lib/powerdns/pdns.db
                    dnssec: true
                ```
            output:
                ```
                ['bind', 'mysql', 'sqlite3']
                ```
        """
        display.v(f"backend_types({data}, {version})")
        result = []
        names = set()
        for entry in data:
            name = entry.get('name', '')
            if name.startswith('g'):
                name = name[1:]             # entferne führendes 'g'
            name = name.split(':')[0]       # entferne alles ab dem ':'
            names.add(name)

        result = sorted(names)

        display.v(f"= {result})")

        return result

    def backend_packages(self, data, packages):
        """
            input:
                ```
                data: ['bind', 'mysql', 'sqlite3'],
                packages: {
                    'geo': 'pdns-backend-geo',
                    'geoip': 'pdns-backend-geoip',
                    'mysql': 'pdns-backend-mysql',
                    'pgsql': 'pdns-backend-pgsql',
                    'sqlite3': 'pdns-backend-sqlite3',
                    ...
                }
                ```
            output:
                ```
                ['pdns-backend-mysql', 'pdns-backend-sqlite3']
                ```
        """
        display.v(f"backend_packages({data}, {packages})")
        result = []

        result = self.flatten([v for k, v in packages.items() if k in data])

        display.v(f"= {result})")

        return result

    def backend_data(self, data, backend):
        """
        """
        # display.v(f"backend_data({data}, {backend})")

        def normalize(name):
            if name.startswith('g'):
                name = name[1:]
            return name.split(':')[0]

        pattern = re.compile(backend)

        result = [entry for entry in data if pattern.search(normalize(entry.get('name', '')))]

        # display.v(f"= {result})")

        return result

    def config_upgrades(self, data, version):
        """
            ersetzt veraltete config parameter
        """
        # display.v(f"config_upgrades({data}, {version})")

        def replace_keys(obj, version):
            key_map = {}
            if version_compare(str(version), '4.5', '>='):
                # https://doc.powerdns.com/authoritative/upgrading.html?highlight=master#to-4-9-0
                key_map.update({
                    "allow-unsigned-supermaster": "allow-unsigned-autoprimary",
                    "master": "primary",
                    "slave-cycle-interval": "xfr-cycle-interval",
                    "slave-renotify": "secondary-do-renotify",
                    "slave": "secondary",
                    "superslave": "autosecondary",
                    "domain-metadata-cache-ttl": "zone-metadata-cache-ttl",
                })

            if version_compare(str(version), '4.9', '>='):
                key_map.update({
                    "supermaster-config": "autoprimary-config",
                    "supermasters": "autoprimaries",
                    "supermaster-destdir": "autoprimary-destdir",
                    "info-all-slaves-query": "info-all-secondaries-query",
                    "supermaster-query": "autoprimary-query",
                    "supermaster-name-to-ips": "autoprimary-name-to-ips",
                    "supermaster-add": "autoprimary-add",
                    "update-master-query": "update-primary-query",
                    "info-all-master-query": "info-all-primary-query",
                })

            if isinstance(obj, dict):
                # Ersetze die Keys und rufe rekursiv für die Werte auf
                return {key_map.get(k, k): replace_keys(v, version) for k, v in obj.items()}
            elif isinstance(obj, list):
                # Falls es eine Liste ist, rekursiv die Elemente bearbeiten
                return [replace_keys(item, version) for item in obj]
            else:
                return obj

        # Ersetze die Keys im geladenen YAML
        result = replace_keys(data, version)

        # display.v(f"= result: {result}")

        return result


    def flatten(self, lst):
        """
            input: nested = [1, [2, [3, 4], 5], 6]
            output: [1, 2, 3, 4, 5, 6]

            input:  [1, 2, 3]
            output: [1, 2, 3]
        """
        result = []
        for item in lst:
            if isinstance(item, list):
                result.extend(self.flatten(item))
            else:
                result.append(item)
        return result
