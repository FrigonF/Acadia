"""Institution management and intake endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models import Institution
from backend.app.models import ApprovedIntake
from backend.app.schemas import (
    InstitutionCreate, InstitutionUpdate, InstitutionResponse,
    IntakeCreate, IntakeResponse
)
from backend.app.core.permissions import get_current_user, require_roles, UserRole
from backend.app.services.reporting.audit_service import log_audit_event

router = APIRouter(prefix="/institutions", tags=["Institutions"])

@router.get("", response_model=List[InstitutionResponse])
def list_institutions(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    query = db.query(Institution)
    # If user is Institution Admin, restrict to their own institution
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id:
        query = query.filter(Institution.id == current_user.institution_id)
    elif status_filter:
        query = query.filter(Institution.status == status_filter)
        
    return query.offset(skip).limit(limit).all()

@router.post("", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: InstitutionCreate,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    existing = db.query(Institution).filter(Institution.aishe_code == payload.aishe_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Institution with AISHE code '{payload.aishe_code}' already exists.")

    inst = Institution(
        name=payload.name,
        aishe_code=payload.aishe_code,
        state=payload.state,
        district=payload.district,
        approved_programmes=payload.approved_programmes,
        reporting_contact=payload.reporting_contact
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)

    log_audit_event(
        db, action="CREATE_INSTITUTION", target_type="INSTITUTION", target_id=inst.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        new_state={"name": inst.name, "aishe_code": inst.aishe_code}
    )
    return inst

@router.get("/{id}", response_model=InstitutionResponse)
def get_institution(
    id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != id:
        raise HTTPException(status_code=403, detail="Access denied to other institutions.")
        
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst

@router.put("/{id}", response_model=InstitutionResponse)
def update_institution(
    id: str,
    payload: InstitutionUpdate,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    prev = {"name": inst.name, "status": inst.status}
    if payload.name is not None:
        inst.name = payload.name
    if payload.state is not None:
        inst.state = payload.state
    if payload.district is not None:
        inst.district = payload.district
    if payload.approved_programmes is not None:
        inst.approved_programmes = payload.approved_programmes
    if payload.reporting_contact is not None:
        inst.reporting_contact = payload.reporting_contact
    if payload.status is not None:
        inst.status = payload.status

    db.commit()
    db.refresh(inst)

    log_audit_event(
        db, action="UPDATE_INSTITUTION", target_type="INSTITUTION", target_id=inst.id,
        actor_id=current_user.id, actor_email=current_user.email, actor_role=current_user.role,
        previous_state=prev, new_state={"name": inst.name, "status": inst.status}
    )
    return inst

# --- Approved Intake Sub-endpoints ---
@router.post("/{id}/intake", response_model=IntakeResponse, status_code=status.HTTP_201_CREATED)
def set_approved_intake(
    id: str,
    payload: IntakeCreate,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER)),
    db: Session = Depends(get_db)
):
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    # Upsert intake
    existing = db.query(ApprovedIntake).filter(
        ApprovedIntake.institution_id == id,
        ApprovedIntake.programme == payload.programme,
        ApprovedIntake.academic_year == payload.academic_year
    ).first()

    if existing:
        existing.approved_intake = payload.approved_intake
        existing.approved_supernumerary = payload.approved_supernumerary
        existing.nri_seats = payload.nri_seats
        existing.oci_seats = payload.oci_seats
        existing.fn_seats = payload.fn_seats
        existing.other_categories = payload.other_categories
        intake_obj = existing
    else:
        intake_obj = ApprovedIntake(
            institution_id=id,
            programme=payload.programme,
            academic_year=payload.academic_year,
            approved_intake=payload.approved_intake,
            approved_supernumerary=payload.approved_supernumerary,
            nri_seats=payload.nri_seats,
            oci_seats=payload.oci_seats,
            fn_seats=payload.fn_seats,
            other_categories=payload.other_categories
        )
        db.add(intake_obj)

    db.commit()
    db.refresh(intake_obj)
    return intake_obj

@router.get("/{id}/intake", response_model=List[IntakeResponse])
def get_institution_intakes(
    id: str,
    current_user = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.AICTE_VERIFIER, UserRole.INSTITUTION_ADMIN)),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.INSTITUTION_ADMIN.value and current_user.institution_id != id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return db.query(ApprovedIntake).filter(ApprovedIntake.institution_id == id).all()
