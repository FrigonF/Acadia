"""Synthetic Data Generator for ACADIA (SIH26263).

Generates:
- 5 Synthetic AICTE-Approved Institutions.
- Standard default user accounts for every role.
- Approved intake capacity across multiple programmes and categories.
- 500+ Synthetic student records with realistic scenarios:
  * Valid records
  * APAAR format violations (< 12 digits, non-numeric)
  * Missing mandatory fields (name, programme, academic year)
  * Within-institution duplicates
  * Cross-institution dual enrollment duplicates
  * Excess intake violations (main intake, NRI quota)
  * Unapproved programme cases

NOTE: All identities, names, and identifiers are strictly synthetic demonstration data.
"""
import random
import csv
import io
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, Base, engine
import sys
import argparse
from backend.app.core.security import get_password_hash, compute_hmac_fingerprint, mask_apaar_id, encrypt_identifier
from backend.app.core.permissions import UserRole
from backend.app.models import (
    User, Institution, Student, ApprovedIntake, UploadBatch, ValidationIssue
)

SYNTHETIC_INSTITUTIONS = [
    {
        "name": "Delhi Institute of Advanced Engineering & Technology",
        "aishe_code": "C-11001",
        "state": "Delhi",
        "district": "New Delhi",
        "approved_programmes": [
            "B.Tech Computer Science and Engineering",
            "B.Tech Electronics and Communication Engineering",
            "B.Tech Mechanical Engineering",
            "M.Tech Artificial Intelligence"
        ],
        "reporting_contact": {"email": "admin@diaet.edu.in", "phone": "+91-11-23456781"}
    },
    {
        "name": "Maharashtra Institute of Technology & Research",
        "aishe_code": "C-22002",
        "state": "Maharashtra",
        "district": "Pune",
        "approved_programmes": [
            "B.Tech Computer Science and Engineering",
            "B.Tech Information Technology",
            "B.Tech Civil Engineering"
        ],
        "reporting_contact": {"email": "registrar@mitr.ac.in", "phone": "+91-20-87654321"}
    },
    {
        "name": "Karnataka Technological Academy",
        "aishe_code": "C-33003",
        "state": "Karnataka",
        "district": "Bengaluru",
        "approved_programmes": [
            "B.Tech Computer Science and Engineering",
            "B.Tech Data Science",
            "B.Tech Electrical Engineering"
        ],
        "reporting_contact": {"email": "office@kta.edu.in", "phone": "+91-80-55443322"}
    },
    {
        "name": "Tamil Nadu College of Engineering & Applied Sciences",
        "aishe_code": "C-44004",
        "state": "Tamil Nadu",
        "district": "Chennai",
        "approved_programmes": [
            "B.Tech Computer Science and Engineering",
            "B.Tech Mechanical Engineering",
            "B.Tech Chemical Engineering"
        ],
        "reporting_contact": {"email": "dean@tnceas.edu.in", "phone": "+91-44-33221100"}
    },
    {
        "name": "Telangana State Institute of Science & Technology",
        "aishe_code": "C-55005",
        "state": "Telangana",
        "district": "Hyderabad",
        "approved_programmes": [
            "B.Tech Computer Science and Engineering",
            "B.Tech Artificial Intelligence & Machine Learning",
            "B.Tech Cyber Security"
        ],
        "reporting_contact": {"email": "admin@tsist.edu.in", "phone": "+91-40-77889900"}
    }
]

