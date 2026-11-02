"""ACADIA Core Configuration and Security Hardening."""
from typing import List, Optional, Dict
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
import json
import logging

logger = logging.getLogger("acadia.config")

# Known insecure legacy development keys that must NEVER be used in production
INSECURE_DEV_SECRETS = {
    "acadia_dev_super_secret_jwt_key_sih26263_zenith_5_2026",
    "acadia_prod_secret_key_sih2026",
    "secret",
    "changeme",
    "admin",
    "password"
}
INSECURE_DEV_HMAC = {
    "acadia_identifier_hmac_secret_key_salt_sih26263",
    "acadia_hmac_secret_key_sih2026",
    "salt"
}
INSECURE_DEV_ED25519 = {
    "4a5c6d7e8f901234567890abcdef1234567890abcdef1234567890abcdef1234"
}

class Settings(BaseSettings):
    PROJECT_NAME: str = "ACADIA - Academic Identity Authenticated"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Security
    ENV: str = "development"
    SECRET_KEY: str = Field(default="acadia_dev_super_secret_jwt_key_sih26263_zenith_5_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # Reduced default token lifetime from 24h to 2h
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./acadia_dev.db"
    )
    
    # Keyed HMAC Salt for Privacy-Preserving Identifier Fingerprinting
    HMAC_SECRET_KEY: str = Field(default="acadia_identifier_hmac_secret_key_salt_sih26263")
    
    # AES-256 GCM Key for Data-at-Rest Encryption of PII / Identifiers (64 hex characters)
    FIELD_ENCRYPTION_KEY: Optional[str] = Field(default=None)
    
    # Ed25519 Digital Signing Keys (Hex private seed)
    ED25519_PRIVATE_KEY_HEX: Optional[str] = Field(
        default="4a5c6d7e8f901234567890abcdef1234567890abcdef1234567890abcdef1234"
    )
    KEY_ID: str = "acadia-dev-key-2026-v1"
    
    # Trusted Public Keys registry for verification: dict mapping key_id -> PEM string
    TRUSTED_PUBLIC_KEYS: Dict[str, str] = Field(default_factory=dict)
    
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

    @model_validator(mode="after")
    def validate_production_security(self):
        is_production = self.ENV.strip().lower() in ("production", "prod")
        
        if is_production:
            if not self.SECRET_KEY or self.SECRET_KEY in INSECURE_DEV_SECRETS or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: Production environment requires a strong, unique SECRET_KEY "
                    "of at least 32 characters. Known development defaults are strictly forbidden."
                )
            if not self.HMAC_SECRET_KEY or self.HMAC_SECRET_KEY in INSECURE_DEV_HMAC or len(self.HMAC_SECRET_KEY) < 32:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: Production environment requires a strong HMAC_SECRET_KEY. "
                    "Known development defaults are strictly forbidden."
                )
            if not self.ED25519_PRIVATE_KEY_HEX or self.ED25519_PRIVATE_KEY_HEX in INSECURE_DEV_ED25519:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: Production environment requires a rotated, unique ED25519_PRIVATE_KEY_HEX. "
                    "Compromised development seeds are strictly forbidden."
                )
            if not self.FIELD_ENCRYPTION_KEY or len(self.FIELD_ENCRYPTION_KEY) != 64:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: Production environment requires FIELD_ENCRYPTION_KEY "
                    "with 64 hex characters (256-bit AES-GCM key) for identifier privacy at rest."
                )
        return self

settings = Settings()
