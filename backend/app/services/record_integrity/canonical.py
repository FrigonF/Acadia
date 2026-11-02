"""Canonical JSON formatting and cryptographic integrity functions."""
import json
import hashlib
from typing import Dict, Any

def create_canonical_json(data: Dict[str, Any]) -> str:
    """Deterministically formats record dictionary into canonical JSON string.
    - Keys are sorted lexicographically.
    - No unnecessary whitespace.
    - Unicode strings preserved consistently.
    """
    # Exclude dynamic/system-only fields from fingerprint
    ignored_keys = {"created_at", "updated_at", "batch_id", "versions", "credentials", "validation_issues"}
    cleaned = {k: v for k, v in data.items() if k not in ignored_keys}
    return json.dumps(cleaned, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def compute_record_fingerprint(canonical_json: str) -> str:
    """Generates SHA-256 hex digest of the canonical JSON string."""
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def verify_record_fingerprint(canonical_json: str, expected_fingerprint: str) -> bool:
    """Verifies that the recalculated SHA-256 fingerprint matches the expected one."""
    calculated = compute_record_fingerprint(canonical_json)
    return hmac_compare(calculated, expected_fingerprint)

def hmac_compare(val1: str, val2: str) -> bool:
    """Constant time string comparison to prevent timing attacks."""
    import hmac
    return hmac.compare_digest(val1.strip(), val2.strip())
