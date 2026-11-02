"""Key rotation, cryptographic verification, and audit chain automated regression tests."""
import pytest
import secrets
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.core.security import (
    encrypt_identifier, decrypt_identifier, register_field_key, compute_hmac_fingerprint
)
from backend.app.services.record_integrity.signer import signature_service
from backend.app.services.record_integrity.migration import migrate_student_identifiers
from backend.app.services.reporting.audit_service import verify_audit_trail_integrity, log_audit_event
from backend.app.models import Student, AuditLog

client = TestClient(app)

# 1. New key signs and verifies successfully
def test_new_key_sign_and_verify():
    test_fp = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    sig = signature_service.sign_fingerprint(test_fp)
    assert sig is not None
    assert signature_service.verify_signature(
        fingerprint=test_fp,
        signature_b64=sig,
        key_id=signature_service.key_id
    ) is True

# 2. Compromised legacy dev key fails verification
def test_compromised_legacy_key_fails_verification():
    # Attempt verification with compromised key id "acadia-dev-key-2026-v1"
    compromised_seed = bytes.fromhex("4a5c6d7e8f901234567890abcdef1234567890abcdef1234567890abcdef1234")
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(compromised_seed)
    pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    test_fp = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    sig = base64.b64encode(priv.sign(test_fp.encode('utf-8'))).decode('utf-8')

    # Explicitly check that revoked / compromised key fails
    assert signature_service.verify_signature(
        fingerprint=test_fp,
        signature_b64=sig,
        key_id="acadia-dev-key-2026-v1",
        public_key_pem=pem
    ) is False

# 3. Arbitrary unknown key fails verification
def test_arbitrary_unknown_key_fails():
    foreign_priv = ed25519.Ed25519PrivateKey.generate()
    foreign_pem = foreign_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    test_fp = "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999"
    sig = base64.b64encode(foreign_priv.sign(test_fp.encode('utf-8'))).decode('utf-8')

    assert signature_service.verify_signature(
        fingerprint=test_fp,
        signature_b64=sig,
        key_id="unregistered-foreign-key",
        public_key_pem=foreign_pem
    ) is False

# 4. Multi-version AES-256-GCM field encryption & keyring
def test_multi_version_aes_encryption():
    plain_apaar = "889900112233"
    
    # 1. Encrypt with v1
    ct_v1 = encrypt_identifier(plain_apaar, key_version="v1")
    assert ct_v1.startswith("enc:v1:")
    assert decrypt_identifier(ct_v1) == plain_apaar

    # 2. Register rotated v2 key into keyring
    new_v2_hex = secrets.token_hex(32)
    register_field_key("v2", new_v2_hex)

    # 3. Encrypt with v2
    ct_v2 = encrypt_identifier(plain_apaar, key_version="v2")
    assert ct_v2.startswith("enc:v2:")
    assert decrypt_identifier(ct_v2) == plain_apaar

    # 4. Confirm v1 still decrypts seamlessly via keyring
    assert decrypt_identifier(ct_v1) == plain_apaar

# 5. Zero-knowledge HMAC duplicate fingerprint migration
def test_hmac_duplicate_migration():
    db = SessionLocal()
    original_hmac = settings.HMAC_SECRET_KEY
    new_test_hmac = secrets.token_hex(32)
    
    try:
        # Migrate to new key
        res = migrate_student_identifiers(
            db,
            new_hmac_key=new_test_hmac,
            actor_email="security-tester@acadia.gov.in"
        )
        assert res["status"] == "MIGRATION_COMPLETED"
        assert res["migrated_records"] > 0
        assert res["preserved_duplicates"] > 0
        
        dups_in_db = db.query(Student).filter(Student.is_duplicate == True).count()
        assert dups_in_db >= res["preserved_duplicates"]
    finally:
        # Restore active settings HMAC so subsequent test suites operate on standard configuration
        migrate_student_identifiers(
            db,
            new_hmac_key=original_hmac,
            actor_email="security-cleanup@acadia.gov.in"
        )
        db.close()

# 6. Tamper-evident Audit Hash Chain Verification
def test_audit_hash_chain_verification():
    db = SessionLocal()
    # Log 3 linked events
    e1 = log_audit_event(db, action="CHAIN_TEST_1", target_type="TEST")
    e2 = log_audit_event(db, action="CHAIN_TEST_2", target_type="TEST")
    e3 = log_audit_event(db, action="CHAIN_TEST_3", target_type="TEST")

    assert e1.entry_hash is not None
    assert e2.previous_entry_hash == e1.entry_hash
    assert e3.previous_entry_hash == e2.entry_hash

    # Verify chain integrity
    report = verify_audit_trail_integrity(db, limit=50)
    assert report["chain_valid"] is True
    assert report["status"] == "CHAIN_VERIFIED"
    db.close()
