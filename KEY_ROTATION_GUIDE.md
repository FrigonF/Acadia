# ACADIA Cryptographic Key Rotation & Management Guide

## 1. Threat Model & Key Compromise Notice
During early development iterations, default signing seeds and test HMAC salts were present in test files and repository samples. Per standard security protocol:
> **All previously exposed development keys (`acadia-dev-key-2026-v1`) must be treated as permanently compromised and are explicitly revoked in `settings.REVOKED_KEY_IDS`.**

ACADIA enforces strict fail-safe validation via `Settings.validate_production_security`: if any known development key or weak secret is detected when `ENV=production`, the application refuses to start.

---

## 2. Key Architecture & Responsibilities

| Key Purpose | Algorithm | Storage Location | Protection Strategy |
| :--- | :--- | :--- | :--- |
| **JWT Access Tokens** | HMAC-SHA256 | Environment (`SECRET_KEY`) | Minimum 32-char high-entropy random string. Short-lived 2-hour tokens. |
| **Identifier Fingerprinting** | Keyed HMAC-SHA256 | Environment (`HMAC_SECRET_KEY`) | 256-bit secret salt preventing rainbow/dictionary attacks against 12-digit APAAR IDs. |
| **Data-at-Rest Encryption** | AES-256-GCM | Environment (`FIELD_ENCRYPTION_KEY`, `FIELD_KEYRING`) | Authenticated ciphertext with 96-bit unique random nonces per field. Key version header `enc:<version>:<payload>`. |
| **Record Sealing** | Ed25519 Asymmetric | Environment / HSM (`ED25519_PRIVATE_KEY_HEX`) | 32-byte private seed for signing. Public keys registered in `TRUSTED_PUBLIC_KEYS`. |

---

## 3. Trusted Public Key Registry & Revocation

To prevent an attacker from modifying database records and forging signatures with an arbitrary injected public key stored in mutable database rows:
1. `RecordVersion` stores `key_id` alongside the signature.
2. `DigitalSignatureService.verify_signature` requires that `key_id` must match a **pre-registered trusted public key** in `settings.TRUSTED_PUBLIC_KEYS` or the active signing key.
3. If `key_id` is in `settings.REVOKED_KEY_IDS`, verification immediately returns `False`.
4. Verification fails immediately if the key is untrusted, revoked, or unregistered.

---

## 4. Ed25519 Key Rotation Procedure

When rotating the Ed25519 signing key:
1. **Generate New Key Pair**:
   ```python
   from cryptography.hazmat.primitives.asymmetric import ed25519
   from cryptography.hazmat.primitives import serialization

   priv = ed25519.Ed25519PrivateKey.generate()
   seed_hex = priv.private_bytes_raw().hex()
   pub_pem = priv.public_key().public_bytes(
       encoding=serialization.Encoding.PEM,
       format=serialization.PublicFormat.SubjectPublicKeyInfo
   ).decode('utf-8')

   print("ED25519_PRIVATE_KEY_HEX=" + seed_hex)
   print("KEY_ID=acadia-prod-2026-v3")
   ```
2. **Retain Historical Public Keys**:
   Append the previous key's public PEM into `TRUSTED_PUBLIC_KEYS` in your production environment config:
   ```json
   TRUSTED_PUBLIC_KEYS={"acadia-active-key-2026-v2": "-----BEGIN PUBLIC KEY-----\n..."}
   ```
3. **Deploy & Verify**:
   - Existing sealed records signed with `acadia-active-key-2026-v2` verify against the trusted historical public key.
   - Newly sealed versions will sign with `acadia-prod-2026-v3`.

---

## 5. AES-256-GCM Keyring Rotation & HMAC Migration

### Field-Level Encryption Rotation
ACADIA uses key-versioned payloads (`enc:v1:...`, `enc:v2:...`). When rotating the data-at-rest encryption key:
1. Retain the old key in `FIELD_KEYRING`:
   ```python
   FIELD_KEYRING={"v1": "<old_64_hex_key>"}
   ACTIVE_KEY_VERSION="v2"
   FIELD_ENCRYPTION_KEY="<new_64_hex_key>"
   ```
2. Any record encrypted under `v1` will decrypt through the keyring, while all newly created or updated records are encrypted using `v2`.

### HMAC Duplicate Detection Salt Migration
If the HMAC duplicate detection secret must be rotated:
Execute the zero-knowledge migration utility:
```python
from backend.app.core.database import SessionLocal
from backend.app.services.record_integrity.migration import migrate_student_identifiers

db = SessionLocal()
migrate_student_identifiers(
    db,
    new_hmac_key="<new_64_hex_key>",
    new_field_encryption_key="<new_aes_key>",
    new_field_version="v2",
    actor_email="admin@acadia.gov.in"
)
db.close()
```
This routine re-indexes all HMAC fingerprints under the new key and re-encrypts stored identifiers without ever writing plaintext identifiers to logs or audit records.
