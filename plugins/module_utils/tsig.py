"""Helpers for BIND TSIG key secrets."""

from __future__ import absolute_import, annotations

import base64
import binascii


def ensure_base64_secret(secret: str | None) -> str | None:
    """Return a TSIG key secret as valid base64.

    TSIG secrets must be base64 encoded. If the given secret already is
    canonical base64 it is returned unchanged (so a value encoded elsewhere is
    not encoded twice); otherwise the raw secret is base64 encoded.

    The very same normalisation must be applied everywhere a secret is
    consumed - the nsupdate client AND the named ``key { ... }`` statement -
    so that both sides derive identical key bytes. Otherwise the signature
    verification fails with BADKEY.

    Args:
        secret: The TSIG secret as provided by the user (base64 or plain text).

    Returns:
        A base64 encoded secret, or the input unchanged when it is empty.
    """
    if not secret:
        return secret

    try:
        decoded = base64.b64decode(secret, validate=True)
        # Only treat it as base64 if it round-trips canonically.
        if base64.b64encode(decoded).decode("ascii") == secret:
            return secret
    except (binascii.Error, ValueError):
        pass

    return base64.b64encode(secret.encode("utf-8")).decode("ascii")
