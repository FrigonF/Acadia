"""Pydantic V2 Schemas for ACADIA API."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    institution_id: Optional[str] = None
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    institution_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

# --- Institution Schemas ---
class InstitutionBase(BaseModel):
    name: str
    aishe_code: str
    state: Optional[str] = None
    district: Optional[str] = None
    approved_programmes: List[str] = []
    reporting_contact: Dict[str, Any] = {}

class InstitutionCreate(InstitutionBase):
    pass

class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    approved_programmes: Optional[List[str]] = None
    reporting_contact: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

class InstitutionResponse(InstitutionBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# --- Approved Intake Schemas ---
class IntakeCreate(BaseModel):
    institution_id: str
    programme: str
    academic_year: str
    approved_intake: int
    approved_supernumerary: int = 0
    nri_seats: int = 0
    oci_seats: int = 0
    fn_seats: int = 0
    other_categories: Dict[str, int] = {}

class IntakeResponse(IntakeCreate):
    id: str
    created_at: datetime
    
    model_config = {"from_attributes": True}

# --- Student Schemas ---
class StudentCreate(BaseModel):
    institution_id: str
    name: str
    apaar_id: str
    programme: str
    academic_year: str
    seat_category: Optional[str] = "GENERAL"
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    enrollment_number: Optional[str] = None
    enrollment_year: Optional[int] = None

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    apaar_id: Optional[str] = None
    programme: Optional[str] = None
    academic_year: Optional[str] = None
    seat_category: Optional[str] = None
    enrollment_number: Optional[str] = None
    reason: str = Field(..., description="Mandatory reason for updating student record")

class StudentDeactivateRequest(BaseModel):
    reason: str = Field(..., description="Mandatory audit reason for deactivating student record")

class StudentResponse(BaseModel):
    id: str
    institution_id: str
    name: str
    # Raw apaar_id omitted to prevent PII exposure across standard responses
    apaar_masked: Optional[str] = None
    programme: str
    academic_year: str
    seat_category: Optional[str] = "GENERAL"
    enrollment_number: Optional[str] = None
    record_status: str
    is_duplicate: bool
    duplicate_type: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}

# --- Batch Upload Schemas ---
class BatchUploadResponse(BaseModel):
    batch_id: str
    institution_id: str
    original_filename: str
    total_records: int
    valid_records: int
    invalid_records: int
    duplicate_records: int
    status: str
    created_at: datetime
    processing_summary: Dict[str, Any]

# --- Validation Issue Schemas ---
class ValidationIssueResponse(BaseModel):
    id: str
    student_id: Optional[str] = None
    batch_id: str
    rule_id: str
    issue_category: str
    severity: str
    field: Optional[str] = None
    source_row: Optional[int] = None
    explanation: str
    recommended_correction: Optional[str] = None
    resolution_status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}

class IssueResolveRequest(BaseModel):
    resolution_notes: str
    action: str = Field(default="RESOLVED") # RESOLVED or WAIVED

# --- Record Integrity & Sealing Schemas ---
class SealRecordResponse(BaseModel):
    record_id: str
    version_number: int
    fingerprint: str
    previous_fingerprint: Optional[str] = None
    signature: str
    key_id: str
    approved_by: str
    approval_timestamp: datetime

class VerifyIntegrityResponse(BaseModel):
    record_id: str
    version_number: int
    is_valid: bool
    signature_valid: bool
    status: str
    message: str
    verified_at: datetime

# --- QR Credential Schemas ---
class QRGenerateResponse(BaseModel):
    credential_id: str
    credential_reference: str
    qr_verification_token: str
    verification_url: str
    qr_code_base64: str
    created_at: datetime

class QRVerifyResponse(BaseModel):
    verified: bool
    status: str
    message: str
    student_preview: Optional[Dict[str, Any]] = None

# --- Audit Log Schema ---
class AuditLogResponse(BaseModel):
    id: str
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[str] = None
    event_metadata: Dict[str, Any]
    timestamp: datetime
    
    model_config = {"from_attributes": True}

# --- Dashboard Overview Schema ---
class DashboardOverviewResponse(BaseModel):
    total_institutions: int
    total_students: int
    validated_records: int
    invalid_records: int
    duplicate_records: int
    pending_verification: int
    intake_violations: int
    approved_records: int
    recent_uploads: List[Dict[str, Any]]
    recent_activities: List[Dict[str, Any]]
    category_distribution: Dict[str, int]
