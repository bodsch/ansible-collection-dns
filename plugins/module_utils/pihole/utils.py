# import math
from typing import Any, Dict, Generator, List
from urllib.parse import urlparse


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

        cleaned.append(
            dict(
                address=address,
                comment=ad.get("comment", ""),
                enabled=ad.get("enabled", True),
            )
        )

    return cleaned


def flatten_config_dict(
    data: Dict[str, Any], prefix: str = ""
) -> Generator[tuple[str, Any], None, None]:
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key

        # Wert ignorieren, wenn None oder leer (str, list, tuple)
        if value is None:
            continue
        if isinstance(value, (str, list, tuple)) and len(value) == 0:
            continue

        if isinstance(value, dict):
            # rekursiv in Subdicts
            yield from flatten_config_dict(value, prefix=full_key)
        else:
            yield full_key, value


def normalize_value(val: Any) -> Any:
    if isinstance(val, str):
        val_lower = val.lower()
        if val_lower == "true":
            return True
        elif val_lower == "false":
            return False
        elif val.isdigit():
            return int(val)
        try:
            # Float-Parsing, z. B. "55.000000"
            return float(val)
        except ValueError:
            pass
    elif isinstance(val, float) and val.is_integer():
        return int(val)
    return val


def is_equal(a: Any, b: Any) -> bool:
    return normalize_value(a) == normalize_value(b)
