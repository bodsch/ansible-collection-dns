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
            'pdns_backend_data': self.backend_data
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

        result = [v for k, v in packages.items() if k in data]

        return result

    def backend_data(self, data, backend):
        """
        """
        display.v(f"backend_data({data}, {backend})")

        def normalize(name):
            if name.startswith('g'):
                name = name[1:]
            return name.split(':')[0]

        pattern = re.compile(backend)

        result = [entry for entry in data if pattern.search(normalize(entry.get('name', '')))]

        display.v(f"= {result})")

        # for entry in data:
        #    name = entry.get('name', '')

        return result
