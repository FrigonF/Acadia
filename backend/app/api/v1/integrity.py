"""Record sealing, canonical SHA-256 fingerprinting, Ed25519 signatures, and tamper verification."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import Student
from backend.app.models import Institution
from backend.app.models import RecordVersion
from backend.app.schemas import SealRecordResponse, VerifyIntegrityResponse
from backend.app.services.record_integrity.canonical import (
    create_canonical_json, compute_record_fingerprint, verify_record_fingerprint
)
from backend.app.services.record_integrity.signer import signature_service
from backend.app.services.reporting.audit_service import log_audit_event

router = APIRouter(prefix="/integrity", tags=["Record Integrity & Cryptographic Sealing"])

@router.post("/{record_id}/seal", response_model=SealRecordResponse)
def seal_record(
    record_id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == record_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    inst = db.query(Institution).filter(Institution.id == student.institution_id).first()

    # Determine latest version number
    latest_version = db.query(RecordVersion).filter(
        RecordVersion.student_id == student.id
    ).order_by(RecordVersion.version_number.desc()).first()

    next_version_num = 1 if not latest_version else latest_version.version_number + 1
    prev_fingerprint = latest_version.fingerprint if latest_version else None
    prev_version_id = latest_version.id if latest_version else None

    # Construct canonical payload
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
        "previous_fingerprint": prev_fingerprint or "ROOT_GENESIS"
    }

    # 1. Deterministic canonical JSON
    canonical_str = create_canonical_json(canonical_payload)
    # 2. SHA-256 fingerprint
    fingerprint = compute_record_fingerprint(canonical_str)
    # 3. Ed25519 digital signature of the fingerprint
    signature = signature_service.sign_fingerprint(fingerprint)
    pub_key_pem = signature_service.get_public_key_pem()

    # 4. Save Version Record
    version_obj = RecordVersion(
        student_id=student.id,
        version_number=next_version_num,
        canonical_payload=canonical_payload,
        fingerprint=fingerprint,
        previous_fingerprint=prev_fingerprint,
        previous_version_id=prev_version_id,
        signature=signature,
        public_key=pub_key_pem,
        key_id=signature_service.key_id,
        approved_by=current_user.id
    )
    db.add(version_obj)

    student.record_status = "APPROVED"
    db.commit()
    db.refresh(version_obj)

    log_audit_event(
        db, action="SEAL_RECORD_VERSION", target_type="STUDENT", target_id=student.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"version": next_version_num, "fingerprint": fingerprint, "key_id": signature_service.key_id}
    )

    return SealRecordResponse(
        record_id=student.id,
        version_number=version_obj.version_number,
        fingerprint=version_obj.fingerprint,
        previous_fingerprint=version_obj.previous_fingerprint,
        signature=version_obj.signature,
        key_id=version_obj.key_id,
        approved_by=version_obj.approved_by,
        approval_timestamp=version_obj.approval_timestamp
    )

@router.get("/{record_id}")
def get_record_versions(
    record_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == record_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")
        
    versions = db.query(RecordVersion).filter(
        RecordVersion.student_id == record_id
    ).order_by(RecordVersion.version_number.desc()).all()

    return {
        "student_id": student.id,
        "name": student.name,
        "record_status": student.record_status,
        "versions": [
            {
                "version_id": v.id,
                "version_number": v.version_number,
                "fingerprint": v.fingerprint,
                "previous_fingerprint": v.previous_fingerprint,
                "key_id": v.key_id,
                "approved_by": v.approved_by,
                "approval_timestamp": v.approval_timestamp.isoformat()
            } for v in versions
        ]
    }

@router.post("/{record_id}/verify", response_model=VerifyIntegrityResponse)
def verify_record_integrity(
    record_id: str,
    version_number: int = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(RecordVersion).filter(RecordVersion.student_id == record_id)
    if version_number:
        query = query.filter(RecordVersion.version_number == version_number)
    else:
        query = query.order_by(RecordVersion.version_number.desc())
        
    version = query.first()
    if not version:
        raise HTTPException(status_code=404, detail="No approved sealed version found for this record.")

    # 1. Verify SHA-256 fingerprint against canonical payload
    canonical_str = create_canonical_json(version.canonical_payload)
    fingerprint_valid = verify_record_fingerprint(canonical_str, version.fingerprint)

    # 2. Verify Ed25519 digital signature
    signature_valid = signature_service.verify_signature(
        fingerprint=version.fingerprint,
        signature_b64=version.signature,
        public_key_pem=version.public_key
    )

    is_completely_valid = fingerprint_valid and signature_valid
    status_str = "INTEGRITY_VERIFIED" if is_completely_valid else "TAMPERING_DETECTED"
    msg = "Record canonical hash and digital signature match perfectly." if is_completely_valid else "Cryptographic hash mismatch or signature verification failure."

    return VerifyIntegrityResponse(
        record_id=record_id,
        version_number=version.version_number,
        is_valid=is_completely_valid,
        signature_valid=signature_valid,
        status=status_str,
        message=msg,
        verified_at=datetime.now(timezone.utc)
    )
