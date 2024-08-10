#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, division, print_function
import os
import json
import hashlib

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = """
module: knot_zone
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

short_description: TBD
description: TBD

options:
  state:
    description:
      - Whether to install (C(present)), or remove (C(absent)) a package.
    default: present
    required: true

  zone:
    description: []
    required: true
    type: str
  zone_ttl:
    description: []
    required: true
    type: int
  zone_soa:
    description: []
    required: true
    type: dict
  name_servers:
    description: []
    required: true
    type: dict
  records:
    description: []
    required: true
    type: dict
  debug:
    description: []
    required: false
    type: bool
    default: false
  database_path:
    description: []
    required: true
    type: str
  owner:
    description: []
    required: false
    type: str
  group:
    description: []
    required: false
    type: str
  mode:
    description: []
    required: false
    type: str
    default: 0666

"""

EXAMPLES = r"""
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class KnotZoneConfig(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.state = module.params.get("state")
        #
        self.zone = module.params.get("zone")
        self.zone_ttl = module.params.get("zone_ttl")
        self.zone_soa = module.params.get("zone_soa")
        self.name_servers = module.params.get("name_servers")
        self.records = module.params.get("records")

        self.database_path = module.params.get("database_path")
        self.owner = module.params.get("owner")
        self.group = module.params.get("group")
        self.mode = module.params.get("mode")

        self.zone_path = f"{self.database_path}"
        self.config_file = f"{self.zone_path}/{self.zone}.zone"
        self.config_checksum = f"{self.zone_path}/.{self.zone}.checksum"
        self.config_serial = f"{self.zone_path}/.{self.zone}.serial"

        # self.module.log(msg="---------------------------------------------")
        # self.module.log(msg="zone_path      : {}".format(self.zone_path))
        # self.module.log(msg="config_file    : {}".format(self.config_file))
        # self.module.log(msg="config_checksum: {}".format(self.config_checksum))
        # self.module.log(msg="config_serial  : {}".format(self.config_serial))
        # self.module.log(msg="---------------------------------------------")

    def run(self):
        """
            run
        """
        if self.state == 'absent':
            """
                remove created zone directory
            """
            _changed = False
            for f in [self.config_file, self.config_checksum, self.config_serial]:
                if os.path.isdir(f):
                    _changed = True
                    os.remove(f)

            return dict(
                changed=_changed,
                failed=False,
                msg="zone removed"
            )

        create_directory(directory=self.zone_path, mode="0750")

        _checksum = ''
        _old_checksum = ''
        _data_changed = False

        data = dict()

        data.update({
            "zone": self.zone,
            "zone_ttl": self.zone_ttl,
            "soa": self.zone_soa,
            "name_servers": self.name_servers,
            "records": self.records
        })

        # self.module.log(msg="---------------------------------------------")
        # self.module.log(msg="data      : {}".format(json.dumps(data, sort_keys=True)))
        # self.module.log(msg="---------------------------------------------")

        _checksum = self.__checksum(json.dumps(data, sort_keys=True))

        if os.path.isfile(self.config_checksum):
            with open(self.config_checksum, "r") as fp:
                _old_checksum = fp.readlines()[0]

        if _old_checksum == _checksum:
            return dict(
                changed=False,
                failed=False,
                msg=f"zone file {self.zone} has no changes."
            )
        else:
            if os.path.isfile(self.config_file):
                msg = f"zone file {self.zone} successfully updated."
            else:
                msg = f"zone file {self.zone} successfully created."

            _data_changed = True

        soa_serial = self.__zone_serial()
        data["soa"]["serial"] = soa_serial

        self.__write_template(self.config_file, data)

        with open(self.config_serial, "w") as fp:
            fp.write(soa_serial)

        with open(self.config_checksum, "w") as fp:
            fp.write(_checksum)

        return dict(
            changed=_data_changed,
            failed=False,
            soa_serial=soa_serial,
            msg=msg
        )

    def __zone_serial(self):
        """

        """
        from datetime import datetime

        now = datetime.now().strftime("%Y%m%d")
        id = "01"

        if os.path.isfile(self.config_serial):
            with open(self.config_serial, 'r') as fp:
                _serial = fp.read()

            # self.module.log(msg="serial    : {}".format(_serial))
            # self.module.log(msg="date      : {}".format(_serial[:-2]))
            # self.module.log(msg="number    : {}".format(_serial[8:]))

            if now == _serial[:-2]:
                id = int(_serial[8:])
                # id = id + 1
                id = "{0:02d}".format(id + 1)

        _serial = f"{now}{id}"

        # self.module.log(msg="serial      : {}".format(_serial))

        return _serial

    def __checksum(self, plaintext):
        """
            create checksum from string
        """
        _bytes = plaintext.encode('utf-8')
        _hash = hashlib.sha256(_bytes)

        return _hash.hexdigest()

    def __write_template(self, file_name, data):
        """
        """
        tpl = """
