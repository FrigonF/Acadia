# ACADIA — Academic Identity Authenticated (SIH 2026)
**Problem Statement ID:** SIH26263  
**Team:** Zenith_5 | **Team ID:** 199064  
**Platform:** APAAR ID-Based Student Data Management and Verification Platform for AICTE-Approved Institutions.

---

## 1. Project Overview & Architecture

ACADIA is a full-stack platform consisting of:
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 ORM, Pydantic v2, SQLite/PostgreSQL, Ed25519 Cryptographic Signatures, Keyed HMAC-SHA256 privacy duplicate detection, scikit-learn Isolation Forest anomaly alerts.
- **Frontend**: React 19, Tailwind CSS v4, Vite 8, TypeScript. Integrates with the backend REST API.

---

## 2. Quickstart Instructions (Windows & Linux)

### Terminal 1: Backend Setup & Execution
```powershell
# 1. Install backend dependencies
python -m pip install -r requirements.txt

# 2. Seed database with synthetic demonstration data (5 institutions, users, intakes, 510+ students)
python -m backend.scripts.generate_synthetic_data

# 3. Run backend test suite (All 8 tests passing)
python -m pytest backend/tests/test_acadia_core.py -v

# 4. Start the FastAPI backend server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger UI docs: `http://localhost:8000/docs`

---

### Terminal 2: Frontend Setup & Execution
```powershell
# 1. Navigate to Frontend folder and install dependencies
cd Frontend
pnpm install

# 2. Start the Vite development server
pnpm dev
```
Open your browser at: `http://localhost:5173`

---

## 3. Pre-configured Demo Login Roles

| Role | Email | Password | Permissions Scope |
| :--- | :--- | :--- | :--- |
| **Platform Administrator** | `admin@acadia.gov.in` | `Admin@Acadia2026` | Full platform access, audits, institutions |
| **AICTE Central Verifier** | `verifier@aicte.gov.in` | `Verifier@Aicte2026` | Intake violations, record sealing, anomaly review |
| **Institution Admin (Delhi)** | `admin@diaet.edu.in` | `Delhi@Inst2026` | Delhi Institute data intake, student records |
| **Institution Admin (Pune)** | `admin@mitr.ac.in` | `Pune@Inst2026` | Pune Institute data intake, student records |
| **External Verifier** | `verifier@external-corp.com` | `Verify@External2026` | QR credential inspection |

---

## 4. End-to-End Workflow & Features Implemented

1. **Authentication & RBAC**: JWT Bearer token authentication with role-based routing and tenant isolation.
2. **Overview Dashboard**: Live statistics (total students, validated, duplicates, intake alerts) and interactive capacity chart.
3. **Institution Directory**: Real-time listing with AISHE codes, approved programmes, and CSV export.
4. **Student Directory**: Student records with privacy-preserving masked APAAR IDs (`XXXXXXXX9012`).
5. **Data Intake**: Drag-and-drop file ingestion supporting both `.csv` and `.xlsx` with format validation.
6. **Verification Queue**: Triage duplicate registrations, intake capacity breaches, and row-level issues with resolution notes.
7. **Record Integrity**: Canonical JSON hashing, Ed25519 digital signing, tamper detection, QR generation and public QR verification.
8. **Reports & Audit**: Centralized immutable audit logs capturing actors, timestamps, and action types.
