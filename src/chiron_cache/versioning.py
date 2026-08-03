"""Content-hash versioning for Raw Atoms (AD-5).

``raw_version`` is a hash of the data itself, never a timestamp or arrival
time — two calls over the same logical content must produce byte-identical
digests regardless of dict key order or Python construction path.
"""

import hashlib
import json
from typing import Any


def compute_raw_version(data: Any) -> str:
    """Return the SHA-256 hex digest of ``data``'s canonical JSON serialization."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
