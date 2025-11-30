#

import datetime


def generate_serial(base_serial=None):
    """ """
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    counter = 1
    serial = int(f"{today}{counter:02d}")

    # Optional: existing serial auslesen und erhöhen
    if base_serial and str(base_serial).startswith(today):
        old_counter = int(str(base_serial)[-2:])
        counter = old_counter + 1
        serial = int(f"{today}{counter:02d}")

    return serial


def fqdn(zone, name):
    """
    Wandelt Kurzformen in FQDNs um:
      - 'srv001' + 'acme-inc.com'     → 'srv001.acme-inc.com.'
      - 'srv001.acme-inc.com.'        → bleibt unverändert
      - '@' + 'acme-inc.com'          → 'acme-inc.com.'
    """
    if name == "@":
        return f"{zone}."  # root of the zone
    if name.endswith("."):
        return name
    if name.endswith(zone):
        return f"{name}."

    return f"{name}.{zone}."


def build_rrset(
    name, rtype, ttl, records, changetype="REPLACE", comment=None, account=None
):

    rrset = {
        "name": name if name.endswith(".") else f"{name}.",
        "type": rtype,
        "ttl": ttl,
        "changetype": changetype,
        "records": [
            {"content": r if isinstance(r, str) else r["content"], "disabled": False}
            for r in records
        ],
    }

    if comment:
        rrset["comments"] = [
            {
                "content": comment,
                "account": account or "",
            }
        ]

    return rrset
