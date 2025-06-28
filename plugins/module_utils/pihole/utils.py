
from urllib.parse import urlparse
from typing import List, Dict, Any

def sanitize_adlist(adlists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    cleaned = []

    for ad in adlists:
        address = ad.get("address")
        if not address:
            continue

        # normalize (e.g., strip whitespaces, lowercase if needed)
        address = address.strip()

        # validate URL
        parsed = urlparse(address)
        if not parsed.scheme.startswith("http"):
            continue  # skip invalid

        if address in seen:
            continue  # skip duplicates

        seen.add(address)

        cleaned.append(dict(
            address=address,
            comment=ad.get("comment", ""),
            enabled=ad.get("enabled", True)
        ))

    return cleaned
