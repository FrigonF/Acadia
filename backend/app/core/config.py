"""ACADIA Core Configuration."""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "ACADIA - Academic Identity Authenticated"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Security
    ENV: str = "development"
    SECRET_KEY: str = Field(default="acadia_dev_super_secret_jwt_key_sih26263_zenith_5_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for dev convenience
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./acadia_dev.db"  # Works out of the box, supports PostgreSQL via env
    )
    
    # Keyed HMAC Salt for Privacy-Preserving Identifier Fingerprinting
    # CRITICAL: Server-side secret key for HMAC-SHA256 duplicate detection
    HMAC_SECRET_KEY: str = Field(default="acadia_identifier_hmac_secret_key_salt_sih26263")
    
    # Ed25519 Digital Signing Keys (Base64/Hex/PEM or auto-generated in dev)
    # Dev private seed for Ed25519
    ED25519_PRIVATE_KEY_HEX: Optional[str] = Field(
        default="4a5c6d7e8f901234567890abcdef1234567890abcdef1234567890abcdef1234"
    )
    KEY_ID: str = "acadia-dev-key-2026-v1"
    
    # Mock APAAR Adapter Flag
    APAAR_MOCK_MODE: bool = True
    APAAR_API_BASE_URL: str = "https://mock.apaar.gov.in/api/v1"
    APAAR_CLIENT_ID: Optional[str] = "mock_acadia_client"
    APAAR_CLIENT_SECRET: Optional[str] = "mock_secret"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Public Base URL for verification links
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
