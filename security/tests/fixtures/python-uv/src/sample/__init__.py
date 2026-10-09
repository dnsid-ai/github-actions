"""Self-test target for the Python workflow."""

import hashlib


def checksum(data: bytes) -> str:
    """Return the hex MD5 of data."""
    # CANARY: ruff S324 (insecure hash) and Semgrep must flag this line.
    return hashlib.md5(data).hexdigest()
