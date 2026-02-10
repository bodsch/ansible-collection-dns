# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

from typing import List, Sequence

__metaclass__ = type

from ansible.utils.display import Display

display = Display()

# ---------------------------------------------------------------------------------------


class FilterModule(object):
    """ """

    def filters(self):
        return {
            "knot_resolver_service": self.knot_resolver_service,
        }

    def knot_resolver_service(
        self, data: Sequence[str], os_family: str, count: int, service: str
    ):
        """ """
        display.v(
            f"knot_resolver_service(data: {data}, os_family: {os_family}, count: {count}, service: {service})"
        )

        _service: List = []

        family = (os_family or "").strip().lower()

        if family == "archlinux":
            _service.append(data)
        elif family == "debian":
            for i in range(1, count + 1):
                _service.append(service.replace("@.", f"@{i}."))

        display.v(f"  = {_service}")
        return _service
