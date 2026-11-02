"""Duplicate detection and intake verification execution endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import Student
from backend.app.models import ApprovedIntake
from backend.app.services.duplicate_detection.detector import duplicate_engine
from backend.app.services.intake_monitoring.intake_service import intake_engine

router = APIRouter(prefix="/verification", tags=["Verification"])

@router.get("/duplicates")
def get_duplicates(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all duplicate flagged students across or within institutions."""
    query = db.query(Student).filter(Student.is_duplicate == True)
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        query = query.filter(Student.institution_id == current_user.institution_id)
        
    dups = query.all()
    results = []
    for s in dups:
        cross_info = duplicate_engine.check_cross_institution_duplicates(
            db, apaar_id=s.apaar_id, current_institution_id=s.institution_id, current_student_id=s.id
        )
        results.append({
            "student_id": s.id,
            "student_name": s.name,
            "apaar_masked": s.apaar_masked,
            "institution_id": s.institution_id,
            "programme": s.programme,
            "academic_year": s.academic_year,
            "duplicate_type": s.duplicate_type,
            "matched_records": cross_info
        })
    return {"total_duplicates": len(results), "records": results}

@router.post("/duplicates/check-single")
def check_single_apaar_duplicates(
    apaar_id: str = Query(...),
    institution_id: Optional[str] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inst_id = institution_id or current_user.institution_id or ""
    matches = duplicate_engine.check_cross_institution_duplicates(db, apaar_id=apaar_id, current_institution_id=inst_id)
    return {
        "apaar_masked": s_masked if 's_masked' in locals() else (apaar_id[:2] + "XXXXXXXX" + apaar_id[-2:] if len(apaar_id)==12 else "INVALID"),
        "match_count": len(matches),
        "matches": matches
    }

@router.get("/intake/alerts")
def get_intake_alerts(
    institution_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calculates intake discrepancies and capacity violations."""
    target_inst = institution_id
    if current_user.role == UserRole.INSTITUTION_ADMIN.value:
        target_inst = current_user.institution_id

    query = db.query(ApprovedIntake)
    if target_inst:
        query = query.filter(ApprovedIntake.institution_id == target_inst)
    if academic_year:
        query = query.filter(ApprovedIntake.academic_year == academic_year)
        
    intakes = query.all()
    alerts = []
    
    for intake in intakes:
        report = intake_engine.verify_intake_for_programme(
            db=db,
            institution_id=intake.institution_id,
            programme=intake.programme,
            academic_year=intake.academic_year
        )
        if report.get("alerts"):
            alerts.append(report)
            
    return {"total_violations": len(alerts), "details": alerts}
