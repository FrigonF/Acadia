"""Intake verification and capacity monitoring engine."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models import Student
from backend.app.models import ApprovedIntake
from backend.app.models import Institution

class IntakeVerificationEngine:
    @staticmethod
    def verify_intake_for_programme(
        db: Session,
        institution_id: str,
        programme: str,
        academic_year: str
    ) -> Dict[str, Any]:
        """Calculates actual enrollments vs approved capacities for general, NRI, OCI, FN, supernumerary seats."""
        intake_spec = db.query(ApprovedIntake).filter(
            ApprovedIntake.institution_id == institution_id,
            func.lower(ApprovedIntake.programme) == programme.lower(),
            ApprovedIntake.academic_year == academic_year
        ).first()

        inst = db.query(Institution).filter(Institution.id == institution_id).first()
        inst_name = inst.name if inst else "Unknown Institution"

        # Query active enrollment counts grouped by seat_category (excludes REJECTED and DEACTIVATED)
        enrollment_counts = db.query(
            Student.seat_category, func.count(Student.id)
        ).filter(
            Student.institution_id == institution_id,
            func.lower(Student.programme) == programme.lower(),
            Student.academic_year == academic_year,
            Student.record_status.notin_(["REJECTED", "DEACTIVATED"])
        ).group_by(Student.seat_category).all()

        cat_counts = {cat.upper() if cat else "GENERAL": count for cat, count in enrollment_counts}
        total_enrolled = sum(cat_counts.values())

        if not intake_spec:
            return {
                "configured": False,
                "institution_id": institution_id,
                "institution_name": inst_name,
                "programme": programme,
                "academic_year": academic_year,
                "approved_intake": 0,
                "total_enrolled": total_enrolled,
                "alerts": [{
                    "severity": "WARNING",
                    "category": "INTAKE_UNCONFIGURED",
                    "explanation": f"No approved intake quota found for programme '{programme}' in academic year '{academic_year}'."
                }]
            }

        alerts = []

        # 1. Check general/main intake limit
        # Main categories typically include GENERAL, OBC, SC, ST, EWS
        main_categories = ["GENERAL", "OBC", "SC", "ST", "EWS"]
        main_enrolled = sum(cat_counts.get(c, 0) for c in main_categories)
        if main_enrolled > intake_spec.approved_intake:
            excess = main_enrolled - intake_spec.approved_intake
            alerts.append({
                "severity": "CRITICAL",
                "category": "INTAKE_EXCEEDED",
                "affected_category": "MAIN_INTAKE",
                "approved_capacity": intake_spec.approved_intake,
                "actual_enrollment": main_enrolled,
                "difference": excess,
                "explanation": f"Main intake exceeded by {excess} students (Approved: {intake_spec.approved_intake}, Enrolled: {main_enrolled})."
            })

        # 2. Check NRI category
        nri_enrolled = cat_counts.get("NRI", 0)
        if intake_spec.nri_seats > 0 and nri_enrolled > intake_spec.nri_seats:
            excess = nri_enrolled - intake_spec.nri_seats
            alerts.append({
                "severity": "CRITICAL",
                "category": "NRI_LIMIT_EXCEEDED",
                "affected_category": "NRI",
                "approved_capacity": intake_spec.nri_seats,
                "actual_enrollment": nri_enrolled,
                "difference": excess,
                "explanation": f"NRI quota exceeded by {excess} students (Approved: {intake_spec.nri_seats}, Enrolled: {nri_enrolled})."
            })

        # 3. Check OCI category
        oci_enrolled = cat_counts.get("OCI", 0)
        if intake_spec.oci_seats > 0 and oci_enrolled > intake_spec.oci_seats:
            excess = oci_enrolled - intake_spec.oci_seats
            alerts.append({
                "severity": "CRITICAL",
                "category": "OCI_LIMIT_EXCEEDED",
                "affected_category": "OCI",
                "approved_capacity": intake_spec.oci_seats,
                "actual_enrollment": oci_enrolled,
                "difference": excess,
                "explanation": f"OCI quota exceeded by {excess} students (Approved: {intake_spec.oci_seats}, Enrolled: {oci_enrolled})."
            })

        # 4. Check FN (Foreign National) category
        fn_enrolled = cat_counts.get("FN", 0)
        if intake_spec.fn_seats > 0 and fn_enrolled > intake_spec.fn_seats:
            excess = fn_enrolled - intake_spec.fn_seats
            alerts.append({
                "severity": "CRITICAL",
                "category": "FN_LIMIT_EXCEEDED",
                "affected_category": "FN",
                "approved_capacity": intake_spec.fn_seats,
                "actual_enrollment": fn_enrolled,
                "difference": excess,
                "explanation": f"Foreign National quota exceeded by {excess} students (Approved: {intake_spec.fn_seats}, Enrolled: {fn_enrolled})."
            })

        # 5. Check Supernumerary / TFWS
        tfws_enrolled = cat_counts.get("TFWS", 0)
        if intake_spec.approved_supernumerary > 0 and tfws_enrolled > intake_spec.approved_supernumerary:
            excess = tfws_enrolled - intake_spec.approved_supernumerary
            alerts.append({
                "severity": "WARNING",
                "category": "SUPERNUMERARY_EXCEEDED",
                "affected_category": "TFWS/SUPERNUMERARY",
                "approved_capacity": intake_spec.approved_supernumerary,
                "actual_enrollment": tfws_enrolled,
                "difference": excess,
                "explanation": f"Supernumerary / TFWS quota exceeded by {excess} students."
            })

        return {
            "configured": True,
            "institution_id": institution_id,
            "institution_name": inst_name,
            "programme": programme,
            "academic_year": academic_year,
            "approved_intake": intake_spec.approved_intake,
            "approved_supernumerary": intake_spec.approved_supernumerary,
            "nri_seats": intake_spec.nri_seats,
            "oci_seats": intake_spec.oci_seats,
            "fn_seats": intake_spec.fn_seats,
            "total_enrolled": total_enrolled,
            "breakdown_by_category": cat_counts,
            "alerts": alerts
        }

intake_engine = IntakeVerificationEngine()
