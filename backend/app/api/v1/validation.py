"""Validation and issue resolution management."""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import ValidationIssue, Student, UploadBatch
from backend.app.schemas import ValidationIssueResponse, IssueResolveRequest
from backend.app.services.reporting.audit_service import log_audit_event

router = APIRouter(prefix="/validation", tags=["Validation & Issues"])

@router.get("/issues", response_model=List[ValidationIssueResponse])
def list_validation_issues(
    batch_id: Optional[str] = None,
    student_id: Optional[str] = None,
    resolution_status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    query = db.query(ValidationIssue)
    
    # Institution Admin scope enforcement
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        query = query.join(UploadBatch, ValidationIssue.batch_id == UploadBatch.id).filter(
            UploadBatch.institution_id == current_user.institution_id
        )
    
    if batch_id:
        query = query.filter(ValidationIssue.batch_id == batch_id)
    if student_id:
        query = query.filter(ValidationIssue.student_id == student_id)
    if resolution_status:
        query = query.filter(ValidationIssue.resolution_status == resolution_status)
    if severity:
        query = query.filter(ValidationIssue.severity == severity)
        
    return query.order_by(ValidationIssue.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/issues/{id}", response_model=ValidationIssueResponse)
def get_validation_issue(
    id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    issue = db.query(ValidationIssue).filter(ValidationIssue.id == id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Validation issue not found")
        
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        batch = db.query(UploadBatch).filter(UploadBatch.id == issue.batch_id).first()
        if not batch or batch.institution_id != current_user.institution_id:
            raise HTTPException(status_code=403, detail="Access denied to other institution's validation issues.")
            
    return issue

@router.patch("/issues/{id}/resolve", response_model=ValidationIssueResponse)
def resolve_validation_issue(
    id: str,
    payload: IssueResolveRequest,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    issue = db.query(ValidationIssue).filter(ValidationIssue.id == id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        batch = db.query(UploadBatch).filter(UploadBatch.id == issue.batch_id).first()
        if not batch or batch.institution_id != current_user.institution_id:
            raise HTTPException(status_code=403, detail="Cannot resolve validation issues belonging to another institution.")

    issue.resolution_status = payload.action.upper()
    issue.resolution_notes = payload.resolution_notes
    issue.resolved_by = current_user.id
    issue.resolved_at = datetime.now(timezone.utc)

    # Check if student has remaining open critical issues
    if issue.student_id:
        remaining_critical = db.query(ValidationIssue).filter(
            ValidationIssue.student_id == issue.student_id,
            ValidationIssue.id != issue.id,
            ValidationIssue.resolution_status == "OPEN",
            ValidationIssue.severity == "CRITICAL"
        ).count()
        
        if remaining_critical == 0:
            student = db.query(Student).filter(Student.id == issue.student_id).first()
            if student and student.record_status == "FLAGGED":
                student.record_status = "VALIDATED"

    db.commit()
    db.refresh(issue)

    log_audit_event(
        db, action="RESOLVE_VALIDATION_ISSUE", target_type="ISSUE", target_id=issue.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"status": issue.resolution_status, "action": payload.action}
    )

    return issue
