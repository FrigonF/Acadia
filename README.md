# ACADIA — Academic Identity Authenticated (SIH 2026)
**Problem Statement ID:** SIH26263  
**Team:** Zenith_5 | **Team ID:** 199064  
**Platform:** APAAR ID-Based Student Data Management and Verification Platform for AICTE-Approved Institutions.

---

## 1. Project Overview & Architecture

ACADIA is an enterprise academic registry platform providing end-to-end student lifecycle management, cryptographically sealed record versioning, and privacy-preserving duplicate detection.

- **Backend Architecture**: Python 3.12, FastAPI, SQLAlchemy 2 ORM, Pydantic v2, Ed25519 Asymmetric Digital Signatures, Keyed HMAC-SHA256 privacy-preserving duplicate detection, AES-256-GCM field-level encryption at rest, and scikit-learn Isolation Forest anomaly alerts.
- **Frontend Architecture**: React 19, Tailwind CSS v4, Vite 8, TypeScript. Connects to backend REST APIs.
- **Live APAAR/DigiLocker Integration Notice**: In compliance with national data privacy standards and Ministry guidelines, live DigiLocker/APAAR API connectivity requires official governmental approval and bilateral credentials. The prototype implements a high-fidelity **Mock APAAR Adapter** with identical payloads, response schemas, and latency simulation.

---

## 2. Quickstart Instructions (Instant Local Run)

### One-Click Launch (Windows)
Double-click `run.bat` in the project root:
- Runs non-destructive database verification / initial seed.
- Launches FastAPI backend on `http://localhost:8000`.
- Launches Vite React frontend on `http://localhost:5173`.
- Automatically opens the browser.

---

### Manual Setup & Execution

#### Terminal 1: Backend Setup
```powershell
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Seed demonstration database (Safe & non-destructive by default)
python -m backend.scripts.generate_synthetic_data

# 3. Run complete automated regression test suite (30 passed)
python -m pytest backend/tests -v

# 4. Start backend API server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`

#### Terminal 2: Frontend Setup
```powershell
cd Frontend
pnpm install
pnpm dev
```
- Web Application: `http://localhost:5173`

---

## 3. Pre-configured Demonstration Accounts

| Role | Email | Password | Permissions Scope |
| :--- | :--- | :--- | :--- |
| **Platform Administrator** | `admin@acadia.gov.in` | `Admin@Acadia2026` | Full platform access, audit trail verification, institution management |
| **AICTE Central Verifier** | `verifier@aicte.gov.in` | `Verifier@Aicte2026` | Review intake alerts, approve records, cryptographic sealing |
| **Institution Admin (Delhi)** | `admin@diaet.edu.in` | `Delhi@Inst2026` | Delhi Institute data intake, student record modifications |
| **Institution Admin (Pune)** | `admin@mitr.ac.in` | `Pune@Inst2026` | Pune Institute data intake, student record modifications |
| **External Verifier** | `verifier@external-corp.com` | `Verify@External2026` | Restricted strictly to public QR verification (`/api/v1/qr/verify/{token}`) |

---

## 4. Cryptographic Security & Privacy Architecture

1. **Secret & Key Management**:
   - Environment-driven configuration via `.env` (derived from `.env.example`).
   - Production validation enforces fail-safe exit if weak or legacy default development keys are detected.
2. **Ed25519 Digital Signatures**:
   - Every sealed version carries an asymmetric Ed25519 signature of the canonical SHA-256 hash.
   - Verified strictly against a trusted in-memory public key registry (`TRUSTED_PUBLIC_KEYS`), neutralizing public-key injection attacks in database columns.
   - Any historical compromised development keys (`acadia-dev-key-2026-v1`) are marked revoked and immediately rejected.
3. **APAAR Privacy & AES-256-GCM Encryption**:
   - Raw 12-digit APAAR IDs are encrypted at rest using authenticated AES-256-GCM with unique random 96-bit nonces.
   - Raw APAAR IDs are omitted from general API responses and audit logs.
   - Key-version tagging (`enc:v1:...`, `enc:v2:...`) supports seamless encryption key rotation and historical retention via a managed keyring.
4. **Keyed HMAC-SHA256 Duplicate Detection**:
   - Uses a secret salt to compute irreversible hashes, preventing cross-institution dual enrollment without exposing plaintext IDs.
   - Migration utility (`migrate_student_identifiers`) supports zero-knowledge re-fingerprinting when rotating HMAC keys.
5. **Tamper-Evident Audit Trail**:
   - Audit entries are cryptographically chained using SHA-256 hash digests (`entry_hash = SHA256(content + previous_entry_hash)`).
   - Tampering or deletion of audit records is instantly detected via `/api/v1/audit/verify-chain/integrity`.

---

## 5. Automated Test Suite

Run the full automated test suite covering all 30 test scenarios:
```powershell
python -m pytest backend/tests -v
```
Test categories covered:
- Core E2E API workflows (`test_acadia_core.py`)
- Full student CRUD lifecycle & cryptographic integrity (`test_qa_lifecycle.py`)
- Role-based access control and tenant isolation (`test_qa_rbac.py`)
- Security remediation & APAAR privacy (`test_remediation_regression.py`)
- Key rotation, AES keyring, HMAC migration & audit hash chain (`test_key_rotation.py`)

---

## 6. Known Prototype Boundaries
- **DigiLocker Integration**: Real-world integration with DigiLocker and APAAR requires formal institutional empanelment and government API gateway tokens. ACADIA uses a compliant mock adapter.
- **Hardware Security Modules (HSM)**: In production deployments, Ed25519 private keys should be stored in cloud KMS or dedicated HSMs rather than filesystem environment variables.
