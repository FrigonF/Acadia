"""Student record listing, inspection, creation, update, and lifecycle management."""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.core.security import compute_hmac_fingerprint, mask_apaar_id, encrypt_identifier
from backend.app.models import Student, Institution, RecordVersion, VerificationCredential, ValidationIssue, UploadBatch
from backend.app.schemas import StudentResponse, StudentCreate, StudentUpdate, StudentDeactivateRequest
from backend.app.services.reporting.audit_service import log_audit_event
from backend.app.services.record_integrity.canonical import create_canonical_json, compute_record_fingerprint
from backend.app.services.record_integrity.signer import signature_service
from backend.app.services.validation.validator import validation_engine
from backend.app.services.duplicate_detection.detector import duplicate_engine
from backend.app.services.intake_monitoring.intake_service import intake_engine

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
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
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
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
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

    inst = db.query(Institution).filter(Institution.id == payload.institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Institution '{payload.institution_id}' not found.")

    apaar = payload.apaar_id.strip()

    # 1. Run deterministic Validation Engine
    raw_dict = {
        "source_row": 1,
        "apaar_id": apaar,
        "name": payload.name.strip(),
        "programme": payload.programme.strip(),
        "academic_year": payload.academic_year.strip(),
        "seat_category": (payload.seat_category or "GENERAL").strip().upper(),
    }
    validation_issues = validation_engine.validate_record(raw_dict, inst)
    has_critical = any(issue.severity == "CRITICAL" for issue in validation_issues)

    # 2. Run Duplicate Detection Engine (HMAC fingerprint)
    fingerprint = compute_hmac_fingerprint(apaar)
    existing_dups = db.query(Student).filter(
        Student.apaar_fingerprint == fingerprint,
        Student.record_status != "DEACTIVATED"
    ).all()
    is_dup = len(existing_dups) > 0
    dup_type = None
    if is_dup:
        has_critical = True
        is_same_inst = any(s.institution_id == inst.id for s in existing_dups)
        dup_type = "WITHIN_INSTITUTION" if is_same_inst else "CROSS_INSTITUTION"

    # 3. Check Approved Intake Capacity
    intake_rep = intake_engine.verify_intake_for_programme(
        db, institution_id=inst.id, programme=payload.programme.strip(), academic_year=payload.academic_year.strip()
    )
    has_intake_violation = len(intake_rep.get("alerts", [])) > 0

    # Determine status
    if has_critical or is_dup or has_intake_violation or validation_issues:
        status_str = "FLAGGED"
    else:
        status_str = "PENDING_VALIDATION"

    masked = mask_apaar_id(apaar)
    encrypted_apaar = encrypt_identifier(apaar)

    # Ensure a default manual upload batch exists for manual intake tracking
    manual_batch = db.query(UploadBatch).filter(
        UploadBatch.institution_id == inst.id,
        UploadBatch.original_filename == "manual_intake_registry"
    ).first()
    if not manual_batch:
        manual_batch = UploadBatch(
            institution_id=inst.id,
            original_filename="manual_intake_registry",
            total_records=0,
            status="COMPLETED",
            uploaded_by=current_user.id
        )
        db.add(manual_batch)
        db.flush()

    student = Student(
        batch_id=manual_batch.id,
        institution_id=payload.institution_id,
        name=payload.name.strip(),
        apaar_id=encrypted_apaar,
        apaar_masked=masked,
        apaar_fingerprint=fingerprint,
        programme=payload.programme.strip(),
        academic_year=payload.academic_year.strip(),
        seat_category=(payload.seat_category or "GENERAL").strip().upper(),
        enrollment_number=payload.enrollment_number.strip() if payload.enrollment_number else None,
        enrollment_year=payload.enrollment_year,
        record_status=status_str,
        is_duplicate=is_dup,
        duplicate_type=dup_type
    )
    db.add(student)
    db.flush()

    # Record validation issues in database
    for issue in validation_issues:
        db.add(ValidationIssue(
            student_id=student.id,
            batch_id=manual_batch.id,
            rule_id=issue.rule_id,
            issue_category=issue.category,
            severity=issue.severity,
            field=issue.field,
            source_row=1,
            explanation=issue.explanation,
            recommended_correction=issue.recommended_correction
        ))

    if is_dup:
        db.add(ValidationIssue(
            student_id=student.id,
            batch_id=manual_batch.id,
            rule_id="RULE_DUPLICATE_APAAR",
            issue_category="DUPLICATE",
            severity="CRITICAL",
            field="apaar_id",
            source_row=1,
            explanation=f"Duplicate enrollment detected ({dup_type}). APAAR fingerprint matches existing record.",
            recommended_correction="Resolve duplicate enrollment with the reporting institution before approval."
        ))

    if has_intake_violation:
        for alert in intake_rep.get("alerts", []):
            db.add(ValidationIssue(
                student_id=student.id,
                batch_id=manual_batch.id,
                rule_id="RULE_INTAKE_CAPACITY",
                issue_category="INTAKE_LIMIT",
                severity=alert.get("severity", "CRITICAL"),
                field="seat_category",
                source_row=1,
                explanation=alert.get("explanation", "Programme intake capacity exceeded."),
                recommended_correction="Adjust institutional intake or transfer student to approved quota."
            ))

    db.commit()
    db.refresh(student)

    # Privacy: raw APAAR never included in audit payloads
    log_audit_event(
        db, action="CREATE_STUDENT", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"name": student.name, "apaar_masked": student.apaar_masked, "programme": student.programme, "status": student.record_status}
    )
    return student

