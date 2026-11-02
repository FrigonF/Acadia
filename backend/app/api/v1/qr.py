"""QR code credential generation, public verification, and revocation."""
import base64
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import Student
from backend.app.models import RecordVersion
from backend.app.models import VerificationCredential
from backend.app.schemas import QRGenerateResponse, QRVerifyResponse
from backend.app.services.qr_verification.qr_service import qr_verification_service
from backend.app.services.reporting.audit_service import log_audit_event

router = APIRouter(prefix="/qr", tags=["QR Verification"])

@router.post("/generate/{record_id}", response_model=QRGenerateResponse)
def generate_qr_credential(
    record_id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == record_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    # Get latest sealed record version
    version = db.query(RecordVersion).filter(
        RecordVersion.student_id == student.id
    ).order_by(RecordVersion.version_number.desc()).first()

    if not version:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate QR credential: Student record has not been sealed with a version and digital signature."
        )

    # Generate unique verification token and secure reference
    token = str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", "")
    cred_ref = f"ACADIA-CERT-{str(uuid.uuid4())[:8].upper()}"
    verification_url = f"{settings.PUBLIC_BASE_URL}/api/v1/qr/verify/{token}"

    credential = VerificationCredential(
        credential_reference=cred_ref,
        student_id=student.id,
        record_version_id=version.id,
        qr_verification_token=token,
        verification_url=verification_url,
        status="ACTIVE"
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    # Generate QR PNG image bytes and base64 encode
    png_bytes = qr_verification_service.generate_verification_qr_image(verification_url)
    b64_qr = base64.b64encode(png_bytes).decode('utf-8')

    log_audit_event(
        db, action="GENERATE_QR_CREDENTIAL", target_type="CREDENTIAL", target_id=credential.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"ref": cred_ref, "token": token}
    )

    return QRGenerateResponse(
        credential_id=credential.id,
        credential_reference=credential.credential_reference,
        qr_verification_token=credential.qr_verification_token,
        verification_url=credential.verification_url,
        qr_code_base64=b64_qr,
        created_at=credential.created_at
    )

@router.get("/verify/{token}", response_model=QRVerifyResponse)
def verify_qr_token(token: str, db: Session = Depends(get_db)):
    """Public verification endpoint accessed by scanning the QR code.
    Discloses minimal authorized information only.
    """
    credential = db.query(VerificationCredential).filter(
        VerificationCredential.qr_verification_token == token
    ).first()

    if not credential:
        return QRVerifyResponse(
            verified=False,
            status="NOT_FOUND",
            message="Verification token is invalid or does not exist."
        )

    version = db.query(RecordVersion).filter(
        RecordVersion.id == credential.record_version_id
    ).first()

    student = db.query(Student).filter(
        Student.id == credential.student_id
    ).first()

    result = qr_verification_service.verify_credential(
        credential=credential,
        record_version=version,
        student=student
    )

    return QRVerifyResponse(
        verified=result["verified"],
        status=result["status"],
        message=result["message"],
        student_preview=result.get("student_preview")
    )

@router.post("/revoke/{credential_id}")
def revoke_credential(
    credential_id: str,
    reason: str = "Administrative revocation",
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    cred = db.query(VerificationCredential).filter(VerificationCredential.id == credential_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    cred.status = "REVOKED"
    cred.revocation_reason = reason
    cred.revoked_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db, action="REVOKE_CREDENTIAL", target_type="CREDENTIAL", target_id=cred.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"status": "REVOKED", "reason": reason}
    )
    return {"message": "Credential revoked successfully", "credential_id": cred.id, "status": "REVOKED"}
