"""QR verification credential generation and verification."""
import io
import uuid
import qrcode
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.core.config import settings
from backend.app.services.record_integrity.signer import signature_service
from backend.app.services.record_integrity.canonical import create_canonical_json, verify_record_fingerprint

class QRVerificationService:
    @staticmethod
    def generate_verification_qr_image(verification_url: str) -> bytes:
        """Generates PNG bytes of QR code pointing to secure verification endpoint."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def verify_credential(
        credential,
        record_version,
        student
    ) -> Dict[str, Any]:
        """Comprehensive verification of QR credential, version integrity, and signature."""
        now = datetime.now(timezone.utc)
        
        # 1. Credential status check
        if credential.status == "REVOKED":
            return {
                "verified": False,
                "status": "REVOKED",
                "message": f"This credential was revoked: {credential.revocation_reason or 'No reason provided'}",
                "student_preview": None
            }

        if credential.status == "SUPERSEDED":
            return {
                "verified": False,
                "status": "SUPERSEDED",
                "message": f"This credential has been superseded by an updated record version: {credential.revocation_reason or 'Updated version generated'}",
                "student_preview": None
            }
            
        if credential.expires_at and credential.expires_at < now:
            return {
                "verified": False,
                "status": "EXPIRED",
                "message": "This credential has expired.",
                "student_preview": None
            }
            
        # 2. Check cryptographic signature of the stored fingerprint
        sig_valid = signature_service.verify_signature(
            fingerprint=record_version.fingerprint,
            signature_b64=record_version.signature,
            public_key_pem=record_version.public_key
        )
        if not sig_valid:
            return {
                "verified": False,
                "status": "SIGNATURE_INVALID",
                "message": "Cryptographic digital signature failed verification. Record may be forged.",
                "student_preview": None
            }
            
        # 3. Canonical integrity check against version payload
        canonical_str = create_canonical_json(record_version.canonical_payload)
        fingerprint_match = verify_record_fingerprint(canonical_str, record_version.fingerprint)
        if not fingerprint_match:
            return {
                "verified": False,
                "status": "TAMPERED_VERSION",
                "message": "Record version payload has been modified post-sealing. Tampering detected.",
                "student_preview": None
            }
            
        # 4. Minimal Authorized Public Disclosure (Privacy Preserving)
        payload = record_version.canonical_payload
        student_preview = {
            "student_name": payload.get("name"),
            "apaar_masked": payload.get("apaar_masked"),
            "programme": payload.get("programme"),
            "academic_year": payload.get("academic_year"),
            "institution_name": payload.get("institution_name", "AICTE Approved Institution"),
            "seat_category": payload.get("seat_category"),
            "record_version": record_version.version_number,
            "certified_at": record_version.approval_timestamp.isoformat() if record_version.approval_timestamp else None,
            "key_id": record_version.key_id
        }
        
        return {
            "verified": True,
            "status": "VERIFIED_AUTHENTIC",
            "message": "Student record is authentic, tamper-evident, and cryptographically verified by AICTE/ACADIA authority.",
            "student_preview": student_preview
        }

qr_verification_service = QRVerificationService()