@router.patch("/{id}", response_model=StudentResponse)
def update_student(
    id: str,
    payload: StudentUpdate,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
        raise HTTPException(status_code=403, detail="Cannot edit records of another institution.")

    # Record previous state (clean, masked)
    previous_state = {
        "name": student.name,
        "apaar_masked": student.apaar_masked,
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

    if payload.apaar_id is not None and payload.apaar_id.strip() != "":
        new_apaar = payload.apaar_id.strip()
        if not new_apaar.isdigit() or len(new_apaar) != 12:
            raise HTTPException(status_code=400, detail="Updated APAAR ID must be exactly 12 numeric digits.")
        changed_fields["apaar_id"] = {"old": student.apaar_masked, "new": mask_apaar_id(new_apaar)}
        student.apaar_id = encrypt_identifier(new_apaar)
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

    # Re-validate updated record
    inst = db.query(Institution).filter(Institution.id == student.institution_id).first()
    check_dict = {
        "source_row": 1,
        "apaar_id": payload.apaar_id.strip() if (payload.apaar_id and payload.apaar_id.strip()) else "000000000000",
        "name": student.name,
        "programme": student.programme,
        "academic_year": student.academic_year,
        "seat_category": student.seat_category
    }
    validation_issues = validation_engine.validate_record(check_dict, inst)
    has_critical = any(issue.severity == "CRITICAL" for issue in validation_issues)

    # Invalidate / supersede old active credentials immediately upon modification
    existing_creds = db.query(VerificationCredential).filter(
        VerificationCredential.student_id == student.id,
        VerificationCredential.status == "ACTIVE"
    ).all()
    for cred in existing_creds:
        cred.status = "SUPERSEDED"
        cred.revocation_reason = f"Superseded by update: {payload.reason}"
        cred.revoked_at = datetime.now(timezone.utc)

    # Separation of duties:
    # If the modifier is an authorized central verifier / platform admin, they may directly approve and seal.
    # If modified by Institution Admin, the record transitions to PENDING_VALIDATION or FLAGGED and requires independent verification.
    is_verifier = current_user.role in (UserRole.PLATFORM_ADMIN.value, UserRole.AICTE_VERIFIER.value)
    
    if is_verifier and not has_critical:
        student.record_status = "APPROVED"
        latest_version = db.query(RecordVersion).filter(
            RecordVersion.student_id == student.id
        ).order_by(RecordVersion.version_number.desc()).first()
        next_version_num = (latest_version.version_number + 1) if latest_version else 1
        prev_fingerprint = latest_version.fingerprint if latest_version else None

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
    else:
        # Proposed correction by Institution Admin requires independent verification
        student.record_status = "FLAGGED" if has_critical else "PENDING_VALIDATION"

    db.commit()
    db.refresh(student)

    # Record Audit Log (Notice: raw APAAR is never logged)
    log_audit_event(
        db, action="UPDATE_STUDENT_RECORD", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        previous_state=previous_state,
        new_state={"status": student.record_status, "changed_fields": changed_fields},
        metadata={"reason": payload.reason, "requires_verifier_approval": not is_verifier}
    )

    return student

@router.post("/{id}/deactivate", response_model=StudentResponse)
def deactivate_student(
    id: str,
    payload: StudentDeactivateRequest,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != student.institution_id:
        raise HTTPException(status_code=403, detail="Cannot deactivate students of another institution.")

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
