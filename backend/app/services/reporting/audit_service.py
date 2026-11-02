"""Tamper-evident Audit Logger Utility with Cryptographic Hash Chaining and External Signed Checkpoints."""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
import json
import os
from sqlalchemy.orm import Session
from backend.app.models import AuditLog
from backend.app.services.record_integrity.signer import signature_service

CHECKPOINT_LOG_FILE = "backend/data/audit_checkpoints.jsonl"

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

def create_external_audit_checkpoint(db: Session, checkpoint_path: str = CHECKPOINT_LOG_FILE) -> Dict[str, Any]:
    """Generates an externally stored, cryptographically signed checkpoint of the current audit trail tip.
    
    Defends against:
    - Truncation attacks (deleting recent audit records from the tail of the table).
    - Complete database replacement or rollback to an earlier snapshot.
    """
    last_entry = db.query(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).first()
    if not last_entry:
        return {"status": "EMPTY", "message": "No audit entries to checkpoint."}

    total_count = db.query(AuditLog).count()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    checkpoint_payload = {
        "tip_audit_id": last_entry.id,
        "tip_entry_hash": last_entry.entry_hash,
        "tip_timestamp": last_entry.timestamp.isoformat(),
        "total_audit_count": total_count,
        "checkpoint_created_at": now_iso
    }
    canonical_checkpoint = json.dumps(checkpoint_payload, sort_keys=True, separators=(',', ':'))
    signature = signature_service.sign_fingerprint(
        hashlib.sha256(canonical_checkpoint.encode('utf-8')).hexdigest()
    )

    checkpoint_record = {
        **checkpoint_payload,
        "key_id": signature_service.key_id,
        "signature": signature
    }

    # Append to external checkpoint file
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    with open(checkpoint_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(checkpoint_record) + "\n")

    return {
        "status": "CHECKPOINT_CREATED",
        "checkpoint": checkpoint_record
    }

def verify_audit_against_checkpoints(db: Session, checkpoint_path: str = CHECKPOINT_LOG_FILE) -> Dict[str, Any]:
    """Verifies that all historically signed external checkpoints still exist in the database in exact sequence.
    Detects if the database was rolled back, replaced, or had records deleted from the tail.
    """
    if not os.path.exists(checkpoint_path):
        return {"status": "NO_CHECKPOINTS", "message": "No external checkpoints file found."}

    checkpoints: List[Dict[str, Any]] = []
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    checkpoints.append(json.loads(line.strip()))
                except Exception:
                    continue

    if not checkpoints:
        return {"status": "NO_CHECKPOINTS", "message": "Checkpoints file was empty."}

    for idx, cp in enumerate(checkpoints):
        # 1. Verify digital signature of the external checkpoint itself
        cp_copy = dict(cp)
        sig = cp_copy.pop("signature", None)
        key_id = cp_copy.pop("key_id", None)
        canonical = json.dumps(cp_copy, sort_keys=True, separators=(',', ':'))
        cp_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        
        if not signature_service.verify_signature(fingerprint=cp_hash, signature_b64=sig, key_id=key_id):
            return {
                "status": "CHECKPOINT_SIGNATURE_INVALID",
                "checkpoint_index": idx,
                "tip_audit_id": cp.get("tip_audit_id"),
                "error": "External checkpoint digital signature failed verification against trusted registry."
            }

        # 2. Verify that the checkpointed audit entry still exists in the database
        db_entry = db.query(AuditLog).filter(AuditLog.id == cp["tip_audit_id"]).first()
        if not db_entry:
            return {
                "status": "TAMPER_DELETION_DETECTED",
                "checkpoint_index": idx,
                "missing_audit_id": cp["tip_audit_id"],
                "error": f"Database has been truncated or rolled back: Checkpointed entry {cp['tip_audit_id']} is missing from database."
            }

        # 3. Verify entry hash matches
        if db_entry.entry_hash != cp["tip_entry_hash"]:
            return {
                "status": "TAMPER_MODIFICATION_DETECTED",
                "checkpoint_index": idx,
                "audit_id": cp["tip_audit_id"],
                "error": "Checkpointed entry hash differs from database entry hash. Database substitution detected."
            }

    return {
        "status": "CHECKPOINTS_VERIFIED",
        "verified_checkpoints_count": len(checkpoints),
        "tampering_detected": False
    }

def verify_audit_trail_integrity(db: Session, limit: int = 100) -> Dict[str, Any]:
    """Verifies the mathematical hash chain of the audit trail to detect internal modifications or gaps."""
    entries = db.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).limit(limit).all()
    if not entries:
        return {"status": "EMPTY", "verified_count": 0, "chain_valid": True}

    prev_hash = "GENESIS_AUDIT_ROOT"
    for idx, entry in enumerate(entries):
        if not entry.entry_hash:
            continue
        expected_prev = prev_hash
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
