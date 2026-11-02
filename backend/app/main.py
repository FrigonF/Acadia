"""ACADIA FastAPI Application Entry Point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import Base, engine
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.institutions import router as institutions_router
from backend.app.api.v1.students import router as students_router
from backend.app.api.v1.uploads import router as uploads_router
from backend.app.api.v1.validation import router as validation_router
from backend.app.api.v1.verification import router as verification_router
from backend.app.api.v1.integrity import router as integrity_router
from backend.app.api.v1.qr import router as qr_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.audit import router as audit_router

# Initialize all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="ACADIA: APAAR ID-Based Student Data Management and Verification Platform for AICTE-Approved Institutions (SIH26263)."
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(institutions_router, prefix=settings.API_V1_STR)
app.include_router(students_router, prefix=settings.API_V1_STR)
app.include_router(uploads_router, prefix=settings.API_V1_STR)
app.include_router(validation_router, prefix=settings.API_V1_STR)
app.include_router(verification_router, prefix=settings.API_V1_STR)
app.include_router(integrity_router, prefix=settings.API_V1_STR)
app.include_router(qr_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "database": "CONNECTED",
        "mock_apaar_mode": settings.APAAR_MOCK_MODE
    }

@app.get("/", tags=["System"])
def root():
    return {
        "message": "Welcome to ACADIA Core Engine API",
        "docs": "/docs",
        "problem_statement": "SIH26263",
        "team": "Zenith_5 (199064)"
    }
