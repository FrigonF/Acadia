"""Security utilities: password hashing (direct bcrypt), JWT tokens, field encryption, and HMAC-SHA256 fingerprinting."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import hashlib
import hmac
import os
import base64
import bcrypt
from jose import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.app.core.config import settings

# In-memory derived AES-GCM cipher for field-level encryption at rest
_CIPHER: Optional[AESGCM] = None

def _get_aesgcm() -> AESGCM:
    global _CIPHER
    if _CIPHER is not None:
        return _CIPHER
    
    # Obtain or derive a 256-bit key
    if settings.FIELD_ENCRYPTION_KEY and len(settings.FIELD_ENCRYPTION_KEY) == 64:
        key_bytes = bytes.fromhex(settings.FIELD_ENCRYPTION_KEY)
    else:
        # Fallback to key derived from HMAC_SECRET_KEY in non-prod
        key_bytes = hashlib.sha256(settings.HMAC_SECRET_KEY.encode('utf-8')).digest()
        
    _CIPHER = AESGCM(key_bytes)
    return _CIPHER

def encrypt_identifier(plain_id: Optional[str]) -> Optional[str]:
    """Encrypts an identifier (such as raw APAAR ID) using authenticated AES-256-GCM.
    Returns Base64 encoded (nonce + ciphertext + tag).
    """
    if not plain_id:
        return None
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    data = plain_id.strip().encode('utf-8')
    ciphertext = _get_aesgcm().encrypt(nonce, data, None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_identifier(encrypted_id: Optional[str]) -> Optional[str]:
    """Decrypts an AES-256-GCM encrypted identifier string."""
    if not encrypted_id:
        return None
    try:
        raw_bytes = base64.b64decode(encrypted_id.encode('utf-8'))
        if len(raw_bytes) < 12:
            return None
        nonce = raw_bytes[:12]
        ciphertext = raw_bytes[12:]
        decrypted = _get_aesgcm().decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception:
        # Return None or unencrypted fallback if legacy record was plain
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # Truncate to 72 bytes if necessary to adhere strictly to bcrypt spec
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception:
        return None

def compute_hmac_fingerprint(identifier: str) -> str:
    """Compute keyed HMAC-SHA256 fingerprint of identifier for cross-institution duplicate detection.
    
    Protects privacy: Predictable 12-digit identifiers cannot be reversed or dictionary-attacked
    without the server-side HMAC secret key.
    """
    cleaned = str(identifier).strip()
    return hmac.new(
        settings.HMAC_SECRET_KEY.encode("utf-8"),
        cleaned.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def mask_apaar_id(apaar_id: Optional[str]) -> str:
    """Mask APAAR ID for safe display in logs and responses.
    
    e.g., '123456789012' -> 'XXXXXXXX9012'
    """
    if not apaar_id:
        return "N/A"
    clean = str(apaar_id).strip()
    if len(clean) >= 4:
        return "X" * (len(clean) - 4) + clean[-4:]
    return "XXXX"
