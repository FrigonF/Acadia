"""Tamper-evident Audit Logger Utility with Cryptographic Hash Chaining."""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy.orm import Session
from backend.app.models import AuditLog

def _compute_audit_hash(
    actor_email: Optional[str],
    action: str,
    target_type: str,
    target_id: Optional[str],
    previous_state: Optional[Dict[str, Any]],
    new_state: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]],
    timestamp_str: str,
    previous_hash: str
) -> str:
    """Computes deterministic SHA-256 hash for audit entry chaining."""
    canonical_dict = {
        "actor": actor_email or "SYSTEM",
        "action": action,
        "target_type": target_type,
        "target_id": target_id or "",
        "previous_state": previous_state or {},
        "new_state": new_state or {},
        "metadata": metadata or {},
        "timestamp": timestamp_str,
        "previous_hash": previous_hash
    }
    encoded = json.dumps(canonical_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def log_audit_event(
    db: Session,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Creates a tamper-evident audit log record linked cryptographically to the preceding entry."""
    now = datetime.now(timezone.utc)
    
    # 1. Fetch the latest audit log entry to establish hash chain link
    last_entry = db.query(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).first()
    prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else "GENESIS_AUDIT_ROOT"
    
    # 2. Compute SHA-256 hash chain digest
    entry_hash = _compute_audit_hash(
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        previous_state=previous_state,
        new_state=new_state,
        metadata=metadata,
        timestamp_str=now.isoformat(),
        previous_hash=prev_hash
    )

    audit_entry = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        previous_state=previous_state,
        new_state=new_state,
        event_metadata=metadata or {},
        ip_address=ip_address,
        timestamp=now,
        entry_hash=entry_hash,
        previous_entry_hash=prev_hash
    )
    db.add(audit_entry)
    db.commit()
    return audit_entry

def verify_audit_trail_integrity(db: Session, limit: int = 100) -> Dict[str, Any]:
    """Verifies the mathematical hash chain of the audit trail to detect tampering or deletions."""
    entries = db.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).limit(limit).all()
    if not entries:
        return {"status": "EMPTY", "verified_count": 0, "chain_valid": True}

    prev_hash = "GENESIS_AUDIT_ROOT"
    for idx, entry in enumerate(entries):
        if not entry.entry_hash:
            continue
        expected_prev = prev_hash
        # Recompute expected hash
        recomputed = _compute_audit_hash(
            actor_email=entry.actor_email,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            previous_state=entry.previous_state,
            new_state=entry.new_state,
            metadata=entry.event_metadata,
            timestamp_str=entry.timestamp.isoformat(),
            previous_hash=expected_prev
        )
        if entry.previous_entry_hash != expected_prev or entry.entry_hash != recomputed:
            return {
                "status": "TAMPER_DETECTED",
                "broken_at_id": entry.id,
                "broken_index": idx,
                "chain_valid": False,
                "verified_count": idx
            }
        prev_hash = entry.entry_hash

    return {
        "status": "CHAIN_VERIFIED",
        "verified_count": len(entries),
        "chain_valid": True
    }
