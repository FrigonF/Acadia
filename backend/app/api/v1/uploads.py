"""File upload, parsing, ingestion and batch management."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.core.security import compute_hmac_fingerprint, mask_apaar_id
from backend.app.models import Institution
from backend.app.models import UploadBatch
from backend.app.models import Student
from backend.app.models import ValidationIssue
from backend.app.schemas import BatchUploadResponse
from backend.app.services.ingestion.parser import ingestion_engine
from backend.app.services.validation.validator import validation_engine
from backend.app.services.duplicate_detection.detector import duplicate_engine
from backend.app.services.reporting.audit_service import log_audit_event

router = APIRouter(prefix="/uploads", tags=["Uploads & Ingestion"])

@router.post("", response_model=BatchUploadResponse)
async def upload_student_batch(
    file: UploadFile = File(...),
    institution_id: Optional[str] = Form(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Determine target institution
    target_inst_id = institution_id
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        target_inst_id = current_user.institution_id
        
    if not target_inst_id:
        raise HTTPException(status_code=400, detail="Target institution_id must be specified.")

    inst = db.query(Institution).filter(Institution.id == target_inst_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Institution '{target_inst_id}' not found.")

    file_bytes = await file.read()
    records, parse_errors = ingestion_engine.parse_file(file_bytes, file.filename)
    
    if parse_errors:
        raise HTTPException(status_code=400, detail={"errors": parse_errors})

    # Create UploadBatch record
    batch = UploadBatch(
        institution_id=inst.id,
        original_filename=file.filename,
        total_records=len(records),
        status="PROCESSING",
        uploaded_by=current_user.id
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # 1. In-batch duplicate detection
    in_batch_dups = duplicate_engine.detect_in_batch_duplicates(records)

    valid_count = 0
    invalid_count = 0
    duplicate_count = 0

    student_objects = []
    issues_to_create = []

    for r in records:
        source_row = r.get("source_row")
        apaar = r.get("apaar_id", "").strip()
        name = r.get("name", "").strip()
        programme = r.get("programme", "").strip()
        academic_year = r.get("academic_year", "").strip()
        seat_category = (r.get("seat_category") or "GENERAL").strip().upper()
        
        # Rule validation
        validation_results = validation_engine.validate_record(r, inst)
        has_critical = any(res.severity == "CRITICAL" for res in validation_results)

        # Duplicate checking
        is_dup = False
        dup_type = None
        
        if apaar and apaar in in_batch_dups:
            is_dup = True
            dup_type = "WITHIN_INSTITUTION"
            validation_results.append(type('Obj', (), {
                'rule_id': "RULE_DUPLICATE_IN_BATCH",
                'passed': False,
                'severity': "CRITICAL",
                'category': "DUPLICATE",
                'field': "apaar_id",
                'source_row': source_row,
                'explanation': f"Duplicate APAAR ID within this upload batch (Rows: {in_batch_dups[apaar]}).",
                'recommended_correction': "Resolve duplicate student entry in the batch source."
            })())
        elif apaar:
            # Check existing records in database
            cross_dups = duplicate_engine.check_cross_institution_duplicates(
                db, apaar_id=apaar, current_institution_id=inst.id
            )
            if cross_dups:
                is_dup = True
                dup_type = cross_dups[0]["duplicate_type"]
                other_inst = cross_dups[0]["institution_name"]
                validation_results.append(type('Obj', (), {
                    'rule_id': "RULE_DUPLICATE_IDENTIFIER",
                    'passed': False,
                    'severity': "CRITICAL",
                    'category': "DUPLICATE",
                    'field': "apaar_id",
                    'source_row': source_row,
                    'explanation': f"APAAR ID already registered ({dup_type} at '{other_inst}').",
                    'recommended_correction': "Coordinate with institutional authority for dual enrollment verification."
                })())

        if is_dup:
            duplicate_count += 1
            has_critical = True

        status_str = "FLAGGED" if validation_results else "VALIDATED"
        if has_critical:
            invalid_count += 1
        else:
            valid_count += 1

        fingerprint = compute_hmac_fingerprint(apaar) if apaar else "UNASSIGNED"
        masked = mask_apaar_id(apaar)

        student = Student(
            batch_id=batch.id,
            institution_id=inst.id,
            name=name,
            apaar_id=apaar,
            apaar_masked=masked,
            apaar_fingerprint=fingerprint,
            programme=programme,
            academic_year=academic_year,
            seat_category=seat_category,
            record_status=status_str,
            is_duplicate=is_dup,
            duplicate_type=dup_type
        )
        db.add(student)
        db.flush() # Flush to get student.id

        for issue in validation_results:
            issues_to_create.append(ValidationIssue(
                student_id=student.id,
                batch_id=batch.id,
                rule_id=issue.rule_id,
                issue_category=issue.category,
                severity=issue.severity,
                field=issue.field,
                source_row=issue.source_row,
                explanation=issue.explanation,
                recommended_correction=issue.recommended_correction
            ))

    if issues_to_create:
        db.add_all(issues_to_create)

    batch.valid_records = valid_count
    batch.invalid_records = invalid_count
    batch.duplicate_records = duplicate_count
    batch.status = "COMPLETED"
    batch.processing_summary = {
        "processed_rows": len(records),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "issues_flagged": len(issues_to_create)
    }

    db.commit()
    db.refresh(batch)

    log_audit_event(
        db, action="UPLOAD_BATCH", target_type="BATCH", target_id=batch.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state=batch.processing_summary
    )

    return BatchUploadResponse(
        batch_id=batch.id,
        institution_id=batch.institution_id,
        original_filename=batch.original_filename,
        total_records=batch.total_records,
        valid_records=batch.valid_records,
        invalid_records=batch.invalid_records,
        duplicate_records=batch.duplicate_records,
        status=batch.status,
        created_at=batch.created_at,
        processing_summary=batch.processing_summary
    )

@router.get("", response_model=List[BatchUploadResponse])
def list_batches(
    skip: int = 0,
    limit: int = 50,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(UploadBatch)
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        query = query.filter(UploadBatch.institution_id == current_user.institution_id)
        
    batches = query.order_by(UploadBatch.created_at.desc()).offset(skip).limit(limit).all()
    return [
        BatchUploadResponse(
            batch_id=b.id,
            institution_id=b.institution_id,
            original_filename=b.original_filename,
            total_records=b.total_records,
            valid_records=b.valid_records,
            invalid_records=b.invalid_records,
            duplicate_records=b.duplicate_records,
            status=b.status,
            created_at=b.created_at,
            processing_summary=b.processing_summary or {}
        ) for b in batches
    ]

@router.get("/{batch_id}/report")
def get_batch_report(
    batch_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != batch.institution_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    issues = db.query(ValidationIssue).filter(ValidationIssue.batch_id == batch_id).all()
    
    return {
        "batch_id": batch.id,
        "filename": batch.original_filename,
        "total_records": batch.total_records,
        "valid_records": batch.valid_records,
        "invalid_records": batch.invalid_records,
        "duplicate_records": batch.duplicate_records,
        "issues_summary": [
            {
                "issue_id": issue.id,
                "student_id": issue.student_id,
                "rule_id": issue.rule_id,
                "category": issue.issue_category,
                "severity": issue.severity,
                "field": issue.field,
                "source_row": issue.source_row,
                "explanation": issue.explanation,
                "recommended_correction": issue.recommended_correction,
                "resolution_status": issue.resolution_status
            } for issue in issues
        ]
    }
