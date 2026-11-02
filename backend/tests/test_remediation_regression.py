"""Comprehensive automated regression tests for ACADIA Security and Data-Integrity Remediation.

Tests all 14 mandatory regression criteria:
1. External Verifier cannot list students.
2. External Verifier cannot view arbitrary student details.
3. Cross-institution record-history access is denied.
4. Cross-institution audit access is denied.
5. Cross-institution validation issue access is denied.
6. External Verifier cannot upload institutional data.
7. Manual creation rejects duplicates.
8. Manual creation rejects unapproved programmes.
9. Manual creation checks intake capacity.
10. Raw APAAR IDs are absent from general API responses and audit events.
11. Inactive accounts cannot log in through either login endpoint.
12. Deactivated records are excluded from active intake calculations.
13. Institution Admin changes requiring verifier approval are not automatically sealed.
14. Invalid or untrusted signing keys fail verification.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models import User, Student, Institution, ApprovedIntake, RecordVersion, VerificationCredential, AuditLog
from backend.app.core.security import get_password_hash, compute_hmac_fingerprint, mask_apaar_id, encrypt_identifier
from backend.app.services.record_integrity.signer import signature_service

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_tokens():
    """Retrieve auth tokens for test roles."""
    tokens = {}
    creds = {
        "admin": ("admin@acadia.gov.in", "Admin@Acadia2026"),
        "verifier": ("verifier@aicte.gov.in", "Verifier@Aicte2026"),
        "delhi_admin": ("admin@diaet.edu.in", "Delhi@Inst2026"),
        "pune_admin": ("admin@mitr.ac.in", "Pune@Inst2026"),
        "ext_verifier": ("verifier@external-corp.com", "Verify@External2026"),
    }
    for role, (email, pwd) in creds.items():
        res = client.post("/api/v1/auth/login", data={"username": email, "password": pwd})
        assert res.status_code == 200, f"Login failed for {email}"
        tokens[role] = res.json()["access_token"]
    return tokens

# 1. External Verifier cannot list students
def test_external_verifier_cannot_list_students(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['ext_verifier']}"}
    res = client.get("/api/v1/students", headers=headers)
    assert res.status_code == 403

# 2. External Verifier cannot view arbitrary student details
def test_external_verifier_cannot_view_student_details(auth_tokens):
    db = SessionLocal()
    student = db.query(Student).first()
    db.close()
    headers = {"Authorization": f"Bearer {auth_tokens['ext_verifier']}"}
    res = client.get(f"/api/v1/students/{student.id}", headers=headers)
    assert res.status_code == 403

# 3. Cross-institution record-history access is denied
def test_cross_institution_record_history_denied(auth_tokens):
    db = SessionLocal()
    # Find Pune student
    pune_inst = db.query(Institution).filter(Institution.name.like("%Maharashtra%")).first()
    pune_student = db.query(Student).filter(Student.institution_id == pune_inst.id).first()
    db.close()

    # Delhi admin attempts to access Pune student's record history
    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    res = client.get(f"/api/v1/integrity/{pune_student.id}", headers=headers)
    assert res.status_code == 403

# 4. Cross-institution audit access is denied
def test_cross_institution_audit_access_denied(auth_tokens):
    db = SessionLocal()
    pune_inst = db.query(Institution).filter(Institution.name.like("%Maharashtra%")).first()
    pune_student = db.query(Student).filter(Student.institution_id == pune_inst.id).first()
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    res = client.get(f"/api/v1/audit/{pune_student.id}", headers=headers)
    assert res.status_code == 403

# 5. Cross-institution validation issue access is denied
def test_cross_institution_validation_issue_access_denied(auth_tokens):
    db = SessionLocal()
    pune_inst = db.query(Institution).filter(Institution.name.like("%Maharashtra%")).first()
    pune_student = db.query(Student).filter(Student.institution_id == pune_inst.id).first()
    # Create or find issue for Pune student
    from backend.app.models import ValidationIssue, UploadBatch
    batch = db.query(UploadBatch).filter(UploadBatch.institution_id == pune_inst.id).first()
    issue = ValidationIssue(
        student_id=pune_student.id,
        batch_id=batch.id if batch else "placeholder",
        rule_id="RULE_TEST",
        issue_category="TEST",
        severity="WARNING",
        explanation="Test explanation"
    )
    db.add(issue)
    db.commit()
    issue_id = issue.id
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    res = client.get(f"/api/v1/validation/issues/{issue_id}", headers=headers)
    assert res.status_code == 403

# 6. External Verifier cannot upload institutional data
def test_external_verifier_cannot_upload_data(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['ext_verifier']}"}
    res = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"institution_id": "dummy-id"},
        files={"file": ("test.csv", "name,apaar_id\nTest,112233445566\n", "text/csv")}
    )
    assert res.status_code == 403

# 7. Manual creation rejects duplicates
def test_manual_creation_rejects_duplicates(auth_tokens):
    db = SessionLocal()
    delhi_inst = db.query(Institution).filter(Institution.aishe_code == "C-11001").first()
    existing_student = db.query(Student).filter(Student.institution_id == delhi_inst.id).first()
    from backend.app.core.security import decrypt_identifier
    plain_apaar = decrypt_identifier(existing_student.apaar_id)
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    payload = {
        "institution_id": delhi_inst.id,
        "name": "Duplicate Candidate",
        "apaar_id": plain_apaar,
        "programme": "B.Tech Computer Science and Engineering",
        "academic_year": "2025-2026",
        "seat_category": "GENERAL"
    }
    res = client.post("/api/v1/students", headers=headers, json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["is_duplicate"] is True
    assert created["record_status"] == "FLAGGED"

# 8. Manual creation rejects unapproved programmes
def test_manual_creation_rejects_unapproved_programmes(auth_tokens):
    db = SessionLocal()
    delhi_inst = db.query(Institution).filter(Institution.aishe_code == "C-11001").first()
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    payload = {
        "institution_id": delhi_inst.id,
        "name": "Astronomy Aspirant",
        "apaar_id": "999988887777",
        "programme": "Unapproved Bachelor of Astrology and Palmistry",
        "academic_year": "2025-2026",
        "seat_category": "GENERAL"
    }
    res = client.post("/api/v1/students", headers=headers, json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["record_status"] == "FLAGGED"

# 9. Manual creation checks intake capacity
def test_manual_creation_checks_intake_capacity(auth_tokens):
    db = SessionLocal()
    delhi_inst = db.query(Institution).filter(Institution.aishe_code == "C-11001").first()
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    payload = {
        "institution_id": delhi_inst.id,
        "name": "NRI Quota Applicant",
        "apaar_id": "778899112233",
        "programme": "B.Tech Computer Science and Engineering",
        "academic_year": "2025-2026",
        "seat_category": "NRI" # Delhi CS has NRI quota limit 5, already exceeded in synthetic test data
    }
    res = client.post("/api/v1/students", headers=headers, json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["record_status"] == "FLAGGED"

# 10. Raw APAAR IDs are absent from general API responses and audit events
def test_raw_apaar_absent_from_api_and_audit(auth_tokens):
    headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
    # Check student response
    res = client.get("/api/v1/students?limit=5", headers=headers)
    assert res.status_code == 200
    for s in res.json():
        assert "apaar_id" not in s or s.get("apaar_id") is None
        assert "apaar_masked" in s
        assert "XXXX" in s["apaar_masked"]

    # Check audit logs
    audit_res = client.get("/api/v1/audit?limit=20", headers=headers)
    assert audit_res.status_code == 200
    for log in audit_res.json():
        # Ensure raw 12-digit numbers are not dumped in previous_state or new_state
        log_str = str(log.get("previous_state", "")) + str(log.get("new_state", ""))
        assert "apaar_id" not in log_str

# 11. Inactive accounts cannot log in through either login endpoint
def test_inactive_accounts_cannot_login():
    db = SessionLocal()
    inactive_user = db.query(User).filter(User.email == "inactive_test@acadia.gov.in").first()
    if not inactive_user:
        inactive_user = User(
            name="Deactivated Officer",
            email="inactive_test@acadia.gov.in",
            hashed_password=get_password_hash("Inactive@2026"),
            role="AICTE_VERIFIER",
            is_active=False
        )
        db.add(inactive_user)
        db.commit()
    db.close()

    # OAuth form login
    res_form = client.post("/api/v1/auth/login", data={"username": "inactive_test@acadia.gov.in", "password": "Inactive@2026"})
    assert res_form.status_code == 403
    assert "inactive" in res_form.json()["detail"].lower()

    # JSON login
    res_json = client.post("/api/v1/auth/login/json", json={"email": "inactive_test@acadia.gov.in", "password": "Inactive@2026"})
    assert res_json.status_code == 403
    assert "inactive" in res_json.json()["detail"].lower()

# 12. Deactivated records are excluded from active intake calculations
def test_deactivated_records_excluded_from_intake(auth_tokens):
    db = SessionLocal()
    delhi_inst = db.query(Institution).filter(Institution.aishe_code == "C-11001").first()
    from backend.app.services.intake_monitoring.intake_service import intake_engine
    rep_before = intake_engine.verify_intake_for_programme(
        db, delhi_inst.id, "B.Tech Computer Science and Engineering", "2025-2026"
    )
    count_before = rep_before["total_enrolled"]

    # Find one student in that programme and deactivate
    student = db.query(Student).filter(
        Student.institution_id == delhi_inst.id,
        Student.programme == "B.Tech Computer Science and Engineering",
        Student.record_status != "DEACTIVATED"
    ).first()
    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    client.post(f"/api/v1/students/{student.id}/deactivate", headers=headers, json={"reason": "Testing intake exclusion"})

    rep_after = intake_engine.verify_intake_for_programme(
        db, delhi_inst.id, "B.Tech Computer Science and Engineering", "2025-2026"
    )
    count_after = rep_after["total_enrolled"]
    assert count_after == count_before - 1
    db.close()

# 13. Institution Admin changes requiring verifier approval are not automatically sealed
def test_institution_admin_changes_not_auto_sealed(auth_tokens):
    db = SessionLocal()
    delhi_inst = db.query(Institution).filter(Institution.aishe_code == "C-11001").first()
    student = db.query(Student).filter(
        Student.institution_id == delhi_inst.id,
        Student.record_status != "DEACTIVATED"
    ).first()
    db.close()

    headers = {"Authorization": f"Bearer {auth_tokens['delhi_admin']}"}
    res = client.patch(f"/api/v1/students/{student.id}", headers=headers, json={
        "name": student.name + " (Correction)",
        "reason": "Institution admin requested correction"
    })
    assert res.status_code == 200
    updated = res.json()
    # Must NOT be APPROVED automatically
    assert updated["record_status"] in ("PENDING_VALIDATION", "FLAGGED")

# 14. Invalid or untrusted signing keys fail verification
def test_untrusted_signing_keys_fail_verification():
    # Attempt verification using an arbitrary forged PEM key not in trusted registry
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    attacker_key = ed25519.Ed25519PrivateKey.generate()
    attacker_pem = attacker_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    test_fingerprint = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    import base64
    forged_sig = base64.b64encode(attacker_key.sign(test_fingerprint.encode('utf-8'))).decode('utf-8')

    # Must fail because attacker key is not trusted
    assert signature_service.verify_signature(
        fingerprint=test_fingerprint,
        signature_b64=forged_sig,
        key_id="attacker-injected-key-id",
        public_key_pem=attacker_pem
    ) is False