$ORIGIN {{ item.zone }}.
$TTL {{ item.zone_ttl }}

@  SOA  {{ item.soa.primary_dns }}. {{ item.soa.hostmaster }}. (
    {{ item.soa.serial.ljust(2) }}  ; serial
    {{ (item.soa.refresh | default('6h')).ljust(10) }}  ; refresh
    {{ (item.soa.retry | default('1h')).ljust(10) }}  ; retry
    {{ (item.soa.expire | default('1w')).ljust(10) }}  ; expire
    {{ item.soa.minimum | default('1d') }})         ; minimum

{% if item.name_servers | count > 0 %}
    {% for k, v in item.name_servers.items()  %}
{{ (v.ttl | default('3600')).ljust(10).rjust(42) }}  {{ "NS".ljust(19) }}  {{ (k + '.') }}
{{ (k + '.').ljust(30) }}  {{ (v.ttl | default('3600')).ljust(10) }}  {{ "A".ljust(19) }}  {{ v.ip }}
    {% endfor %}
{% endif %}

{% if item.records | count > 0 %}
    {% for k, v in item.records.items()  %}
        {% if v.description is defined and v.description | length != 0 %}
;; {{ v.description }}
        {% endif %}
        {% if k == '@' %}
            {% set source = item.zone %}
        {% else %}
            {% set source = v %}
        {% endif -%}
        {% if v.type == 'A' %}
{{ (k + '.').ljust(30) }}  {{ (v.ttl | default('3600')).ljust(10) }}  {{ v.type.ljust(20) }} {{ v.ip }}
            {% if v.aliases is defined and v.aliases | count > 0 %}
                {% for a in v.aliases %}
                    {% set _source = a + '.' + item.zone %}
                    {% set _type = 'CNAME' %}
{{ (_source + '.').ljust(30) }}  {{ (v.ttl | default(item.zone_ttl) | string).ljust(10) }}  {{ _type.ljust(20) }} {{ (k + '.') }}
                {% endfor %}
            {% endif %}
        {% endif %}
        {% if v.type == 'CNAME' %}
{{ (k + '.').ljust(30) }}  {{ (v.ttl | default('3600')).ljust(10) }}  {{ v.type.ljust(20) }} {{ v.target }}.
        {% endif %}
        {% if v.type == 'TXT' %}
{{ (source + '.').ljust(30) }}  {{ (v.ttl | default('3600')).ljust(10) }}  {{ v.type.ljust(20) }} "{{ v.text }}"
        {% endif %}
        {% if v.type == 'SRV' %}
{{ (k + '.').ljust(30) }}  {{ (v.ttl | default('3600')).ljust(10) }}  {{ v.type.ljust(20) }} {{ v.priority }} {{ v.weight }} {{ v.port }} {{ v.target }}.
        {% endif %}
    {% endfor %}
{% endif %}

"""
        from jinja2 import Template

        tm = Template(tpl, trim_blocks=True, lstrip_blocks=True)
        d = tm.render(item=data)

        with open(file_name, "w") as fp:
            fp.write(d)

        return True


# ---------------------------------------------------------------------------------------
# Module execution.
#

def main():
    """
    """
    args = dict(
        state=dict(
            default="present",
            choices=["absent", "present"]
        ),
        #
        zone=dict(
            required=True,
            type='str'
        ),
        zone_ttl=dict(
            required=True,
            type='int'
        ),
        zone_soa=dict(
            required=True,
            type='dict'
        ),
        name_servers=dict(
            required=True,
            type='dict'
        ),
        records=dict(
            required=True,
            type='dict'
        ),
        debug=dict(
            required=False,
            type="bool",
            default=False
        ),
        database_path=dict(
            required=True,
            type='str'
        ),
        owner=dict(
            required=False,
            type='str'
        ),
        group=dict(
            required=False,
            type='str'
        ),
        mode=dict(
            required=False,
            type='str',
            default="0666"
        ),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
    )

    c = KnotZoneConfig(module)
    result = c.run()

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
