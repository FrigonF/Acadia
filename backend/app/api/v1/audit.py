"""Audit log querying endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import AuditLog, Student
from backend.app.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if target_id:
        query = query.filter(AuditLog.target_id == target_id)
        
    return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

@router.get("/verify-chain/integrity")
def verify_audit_chain(
    limit: int = 100,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    """Cryptographically verifies the SHA-256 hash chain of the audit trail to detect internal tampering."""
    from backend.app.services.reporting.audit_service import verify_audit_trail_integrity
    return verify_audit_trail_integrity(db, limit=limit)

@router.post("/checkpoints/create")
def create_checkpoint(
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    """Creates a cryptographically signed external checkpoint of the audit log tip."""
    from backend.app.services.reporting.audit_service import create_external_audit_checkpoint
    return create_external_audit_checkpoint(db)

@router.get("/checkpoints/verify")
def verify_checkpoints(
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    """Verifies all external checkpoints against the active database to detect deletions, truncation or snapshot replacement."""
    from backend.app.services.reporting.audit_service import verify_audit_against_checkpoints
    return verify_audit_against_checkpoints(db)

@router.get("/{record_id}", response_model=List[AuditLogResponse])
def get_record_audit_history(
    record_id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    # If target is a Student record, check institutional authorization
    student = db.query(Student).filter(Student.id == record_id).first()
    if student:
        if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
            raise HTTPException(status_code=403, detail="Access denied to other institution's audit records.")
    elif current_user.role == UserRole.INSTITUTION_ADMIN.value:
        # If record is not a student belonging to user's institution, deny access
        raise HTTPException(status_code=404, detail="Record not found or access denied.")

    return db.query(AuditLog).filter(
        AuditLog.target_id == record_id
    ).order_by(AuditLog.timestamp.desc()).all()
