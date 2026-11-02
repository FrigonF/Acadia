"""Comprehensive SQLAlchemy ORM Models for ACADIA."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Institution(Base):
    __tablename__ = "institutions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    aishe_code = Column(String(50), unique=True, nullable=False, index=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, SUSPENDED, PENDING_REVIEW
    approved_programmes = Column(JSON, default=list)  # e.g. ["B.Tech Computer Science", "B.Tech Mechanical"]
    reporting_contact = Column(JSON, default=dict)  # {"email": "...", "phone": "..."}
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    users = relationship("User", back_populates="institution", cascade="all, delete-orphan")
    intakes = relationship("ApprovedIntake", back_populates="institution", cascade="all, delete-orphan")
    upload_batches = relationship("UploadBatch", back_populates="institution", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="institution", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # PLATFORM_ADMIN, AICTE_VERIFIER, INSTITUTION_ADMIN, AUTHORIZED_EXTERNAL_VERIFIER
    institution_id = Column(String(36), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    idp_reference = Column(String(255), nullable=True)  # For Keycloak / external SSO
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    institution = relationship("Institution", back_populates="users")

class ApprovedIntake(Base):
    __tablename__ = "approved_intakes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    institution_id = Column(String(36), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    programme = Column(String(255), nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, index=True)  # e.g. "2025-2026"
    approved_intake = Column(Integer, default=0, nullable=False)
    approved_supernumerary = Column(Integer, default=0)
    nri_seats = Column(Integer, default=0)
    oci_seats = Column(Integer, default=0)
    fn_seats = Column(Integer, default=0)
    other_categories = Column(JSON, default=dict)  # {"EWS": 10, "TFWS": 5}
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    institution = relationship("Institution", back_populates="intakes")
    __table_args__ = (
        UniqueConstraint("institution_id", "programme", "academic_year", name="uq_inst_prog_year"),
    )

class UploadBatch(Base):
    __tablename__ = "upload_batches"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    institution_id = Column(String(36), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    total_records = Column(Integer, default=0)
    valid_records = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    duplicate_records = Column(Integer, default=0)
    status = Column(String(50), default="PROCESSING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    processing_summary = Column(JSON, default=dict)
    uploaded_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    institution = relationship("Institution", back_populates="upload_batches")
    students = relationship("Student", back_populates="batch", cascade="all, delete-orphan")
    validation_issues = relationship("ValidationIssue", back_populates="batch", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    institution_id = Column(String(36), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # APAAR ID handling: Encrypted at rest (AES-256-GCM), masked display & keyed HMAC fingerprint
    apaar_id = Column(Text, nullable=True)                    # Encrypted at rest (AES-256-GCM Base64)
    apaar_masked = Column(String(20), nullable=True)          # Safe display e.g. XXXXXXXX1234
    apaar_fingerprint = Column(String(64), nullable=False, index=True) # Keyed HMAC-SHA256 for duplicate lookup
    
    date_of_birth = Column(String(20), nullable=True)
    gender = Column(String(20), nullable=True)
    programme = Column(String(255), nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, index=True)
    enrollment_year = Column(Integer, nullable=True)
    seat_category = Column(String(50), default="GENERAL")  # GENERAL, SC, ST, OBC, NRI, OCI, FN, EWS, TFWS
    enrollment_number = Column(String(100), nullable=True)
    
    # Status: PENDING_VALIDATION, VALIDATED, FLAGGED, APPROVED, REJECTED
    record_status = Column(String(50), default="PENDING_VALIDATION", index=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_type = Column(String(50), nullable=True)  # WITHIN_INSTITUTION, CROSS_INSTITUTION
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    institution = relationship("Institution", back_populates="students")
    batch = relationship("UploadBatch", back_populates="students")
    validation_issues = relationship("ValidationIssue", back_populates="student", cascade="all, delete-orphan")
    versions = relationship("RecordVersion", back_populates="student", cascade="all, delete-orphan")
    credentials = relationship("VerificationCredential", back_populates="student", cascade="all, delete-orphan")

class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    batch_id = Column(String(36), ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String(50), nullable=False, index=True)
    issue_category = Column(String(50), nullable=False)  # APAAR_FORMAT, MISSING_FIELD, DUPLICATE, INTAKE_LIMIT, CONFLICT
    severity = Column(String(20), nullable=False)        # CRITICAL, WARNING, INFO
    field = Column(String(50), nullable=True)
    source_row = Column(Integer, nullable=True)
    explanation = Column(Text, nullable=False)
    recommended_correction = Column(Text, nullable=True)
    
    # Resolution
    resolution_status = Column(String(50), default="OPEN", index=True)  # OPEN, RESOLVED, WAIVED
    resolved_by = Column(String(36), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    student = relationship("Student", back_populates="validation_issues")
    batch = relationship("UploadBatch", back_populates="validation_issues")

class RecordVersion(Base):
    __tablename__ = "record_versions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    
    canonical_payload = Column(JSON, nullable=False)     # Normalized deterministic JSON
    fingerprint = Column(String(64), nullable=False)     # SHA-256 of canonical_payload
    previous_fingerprint = Column(String(64), nullable=True)
    previous_version_id = Column(String(36), nullable=True)
    
    # Cryptographic Digital Signature
    signature = Column(Text, nullable=False)             # Ed25519 signature of fingerprint
    public_key = Column(Text, nullable=False)            # Public key reference/PEM
    key_id = Column(String(100), nullable=False)
    
    approved_by = Column(String(36), nullable=False)     # User ID
    approval_timestamp = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)

    student = relationship("Student", back_populates="versions")
    __table_args__ = (
        UniqueConstraint("student_id", "version_number", name="uq_student_version"),
        Index("idx_record_fingerprint", "fingerprint"),
    )

class VerificationCredential(Base):
    __tablename__ = "verification_credentials"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    credential_reference = Column(String(64), unique=True, nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    record_version_id = Column(String(36), ForeignKey("record_versions.id", ondelete="CASCADE"), nullable=False)
    
    qr_verification_token = Column(String(128), unique=True, nullable=False, index=True)
    verification_url = Column(String(255), nullable=False)
    
    status = Column(String(20), default="ACTIVE", index=True)  # ACTIVE, REVOKED, EXPIRED
    revocation_reason = Column(Text, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    student = relationship("Student", back_populates="credentials")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_email = Column(String(255), nullable=True)
    actor_role = Column(String(50), nullable=True)
    
    action = Column(String(100), nullable=False, index=True) # e.g. UPLOAD_BATCH, APPROVE_RECORD, SEAL_RECORD, RESOLVE_ISSUE
    target_type = Column(String(50), nullable=False)        # STUDENT, BATCH, INTAKE, CREDENTIAL
    target_id = Column(String(36), nullable=True, index=True)
    
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    event_metadata = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
