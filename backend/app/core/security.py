"""Security utilities: password hashing (direct bcrypt), JWT tokens, field encryption with key ring, and HMAC-SHA256 fingerprinting."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import hashlib
import hmac
import os
import base64
import bcrypt
from jose import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.app.core.config import settings

# In-memory dictionary of key_version -> AESGCM cipher
_CIPHERS: Dict[str, AESGCM] = {}

def _init_ciphers():
    global _CIPHERS
    _CIPHERS.clear()
    
    # 1. Primary active key from settings.FIELD_ENCRYPTION_KEY
    if settings.FIELD_ENCRYPTION_KEY and len(settings.FIELD_ENCRYPTION_KEY) == 64:
        key_bytes = bytes.fromhex(settings.FIELD_ENCRYPTION_KEY)
    else:
        key_bytes = hashlib.sha256(settings.HMAC_SECRET_KEY.encode('utf-8')).digest()
        
    active_ver = settings.ACTIVE_KEY_VERSION or "v1"
    _CIPHERS[active_ver] = AESGCM(key_bytes)
    
    # 2. Additional historical keys in settings.FIELD_KEYRING (e.g. {"v1": "hex...", "v2": "hex..."})
    if settings.FIELD_KEYRING:
        for ver, hex_key in settings.FIELD_KEYRING.items():
            if hex_key and len(hex_key) == 64:
                _CIPHERS[ver] = AESGCM(bytes.fromhex(hex_key))

def get_cipher(version: Optional[str] = None) -> AESGCM:
    if not _CIPHERS:
        _init_ciphers()
    ver = version or settings.ACTIVE_KEY_VERSION or "v1"
    if ver in _CIPHERS:
        return _CIPHERS[ver]
    # Fallback to active cipher
    return _CIPHERS[settings.ACTIVE_KEY_VERSION or "v1"]

def register_field_key(version: str, hex_key: str):
    """Dynamically register a historical or rotated key into the active keyring."""
    global _CIPHERS
    if len(hex_key) == 64:
        _CIPHERS[version] = AESGCM(bytes.fromhex(hex_key))

def encrypt_identifier(plain_id: Optional[str], key_version: Optional[str] = None) -> Optional[str]:
    """Encrypts an identifier using authenticated AES-256-GCM.
    Formats ciphertext with explicit key version header:
    e.g. "enc:v1:<base64(nonce + ciphertext + tag)>"
    """
    if not plain_id:
        return None
    ver = key_version or settings.ACTIVE_KEY_VERSION or "v1"
    cipher = get_cipher(ver)
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    data = plain_id.strip().encode('utf-8')
    ciphertext = cipher.encrypt(nonce, data, None)
    b64_payload = base64.b64encode(nonce + ciphertext).decode('utf-8')
    return f"enc:{ver}:{b64_payload}"

def decrypt_identifier(encrypted_id: Optional[str]) -> Optional[str]:
    """Decrypts an AES-256-GCM encrypted identifier string with version identification."""
    if not encrypted_id:
        return None
    try:
        raw_str = encrypted_id.strip()
        version = None
        b64_data = raw_str

        # Check versioned prefix e.g. "enc:v1:..."
        if raw_str.startswith("enc:"):
            parts = raw_str.split(":", 2)
            if len(parts) == 3:
                version = parts[1]
                b64_data = parts[2]

        cipher = get_cipher(version)
        raw_bytes = base64.b64decode(b64_data.encode('utf-8'))
        if len(raw_bytes) < 12:
            return None
        nonce = raw_bytes[:12]
        ciphertext = raw_bytes[12:]
        decrypted = cipher.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception:
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
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

def compute_hmac_fingerprint(identifier: str, secret_key: Optional[str] = None) -> str:
    """Compute keyed HMAC-SHA256 fingerprint of identifier for cross-institution duplicate detection.
    
    Protects privacy: Predictable 12-digit identifiers cannot be reversed or dictionary-attacked
    without the server-side HMAC secret key.
    """
    cleaned = str(identifier).strip()
    key = (secret_key or settings.HMAC_SECRET_KEY).encode("utf-8")
    return hmac.new(
        key,
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
