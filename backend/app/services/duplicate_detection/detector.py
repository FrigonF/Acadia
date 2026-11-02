"""Privacy-preserving duplicate detection engine using keyed HMAC-SHA256."""
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from backend.app.core.security import compute_hmac_fingerprint, mask_apaar_id
from backend.app.models import Student
from backend.app.models import Institution

class DuplicateDetectionEngine:
    @staticmethod
    def detect_in_batch_duplicates(records: List[Dict[str, Any]]) -> Dict[str, List[int]]:
        """Identifies duplicate APAAR IDs within the same uploaded batch.
        Returns a dict mapping apaar_id -> list of source_rows.
        """
        seen: Dict[str, List[int]] = {}
        for r in records:
            apaar = r.get("apaar_id", "").strip()
            if not apaar:
                continue
            row = r.get("source_row", 0)
            seen.setdefault(apaar, []).append(row)
            
        duplicates = {apaar: rows for apaar, rows in seen.items() if len(rows) > 1}
        return duplicates

    @staticmethod
    def check_cross_institution_duplicates(
        db: Session,
        apaar_id: str,
        current_institution_id: str,
        current_student_id: str = None
    ) -> List[Dict[str, Any]]:
        """Compares keyed HMAC-SHA256 fingerprint against all existing student records across institutions.
        
        Returns details of matching registrations across institutions without leaking unencrypted IDs.
        """
        fingerprint = compute_hmac_fingerprint(apaar_id)
        
        query = db.query(Student, Institution).join(
            Institution, Student.institution_id == Institution.id
        ).filter(
            Student.apaar_fingerprint == fingerprint
        )
        
        if current_student_id:
            query = query.filter(Student.id != current_student_id)
            
        matches = query.all()
        results = []
        for student_record, inst in matches:
            is_same_institution = (student_record.institution_id == current_institution_id)
            results.append({
                "student_id": student_record.id,
                "student_name": student_record.name,
                "institution_id": inst.id,
                "institution_name": inst.name,
                "aishe_code": inst.aishe_code,
                "programme": student_record.programme,
                "academic_year": student_record.academic_year,
                "seat_category": student_record.seat_category,
                "duplicate_type": "WITHIN_INSTITUTION" if is_same_institution else "CROSS_INSTITUTION",
                "record_status": student_record.record_status,
                "apaar_masked": student_record.apaar_masked
            })
            
        return results

duplicate_engine = DuplicateDetectionEngine()
