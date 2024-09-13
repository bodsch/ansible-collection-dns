# python 3 headers, required if submitting to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display
# from ansible_collections.bodsch.dns.plugins.module_utils.network_type import reverse_dns

# import json
# import netaddr
# import hashlib
# import time
# import re

display = Display()

# ---------------------------------------------------------------------------------------

DOCUMENTATION = """
name: bind
version_added: 0.9.0
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"

description: TBD
short_description: TBD
"""

EXAMPLES = """
"""

RETURN = """
"""

# ---------------------------------------------------------------------------------------


class FilterModule(object):
    """
    """

    def filters(self):
        return {
            'unbound_helper': self.unbound_helper,
        }

    def unbound_helper(self, helper_1, helper_2):
        """
        """
        display.v(f"unbound_helper({helper_1}, {helper_2})")

        display.v(f"  - 1: {helper_1}")
        display.v(f"  - 2: {helper_2})")

        helper_1_exists = helper_1.get('stat', {}).get('path', None)
        helper_2_exists = helper_2.get('stat', {}).get('path', None)

        if helper_1_exists:
            return helper_1_exists
        elif helper_2_exists:
            return helper_2_exists
        else:
            return None
