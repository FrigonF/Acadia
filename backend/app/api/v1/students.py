"""Student record listing, inspection, creation, update, and lifecycle management."""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.core.security import compute_hmac_fingerprint, mask_apaar_id
from backend.app.models import Student, Institution, RecordVersion, VerificationCredential
from backend.app.schemas import StudentResponse, StudentCreate, StudentUpdate, StudentDeactivateRequest
from backend.app.services.reporting.audit_service import log_audit_event
from backend.app.services.record_integrity.canonical import create_canonical_json, compute_record_fingerprint
from backend.app.services.record_integrity.signer import signature_service

router = APIRouter(prefix="/students", tags=["Students"])

@router.get("", response_model=List[StudentResponse])
def list_students(
    skip: int = 0,
    limit: int = 100,
    institution_id: Optional[str] = None,
    record_status: Optional[str] = None,
    programme: Optional[str] = None,
    academic_year: Optional[str] = None,
    include_inactive: bool = False,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Student)
    
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        query = query.filter(Student.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(Student.institution_id == institution_id)
        
    if not include_inactive:
        query = query.filter(Student.record_status != "DEACTIVATED")
        
    if record_status:
        query = query.filter(Student.record_status == record_status)
    if programme:
        query = query.filter(Student.programme == programme)
    if academic_year:
        query = query.filter(Student.academic_year == academic_year)
        
    return query.order_by(Student.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{id}", response_model=StudentResponse)
def get_student(
    id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")
        
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
        raise HTTPException(status_code=403, detail="Access denied to other institution's student records.")
        
    return student

@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != payload.institution_id:
        raise HTTPException(status_code=403, detail="Cannot create record for another institution.")

    # Format validation
    apaar = payload.apaar_id.strip()
    if not apaar.isdigit() or len(apaar) != 12:
        raise HTTPException(status_code=400, detail="APAAR ID must be exactly 12 numeric digits.")

    masked = mask_apaar_id(apaar)
    fingerprint = compute_hmac_fingerprint(apaar)

    student = Student(
        institution_id=payload.institution_id,
        name=payload.name.strip(),
        apaar_id=apaar,
        apaar_masked=masked,
        apaar_fingerprint=fingerprint,
        programme=payload.programme.strip(),
        academic_year=payload.academic_year.strip(),
        seat_category=(payload.seat_category or "GENERAL").strip().upper(),
        enrollment_number=payload.enrollment_number.strip() if payload.enrollment_number else None,
        enrollment_year=payload.enrollment_year,
        record_status="VALIDATED"
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    log_audit_event(
        db, action="CREATE_STUDENT", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"name": student.name, "apaar_masked": student.apaar_masked, "programme": student.programme}
    )
    return student

@router.patch("/{id}", response_model=StudentResponse)
def update_student(
    id: str,
    payload: StudentUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
        raise HTTPException(status_code=403, detail="Cannot edit records of another institution.")

    if current_user.role == UserRole.AUTHORIZED_EXTERNAL_VERIFIER.value:
        raise HTTPException(status_code=403, detail="External verifiers have read-only access.")

    # Record previous state
    previous_state = {
        "name": student.name,
        "apaar_id": student.apaar_id,
        "programme": student.programme,
        "academic_year": student.academic_year,
        "seat_category": student.seat_category,
        "enrollment_number": student.enrollment_number,
        "record_status": student.record_status,
    }

    changed_fields = {}
    if payload.name is not None and payload.name.strip() != student.name:
        changed_fields["name"] = {"old": student.name, "new": payload.name.strip()}
        student.name = payload.name.strip()

    if payload.apaar_id is not None and payload.apaar_id.strip() != student.apaar_id:
        new_apaar = payload.apaar_id.strip()
        if not new_apaar.isdigit() or len(new_apaar) != 12:
            raise HTTPException(status_code=400, detail="Updated APAAR ID must be exactly 12 numeric digits.")
        changed_fields["apaar_id"] = {"old": student.apaar_masked, "new": mask_apaar_id(new_apaar)}
        student.apaar_id = new_apaar
        student.apaar_masked = mask_apaar_id(new_apaar)
        student.apaar_fingerprint = compute_hmac_fingerprint(new_apaar)

    if payload.programme is not None and payload.programme.strip() != student.programme:
        changed_fields["programme"] = {"old": student.programme, "new": payload.programme.strip()}
        student.programme = payload.programme.strip()

    if payload.academic_year is not None and payload.academic_year.strip() != student.academic_year:
        changed_fields["academic_year"] = {"old": student.academic_year, "new": payload.academic_year.strip()}
        student.academic_year = payload.academic_year.strip()

    if payload.seat_category is not None and payload.seat_category.strip().upper() != student.seat_category:
        changed_fields["seat_category"] = {"old": student.seat_category, "new": payload.seat_category.strip().upper()}
        student.seat_category = payload.seat_category.strip().upper()

    if payload.enrollment_number is not None and payload.enrollment_number.strip() != student.enrollment_number:
        changed_fields["enrollment_number"] = {"old": student.enrollment_number, "new": payload.enrollment_number.strip()}
        student.enrollment_number = payload.enrollment_number.strip()

    if not changed_fields:
        return student

    # If student had an existing sealed version, create a new pending version
    inst = db.query(Institution).filter(Institution.id == student.institution_id).first()
    latest_version = db.query(RecordVersion).filter(
        RecordVersion.student_id == student.id
    ).order_by(RecordVersion.version_number.desc()).first()

    next_version_num = (latest_version.version_number + 1) if latest_version else 1
    prev_fingerprint = latest_version.fingerprint if latest_version else None

    # Construct canonical representation of new version
    canonical_payload = {
        "student_id": student.id,
        "name": student.name,
        "apaar_masked": student.apaar_masked,
        "apaar_fingerprint": student.apaar_fingerprint,
        "institution_id": student.institution_id,
        "institution_name": inst.name if inst else "Unknown",
        "programme": student.programme,
        "academic_year": student.academic_year,
        "seat_category": student.seat_category,
        "enrollment_number": student.enrollment_number or "",
        "version_number": next_version_num,
        "previous_fingerprint": prev_fingerprint or "ROOT_GENESIS",
        "update_reason": payload.reason
    }

    canonical_str = create_canonical_json(canonical_payload)
    new_fingerprint = compute_record_fingerprint(canonical_str)
    new_signature = signature_service.sign_fingerprint(new_fingerprint)
    pub_key_pem = signature_service.get_public_key_pem()

    # Create new record version
    version_obj = RecordVersion(
        student_id=student.id,
        version_number=next_version_num,
        canonical_payload=canonical_payload,
        fingerprint=new_fingerprint,
        previous_fingerprint=prev_fingerprint,
        previous_version_id=latest_version.id if latest_version else None,
        signature=new_signature,
        public_key=pub_key_pem,
        key_id=signature_service.key_id,
        approved_by=current_user.id
    )
    db.add(version_obj)

    # Invalidate / revoke old credentials if sealed
    existing_creds = db.query(VerificationCredential).filter(
        VerificationCredential.student_id == student.id,
        VerificationCredential.status == "ACTIVE"
    ).all()
    for cred in existing_creds:
        cred.status = "SUPERSEDED"
        cred.revocation_reason = f"Superseded by version {next_version_num}: {payload.reason}"
        cred.revoked_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(student)

    # Record Audit Log
    log_audit_event(
        db, action="UPDATE_STUDENT_RECORD", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        previous_state=previous_state,
        new_state={"version": next_version_num, "fingerprint": new_fingerprint, "changed_fields": changed_fields},
        metadata={"reason": payload.reason}
    )

    return student

@router.post("/{id}/deactivate", response_model=StudentResponse)
def deactivate_student(
    id: str,
    payload: StudentDeactivateRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
        raise HTTPException(status_code=403, detail="Cannot deactivate students of another institution.")

    if current_user.role == UserRole.AUTHORIZED_EXTERNAL_VERIFIER.value:
        raise HTTPException(status_code=403, detail="External verifiers cannot deactivate records.")

    prev_status = student.record_status
    student.record_status = "DEACTIVATED"

    # Revoke any active credentials
    active_creds = db.query(VerificationCredential).filter(
        VerificationCredential.student_id == student.id,
        VerificationCredential.status == "ACTIVE"
    ).all()
    for cred in active_creds:
        cred.status = "REVOKED"
        cred.revocation_reason = f"Student deactivated: {payload.reason}"
        cred.revoked_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(student)

    log_audit_event(
        db, action="DEACTIVATE_STUDENT", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        previous_state={"status": prev_status},
        new_state={"status": "DEACTIVATED"},
        metadata={"reason": payload.reason}
    )

    return student

@router.post("/{id}/reactivate", response_model=StudentResponse)
def reactivate_student(
    id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    student.record_status = "VALIDATED"
    db.commit()
    db.refresh(student)

    log_audit_event(
        db, action="REACTIVATE_STUDENT", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"status": "VALIDATED"}
    )
    return student