FIRST_NAMES = ["Aarav", "Aditi", "Ananya", "Arjun", "Deepak", "Diya", "Ishan", "Kavya", "Manish", "Neha", "Pranav", "Pooja", "Rahul", "Rhea", "Rohan", "Sanya", "Siddharth", "Sneha", "Tanvi", "Varun", "Vikram", "Yash", "Lakshmi", "Rakesh", "Gaurav"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Patel", "Reddy", "Nair", "Rao", "Iyer", "Kumar", "Singh", "Das", "Joshi", "Bose", "Mehta", "Chopra", "Kulkarni", "Deshmukh", "Pillai", "Menon", "Bhat"]

def generate_synthetic_data(force_reset: bool = False):
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    existing_students = db.query(Student).count()
    if existing_students > 0 and not force_reset:
        print(f"Database already populated ({existing_students} existing student records found).")
        print("Skipping non-destructive seed to protect existing data and credentials.")
        print("To perform an explicit reset, run: python -m backend.scripts.generate_synthetic_data --reset")
        db.close()
        return

    if force_reset:
        print("--- 1. EXPLICIT RESET REQUESTED: Purging existing demonstration tables ---")
        db.query(ValidationIssue).delete()
        db.query(Student).delete()
        db.query(UploadBatch).delete()
        db.query(ApprovedIntake).delete()
        db.query(User).delete()
        db.query(Institution).delete()
        db.commit()
    else:
        print("--- 1. Initializing clean demonstration database ---")

    print("--- 2. Creating Synthetic Institutions ---")
    inst_objs = []
    for inst_data in SYNTHETIC_INSTITUTIONS:
        inst = Institution(**inst_data)
        db.add(inst)
        inst_objs.append(inst)
    db.commit()

    print("--- 3. Creating Default User Accounts ---")
    default_users = [
        # Platform Admin
        User(
            name="Central Platform Administrator",
            email="admin@acadia.gov.in",
            hashed_password=get_password_hash("Admin@Acadia2026"),
            role=UserRole.PLATFORM_ADMIN.value,
            institution_id=None
        ),
        # AICTE Verifier
        User(
            name="Dr. S. K. Raman (AICTE Central Verifier)",
            email="verifier@aicte.gov.in",
            hashed_password=get_password_hash("Verifier@Aicte2026"),
            role=UserRole.AICTE_VERIFIER.value,
            institution_id=None
        ),
        # Institution Admin 1 (Delhi)
        User(
            name="Delhi Institute Admin",
            email="admin@diaet.edu.in",
            hashed_password=get_password_hash("Delhi@Inst2026"),
            role=UserRole.INSTITUTION_ADMIN.value,
            institution_id=inst_objs[0].id
        ),
        # Institution Admin 2 (Pune)
        User(
            name="Pune Institute Admin",
            email="admin@mitr.ac.in",
            hashed_password=get_password_hash("Pune@Inst2026"),
            role=UserRole.INSTITUTION_ADMIN.value,
            institution_id=inst_objs[1].id
        ),
        # Authorized External Verifier (Employer / Background Verifier)
        User(
            name="TCS Campus Verification Desk",
            email="verifier@external-corp.com",
            hashed_password=get_password_hash("Verify@External2026"),
            role=UserRole.AUTHORIZED_EXTERNAL_VERIFIER.value,
            institution_id=None
        )
    ]
    db.add_all(default_users)
    db.commit()

    print("--- 4. Setting Approved Intakes ---")
    for inst in inst_objs:
        for prog in inst.approved_programmes:
            intake = ApprovedIntake(
                institution_id=inst.id,
                programme=prog,
                academic_year="2025-2026",
                approved_intake=60,  # 60 seats standard capacity
                approved_supernumerary=6, # 10% TFWS
                nri_seats=3,
                oci_seats=2,
                fn_seats=2,
                other_categories={"EWS": 6}
            )
            db.add(intake)
    db.commit()

    print("--- 5. Generating 500+ Synthetic Student Records ---")
    # Dedicated cross-institution duplicate APAAR IDs
    shared_apaar_1 = "987654321001"
    shared_apaar_2 = "987654321002"
    shared_apaar_3 = "987654321003"

    students_to_add = []
    
    # Institution 1: Delhi (120 students)
    # Intake is 60 for CSE; we will enroll 65 to intentionally trigger an INTAKE EXCEED alert
    for i in range(1, 121):
        prog = "B.Tech Computer Science and Engineering" if i <= 65 else "B.Tech Electronics and Communication Engineering"
        apaar = f"1100{i:08d}"
        cat = "GENERAL"
        if i == 1:
            apaar = shared_apaar_1 # Cross-institution match with Inst 2
        elif i == 2:
            apaar = "12345" # Invalid format (< 12 digits)
        elif i == 3:
            apaar = "" # Missing APAAR
        elif i == 4 or i == 5:
            apaar = "110000000004" # Within-institution duplicate

        if i % 15 == 0:
            cat = "NRI"

        s = Student(
            institution_id=inst_objs[0].id,
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            apaar_id=encrypt_identifier(apaar),
            apaar_masked=mask_apaar_id(apaar) if apaar else "N/A",
            apaar_fingerprint=compute_hmac_fingerprint(apaar) if apaar else "UNASSIGNED",
            programme=prog,
            academic_year="2025-2026",
            seat_category=cat,
            enrollment_number=f"DIAET/2025/{i:04d}",
            record_status="VALIDATED" if len(apaar) == 12 and i not in [1, 4, 5] else "FLAGGED",
            is_duplicate=(i in [1, 4, 5]),
            duplicate_type="CROSS_INSTITUTION" if i == 1 else ("WITHIN_INSTITUTION" if i in [4, 5] else None)
        )
        students_to_add.append(s)

    # Institution 2: Maharashtra (110 students)
    for i in range(1, 111):
        apaar = f"2200{i:08d}"
        if i == 1:
            apaar = shared_apaar_1 # Cross-institution match with Inst 1
        elif i == 2:
            apaar = shared_apaar_2 # Cross-institution match with Inst 3
            
        s = Student(
            institution_id=inst_objs[1].id,
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            apaar_id=encrypt_identifier(apaar),
            apaar_masked=mask_apaar_id(apaar),
            apaar_fingerprint=compute_hmac_fingerprint(apaar),
            programme="B.Tech Computer Science and Engineering",
            academic_year="2025-2026",
            seat_category="GENERAL" if i > 5 else "OBC",
            enrollment_number=f"MITR/2025/{i:04d}",
            record_status="VALIDATED" if i not in [1, 2] else "FLAGGED",
            is_duplicate=(i in [1, 2]),
            duplicate_type="CROSS_INSTITUTION" if i in [1, 2] else None
        )
        students_to_add.append(s)

    # Institution 3: Karnataka (100 students)
    for i in range(1, 101):
        apaar = f"3300{i:08d}"
        if i == 1:
            apaar = shared_apaar_2 # Cross-institution duplicate with Inst 2
        s = Student(
            institution_id=inst_objs[2].id,
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            apaar_id=encrypt_identifier(apaar),
            apaar_masked=mask_apaar_id(apaar),
            apaar_fingerprint=compute_hmac_fingerprint(apaar),
            programme="B.Tech Computer Science and Engineering" if i <= 50 else "B.Tech Data Science",
            academic_year="2025-2026",
            seat_category="GENERAL",
            enrollment_number=f"KTA/2025/{i:04d}",
            record_status="VALIDATED" if i != 1 else "FLAGGED",
            is_duplicate=(i == 1),
            duplicate_type="CROSS_INSTITUTION" if i == 1 else None
        )
        students_to_add.append(s)

    # Institution 4: Tamil Nadu (90 students)
    for i in range(1, 91):
        apaar = f"4400{i:08d}"
        s = Student(
            institution_id=inst_objs[3].id,
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            apaar_id=encrypt_identifier(apaar),
            apaar_masked=mask_apaar_id(apaar),
            apaar_fingerprint=compute_hmac_fingerprint(apaar),
            programme="B.Tech Computer Science and Engineering" if i <= 45 else "B.Tech Mechanical Engineering",
            academic_year="2025-2026",
            seat_category="GENERAL" if i > 10 else "SC",
            enrollment_number=f"TNCEAS/2025/{i:04d}",
            record_status="VALIDATED"
        )
        students_to_add.append(s)

    # Institution 5: Telangana (90 students)
    for i in range(1, 91):
        apaar = f"5500{i:08d}"
        s = Student(
            institution_id=inst_objs[4].id,
            name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            apaar_id=encrypt_identifier(apaar),
            apaar_masked=mask_apaar_id(apaar),
            apaar_fingerprint=compute_hmac_fingerprint(apaar),
            programme="B.Tech Artificial Intelligence & Machine Learning",
            academic_year="2025-2026",
            seat_category="GENERAL",
            enrollment_number=f"TSIST/2025/{i:04d}",
            record_status="VALIDATED"
        )
        students_to_add.append(s)

    db.add_all(students_to_add)
    db.commit()

    total_count = db.query(Student).count()
    print(f"Successfully generated {total_count} synthetic student records across 5 institutions.")

    # Generate a sample CSV file for testing batch upload
    sample_csv_path = "backend/sample_data/sample_student_batch.csv"
    with open(sample_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_name", "apaar_id", "programme", "academic_year", "seat_category", "enrollment_number"])
        writer.writerow(["Rohan Verma", "880012345678", "B.Tech Computer Science and Engineering", "2025-2026", "GENERAL", "EN-8801"])
        writer.writerow(["Pooja Nair", "880012345679", "B.Tech Computer Science and Engineering", "2025-2026", "OBC", "EN-8802"])
        writer.writerow(["Aarav Singh", "12345", "B.Tech Computer Science and Engineering", "2025-2026", "GENERAL", "EN-8803"]) # Bad APAAR
        writer.writerow(["Kavya Iyer", "880012345678", "B.Tech Computer Science and Engineering", "2025-2026", "GENERAL", "EN-8804"]) # Duplicate in batch
        writer.writerow(["", "880099999999", "B.Tech Computer Science and Engineering", "2025-2026", "GENERAL", "EN-8805"]) # Missing name
        writer.writerow(["Vikas Reddy", "880011223344", "Unapproved Aeronautical Studies", "2025-2026", "GENERAL", "EN-8806"]) # Unapproved programme

    print(f"Created sample batch CSV file at: {sample_csv_path}")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACADIA Demonstration Data Seeder")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Explicit confirmation flag to wipe and rebuild database tables"
    )
    args = parser.parse_args()
    generate_synthetic_data(force_reset=args.reset)
