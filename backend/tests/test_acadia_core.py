"""Comprehensive Pytest Suite for ACADIA Core Engine."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.security import (
    verify_password, get_password_hash, compute_hmac_fingerprint, mask_apaar_id
)
from backend.app.services.record_integrity.canonical import (
    create_canonical_json, compute_record_fingerprint, verify_record_fingerprint
)
from backend.app.services.record_integrity.signer import signature_service
from backend.app.services.validation.validator import validation_engine

client = TestClient(app)

# 1. Security & Fingerprinting Tests
def test_password_hashing():
    pw = "SecretTestPass123!"
    hashed = get_password_hash(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_keyed_hmac_fingerprint():
    id1 = "123456789012"
    id2 = "123456789012"
    id3 = "123456789013"
    fp1 = compute_hmac_fingerprint(id1)
    fp2 = compute_hmac_fingerprint(id2)
    fp3 = compute_hmac_fingerprint(id3)
    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64

def test_mask_apaar_id():
    assert mask_apaar_id("123456789012") == "XXXXXXXX9012"
    assert mask_apaar_id("9876") == "9876"
    assert mask_apaar_id("") == "N/A"

# 2. Validation Engine Tests
def test_apaar_validation_rules():
    # Valid record
    valid_rec = {
        "name": "Aarav Sharma",
        "apaar_id": "112233445566",
        "programme": "B.Tech Computer Science and Engineering",
        "academic_year": "2025-2026",
        "seat_category": "GENERAL"
    }
    issues = validation_engine.validate_record(valid_rec, None)
    assert len(issues) == 0

    # Invalid APAAR length (< 12 digits)
    invalid_rec = {
        "name": "Aarav Sharma",
        "apaar_id": "12345",
        "programme": "B.Tech Computer Science and Engineering",
        "academic_year": "2025-2026"
    }
    issues = validation_engine.validate_record(invalid_rec, None)
    assert any(i.rule_id == "RULE_APAAR_FORMAT" for i in issues)

    # Missing mandatory name
    missing_name = {
        "name": "",
        "apaar_id": "112233445566",
        "programme": "B.Tech Computer Science and Engineering",
        "academic_year": "2025-2026"
    }
    issues = validation_engine.validate_record(missing_name, None)
    assert any(i.rule_id == "RULE_NAME_MANDATORY" for i in issues)

# 3. Canonical Fingerprint and Tamper Verification Tests
def test_canonical_json_determinism():
    data1 = {"b": 2, "a": 1, "nested": {"y": 20, "x": 10}}
    data2 = {"a": 1, "nested": {"x": 10, "y": 20}, "b": 2}
    c1 = create_canonical_json(data1)
    c2 = create_canonical_json(data2)
    assert c1 == c2
    assert compute_record_fingerprint(c1) == compute_record_fingerprint(c2)

def test_tamper_detection():
    data = {"student_id": "ST-001", "name": "Rohan Verma", "apaar_masked": "XXXXXXXX5678"}
    canonical = create_canonical_json(data)
    fingerprint = compute_record_fingerprint(canonical)
    
    # Matching passes
    assert verify_record_fingerprint(canonical, fingerprint) is True

    # Tampered payload fails
    tampered_data = {"student_id": "ST-001", "name": "Rohan Verma (Modified)", "apaar_masked": "XXXXXXXX5678"}
    tampered_canonical = create_canonical_json(tampered_data)
    assert verify_record_fingerprint(tampered_canonical, fingerprint) is False

# 4. Cryptographic Ed25519 Digital Signature Tests
def test_ed25519_digital_signature():
    fingerprint = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    sig = signature_service.sign_fingerprint(fingerprint)
    assert sig is not None
    assert len(sig) > 0

    # Verification of genuine signature
    is_valid = signature_service.verify_signature(fingerprint, sig)
    assert is_valid is True

    # Verification of corrupted signature fails
    corrupted_sig = sig[:-4] + "AAAA"
    assert signature_service.verify_signature(fingerprint, corrupted_sig) is False

# 5. Full End-to-End API Integration Workflow Test
def test_e2e_workflow():
    # Step 1: Login as Admin
    login_res = client.post("/api/v1/auth/login", data={"username": "admin@acadia.gov.in", "password": "Admin@Acadia2026"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Check Dashboard Overview
    overview_res = client.get("/api/v1/reports/overview", headers=headers)
    assert overview_res.status_code == 200
    overview_data = overview_res.json()
    assert overview_data["total_institutions"] == 5
    assert overview_data["total_students"] >= 500

    # Step 3: Check Verification Duplicates
    dup_res = client.get("/api/v1/verification/duplicates", headers=headers)
    assert dup_res.status_code == 200
    assert dup_res.json()["total_duplicates"] > 0

    # Step 4: Check Intake Capacity Violations
    intake_res = client.get("/api/v1/verification/intake/alerts", headers=headers)
    assert intake_res.status_code == 200
    assert intake_res.json()["total_violations"] > 0

    # Step 5: Check AI Anomalies
    anomaly_res = client.get("/api/v1/reports/anomalies", headers=headers)
    assert anomaly_res.status_code == 200
    assert "anomalies" in anomaly_res.json()

    # Step 6: Upload a CSV Batch
    import uuid
    unique_apaar = f"99{str(uuid.uuid4().int)[:10]}"
    csv_content = (
        "student_name,apaar_id,programme,academic_year,seat_category\n"
        f"E2E Test Student,{unique_apaar},B.Tech Computer Science and Engineering,2025-2026,GENERAL\n"
        "E2E Invalid Student,999,B.Tech Computer Science and Engineering,2025-2026,GENERAL\n"
    )
    inst_res = client.get("/api/v1/institutions", headers=headers)
    inst_id = inst_res.json()[0]["id"]
    
    upload_res = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"institution_id": inst_id},
        files={"file": ("test_batch.csv", csv_content, "text/csv")}
    )
    assert upload_res.status_code == 200
    batch_data = upload_res.json()
    assert batch_data["total_records"] == 2
    assert batch_data["valid_records"] == 1
    assert batch_data["invalid_records"] == 1

    # Step 7: Seal an approved student record with version & digital signature
    students = client.get(f"/api/v1/students?institution_id={inst_id}&record_status=VALIDATED", headers=headers).json()
    assert len(students) > 0
    target_student_id = students[0]["id"]

    seal_res = client.post(f"/api/v1/integrity/{target_student_id}/seal", headers=headers)
    assert seal_res.status_code == 200
    seal_data = seal_res.json()
    assert seal_data["version_number"] == 1
    assert len(seal_data["fingerprint"]) == 64
    assert len(seal_data["signature"]) > 0

    # Step 8: Verify Record Integrity
    verify_res = client.post(f"/api/v1/integrity/{target_student_id}/verify", headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["is_valid"] is True
    assert verify_res.json()["signature_valid"] is True

    # Step 9: Generate QR Credential
    qr_res = client.post(f"/api/v1/qr/generate/{target_student_id}", headers=headers)
    assert qr_res.status_code == 200
    qr_data = qr_res.json()
    assert "qr_verification_token" in qr_data
    assert "qr_code_base64" in qr_data

    # Step 10: Scan / Publicly Verify QR Code Credential
    token_str = qr_data["qr_verification_token"]
    public_verify_res = client.get(f"/api/v1/qr/verify/{token_str}")
    assert public_verify_res.status_code == 200
    ver_payload = public_verify_res.json()
    assert ver_payload["verified"] is True
    assert ver_payload["status"] == "VERIFIED_AUTHENTIC"
    assert ver_payload["student_preview"]["student_name"] is not None
    # Privacy check: APAAR is masked in public response
    assert "X" in ver_payload["student_preview"]["apaar_masked"]
