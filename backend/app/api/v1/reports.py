"""Dashboard, analytics, anomaly detection, and reporting endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.models import Institution
from backend.app.models import Student
from backend.app.models import UploadBatch
from backend.app.models import ValidationIssue
from backend.app.models import AuditLog
from backend.app.models import ApprovedIntake
from backend.app.schemas import DashboardOverviewResponse
from backend.app.services.intake_monitoring.intake_service import intake_engine
from backend.app.services.anomaly_detection.detector import anomaly_service

router = APIRouter(prefix="/reports", tags=["Reports & Dashboard"])

@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Provides consolidated metrics for the React frontend Figma dashboard."""
    student_query = db.query(Student)
    inst_query = db.query(Institution)
    batch_query = db.query(UploadBatch)
    issue_query = db.query(ValidationIssue)
    
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id:
        student_query = student_query.filter(Student.institution_id == current_user.institution_id)
        inst_query = inst_query.filter(Institution.id == current_user.institution_id)
        batch_query = batch_query.filter(UploadBatch.institution_id == current_user.institution_id)
        issue_query = issue_query.join(Student, ValidationIssue.student_id == Student.id).filter(
            Student.institution_id == current_user.institution_id
        )

    total_insts = inst_query.count()
    total_students = student_query.count()
    validated = student_query.filter(Student.record_status == "VALIDATED").count()
    approved = student_query.filter(Student.record_status == "APPROVED").count()
    invalid = student_query.filter(Student.record_status == "FLAGGED").count()
    duplicates = student_query.filter(Student.is_duplicate == True).count()
    pending = student_query.filter(Student.record_status.in_(["PENDING_VALIDATION", "FLAGGED"])).count()

    # Intake violations count
    intakes = db.query(ApprovedIntake).all()
    violation_count = 0
    for intake in intakes:
        rep = intake_engine.verify_intake_for_programme(
            db=db, institution_id=intake.institution_id, programme=intake.programme, academic_year=intake.academic_year
        )
        if rep.get("alerts"):
            violation_count += 1

    # Category breakdown
    cat_counts = student_query.with_entities(Student.seat_category, func.count(Student.id)).group_by(Student.seat_category).all()
    cat_dist = {cat or "GENERAL": cnt for cat, cnt in cat_counts}

    # Recent uploads
    recent_batches = batch_query.order_by(UploadBatch.created_at.desc()).limit(5).all()
    recent_uploads_data = [
        {
            "id": b.id,
            "filename": b.original_filename,
            "total": b.total_records,
            "status": b.status,
            "timestamp": b.created_at.isoformat()
        } for b in recent_batches
    ]

    # Recent audit activities
    recent_audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(5).all()
    recent_act_data = [
        {
            "action": a.action,
            "actor": a.actor_email or "System",
            "target": a.target_type,
            "timestamp": a.timestamp.isoformat()
        } for a in recent_audit
    ]

    return DashboardOverviewResponse(
        total_institutions=total_insts,
        total_students=total_students,
        validated_records=validated,
        invalid_records=invalid,
        duplicate_records=duplicates,
        pending_verification=pending,
        intake_violations=violation_count,
        approved_records=approved,
        recent_uploads=recent_uploads_data,
        recent_activities=recent_act_data,
        category_distribution=cat_dist
    )

@router.get("/institutions")
def get_institution_reports(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    institutions = db.query(Institution).all()
    results = []
    for inst in institutions:
        st_count = db.query(Student).filter(Student.institution_id == inst.id).count()
        dup_count = db.query(Student).filter(Student.institution_id == inst.id, Student.is_duplicate == True).count()
        results.append({
            "institution_id": inst.id,
            "name": inst.name,
            "aishe_code": inst.aishe_code,
            "state": inst.state,
            "total_students": st_count,
            "duplicates": dup_count
        })
    return results

@router.get("/anomalies")
def get_ai_anomaly_report(
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    """Executes explainable AI / Isolation Forest anomaly detection across institutions."""
    institutions = db.query(Institution).all()
    metrics = []
    for inst in institutions:
        total = db.query(Student).filter(Student.institution_id == inst.id).count()
        dups = db.query(Student).filter(Student.institution_id == inst.id, Student.is_duplicate == True).count()
        nri = db.query(Student).filter(Student.institution_id == inst.id, Student.seat_category == "NRI").count()
        
        # Check quota overshoot
        overshoot = 0
        intakes = db.query(ApprovedIntake).filter(ApprovedIntake.institution_id == inst.id).all()
        for it in intakes:
            rep = intake_engine.verify_intake_for_programme(
                db=db, institution_id=inst.id, programme=it.programme, academic_year=it.academic_year
            )
            for alert in rep.get("alerts", []):
                overshoot += alert.get("difference", 0)

        metrics.append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "total_students": total,
            "duplicate_count": dups,
            "nri_count": nri,
            "quota_overshoot": overshoot
        })

    anomalies = anomaly_service.detect_enrollment_anomalies(metrics)
    return {
        "analyzed_institutions": len(metrics),
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies
    }
