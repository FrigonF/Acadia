"""Audit logger utility for recording immutable state changes."""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models import AuditLog

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
    """Creates a persistent audit log record."""
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
        ip_address=ip_address
    )
    db.add(audit_entry)
    db.commit()
    return audit_entry
