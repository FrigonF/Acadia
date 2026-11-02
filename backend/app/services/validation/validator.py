"""Rule-based APAAR validation engine with explainable issues and recommended fixes."""
import re
from typing import List, Dict, Any, Optional

class ValidationRuleResult:
    def __init__(
        self,
        rule_id: str,
        passed: bool,
        severity: str, # CRITICAL, WARNING, INFO
        category: str, # APAAR_FORMAT, MISSING_FIELD, CONFLICT, INSTITUTION_CHECK
        field: str,
        source_row: int,
        explanation: str,
        recommended_correction: str
    ):
        self.rule_id = rule_id
        self.passed = passed
        self.severity = severity
        self.category = category
        self.field = field
        self.source_row = source_row
        self.explanation = explanation
        self.recommended_correction = recommended_correction

class ValidationEngine:
    # 12-digit numeric regex format for APAAR ID
    APAAR_REGEX = re.compile(r"^\d{12}$")
    ACADEMIC_YEAR_REGEX = re.compile(r"^\d{4}-\d{4}$")

    @classmethod
    def validate_record(
        cls,
        record: Dict[str, Any],
        institution,
        existing_records_in_batch: List[Dict[str, Any]] = None
    ) -> List[ValidationRuleResult]:
        """Runs all deterministic validation rules against a student record."""
        issues: List[ValidationRuleResult] = []
        source_row = record.get("source_row", 0)
        
        # 1. Rule RULE_APAAR_MANDATORY: Check APAAR presence
        apaar = record.get("apaar_id", "").strip()
        if not apaar:
            issues.append(ValidationRuleResult(
                rule_id="RULE_APAAR_MANDATORY",
                passed=False,
                severity="CRITICAL",
                category="MISSING_FIELD",
                field="apaar_id",
                source_row=source_row,
                explanation="APAAR ID is missing or empty.",
                recommended_correction="Provide the 12-digit APAAR ID assigned by the Ministry of Education / Digilocker."
            ))
        else:
            # 2. Rule RULE_APAAR_FORMAT: Exactly 12 digits
            if not cls.APAAR_REGEX.match(apaar):
                issues.append(ValidationRuleResult(
                    rule_id="RULE_APAAR_FORMAT",
                    passed=False,
                    severity="CRITICAL",
                    category="APAAR_FORMAT",
                    field="apaar_id",
                    source_row=source_row,
                    explanation=f"APAAR ID '{apaar}' does not conform to the required 12-digit numeric format.",
                    recommended_correction="Ensure the APAAR ID consists of exactly 12 numeric digits without hyphens or spaces."
                ))

        # 3. Rule RULE_NAME_MANDATORY: Name presence and length
        name = record.get("name", "").strip()
        if not name or len(name) < 2:
            issues.append(ValidationRuleResult(
                rule_id="RULE_NAME_MANDATORY",
                passed=False,
                severity="CRITICAL",
                category="MISSING_FIELD",
                field="name",
                source_row=source_row,
                explanation="Student name is missing or too short.",
                recommended_correction="Enter the full official name of the student as recorded in secondary certificates."
            ))

        # 4. Rule RULE_PROGRAMME_VALIDITY: Programme must be approved for the institution
        programme = record.get("programme", "").strip()
        if not programme:
            issues.append(ValidationRuleResult(
                rule_id="RULE_PROGRAMME_MANDATORY",
                passed=False,
                severity="CRITICAL",
                category="MISSING_FIELD",
                field="programme",
                source_row=source_row,
                explanation="Programme / branch field is required.",
                recommended_correction="Specify the AICTE-approved academic programme name (e.g., 'B.Tech Computer Science and Engineering')."
            ))
        elif institution and institution.approved_programmes:
            # Case-insensitive match against approved programmes
            approved_lower = [p.lower() for p in institution.approved_programmes]
            if programme.lower() not in approved_lower:
                issues.append(ValidationRuleResult(
                    rule_id="RULE_PROGRAMME_UNAPPROVED",
                    passed=False,
                    severity="WARNING",
                    category="INSTITUTION_CHECK",
                    field="programme",
                    source_row=source_row,
                    explanation=f"Programme '{programme}' is not currently in the AICTE-approved list for {institution.name}.",
                    recommended_correction=f"Verify programme against approved list: {', '.join(institution.approved_programmes[:3])}..."
                ))

        # 5. Rule RULE_ACADEMIC_YEAR_FORMAT: Check format YYYY-YYYY
        acad_year = record.get("academic_year", "").strip()
        if not acad_year:
            issues.append(ValidationRuleResult(
                rule_id="RULE_ACAD_YEAR_MANDATORY",
                passed=False,
                severity="CRITICAL",
                category="MISSING_FIELD",
                field="academic_year",
                source_row=source_row,
                explanation="Academic year is missing.",
                recommended_correction="Provide academic year in format 'YYYY-YYYY' (e.g. 2025-2026)."
            ))
        elif not cls.ACADEMIC_YEAR_REGEX.match(acad_year):
            issues.append(ValidationRuleResult(
                rule_id="RULE_ACAD_YEAR_FORMAT",
                passed=False,
                severity="WARNING",
                category="CONFLICT",
                field="academic_year",
                source_row=source_row,
                explanation=f"Academic year '{acad_year}' does not match standard 'YYYY-YYYY' format.",
                recommended_correction="Normalize academic year to 'YYYY-YYYY' (e.g. 2025-2026)."
            ))
            
        # 6. Rule RULE_SEAT_CATEGORY: Valid seat category
        valid_categories = {"GENERAL", "OBC", "SC", "ST", "EWS", "TFWS", "NRI", "OCI", "FN", "MANAGEMENT", "PWD"}
        seat_cat = (record.get("seat_category") or "GENERAL").strip().upper()
        if seat_cat not in valid_categories:
            issues.append(ValidationRuleResult(
                rule_id="RULE_SEAT_CATEGORY_INVALID",
                passed=False,
                severity="WARNING",
                category="CONFLICT",
                field="seat_category",
                source_row=source_row,
                explanation=f"Seat category '{seat_cat}' is unrecognized.",
                recommended_correction=f"Map seat category to one of: {', '.join(sorted(valid_categories))}."
            ))

        return issues

validation_engine = ValidationEngine()
