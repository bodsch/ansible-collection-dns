
import netaddr
from ansible_collections.bodsch.dns.plugins.module_utils.network_type import (
    is_valid_ipv4,
)


def reverse_zone_names(module, network):
    """ """
    module.log(f"reverse_zone_names({network})")

    # ----------------------------------------------------
    reverse_ip = None

    if is_valid_ipv4(network):

        # module.log(f"

        reverse_ip = ".".join(network.replace(network + ".", "").split(".")[::-1])
        # reverse_ip = ".".join(ip.split(".")[::-1])

        result = f"{reverse_ip}.in-addr.arpa"

    else:
        try:
            _offset = None
            if network.count("/") == 1:
                _prefix = network.split("/")[1]
                _offset = int(9 + int(_prefix) // 2)
                # module.log(msg=f" - {_prefix} - {_offset}")

            _network = netaddr.IPNetwork(str(network))
            _prefix = _network.prefixlen
            _ipaddress = netaddr.IPAddress(_network)
            reverse_ip = _ipaddress.reverse_dns

            if _offset:
                result = reverse_ip[-_offset:]

            if result[-1] == ".":
                result = result[:-1]

        except Exception as e:
            module.log(msg=f" =>  ERROR: {e}")
            pass

    if not result:
        module.log(
            msg=f" PROBLEM: {network} is neither a valid IPv4 nor a valid IPv6 network."
        )

    # module.log(msg=f" = '{result}'")

    return result
