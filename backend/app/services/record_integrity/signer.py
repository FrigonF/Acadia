"""Ed25519 asymmetric digital signature and verification service with key registry management."""
import base64
from typing import Tuple, Dict, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from backend.app.core.config import settings

class DigitalSignatureService:
    def __init__(self):
        # Derive or load Ed25519 key from config
        seed_hex = settings.ED25519_PRIVATE_KEY_HEX
        if seed_hex and len(seed_hex) == 64:
            seed_bytes = bytes.fromhex(seed_hex)
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
        else:
            # Fallback to ephemeral generated key for test/dev
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            
        self._public_key = self._private_key.public_key()
        self.key_id = settings.KEY_ID
        
        # In-memory trusted public key registry (maps key_id -> PEM)
        self._trusted_keys: Dict[str, str] = dict(settings.TRUSTED_PUBLIC_KEYS or {})
        # Always register the current active public key in the trusted set
        self._trusted_keys[self.key_id] = self.get_public_key_pem()

    def get_public_key_pem(self) -> str:
        """Returns public key in standard OpenSSL PEM format."""
        pem_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode('utf-8')

    def register_trusted_key(self, key_id: str, public_key_pem: str):
        """Allows registering a known historical or external root public key."""
        self._trusted_keys[key_id] = public_key_pem

    def sign_fingerprint(self, fingerprint: str) -> str:
        """Signs a SHA-256 fingerprint hex string using Ed25519.
        Returns URL-safe Base64 encoded signature.
        """
        data = fingerprint.encode('utf-8')
        signature_bytes = self._private_key.sign(data)
        return base64.b64encode(signature_bytes).decode('utf-8')

    def verify_signature(
        self,
        fingerprint: str,
        signature_b64: str,
        key_id: Optional[str] = None,
        public_key_pem: Optional[str] = None
    ) -> bool:
        """Cryptographically verifies that the signature corresponds to the fingerprint.
        
        SECURITY REMEDIATION:
        Never trusts arbitrary public keys supplied by untrusted callers or unverified DB rows.
        Verifies against the platform's trusted public keys registry for that key_id.
        """
        try:
            signature_bytes = base64.b64decode(signature_b64)
            data = fingerprint.encode('utf-8')
            
            # Determine the trusted public key to use
            trusted_pem = None
            if key_id and key_id in self._trusted_keys:
                trusted_pem = self._trusted_keys[key_id]
            elif public_key_pem and not key_id:
                # If no key_id provided, only allow if the PEM matches our current active key
                if public_key_pem.strip() == self.get_public_key_pem().strip():
                    trusted_pem = public_key_pem
                else:
                    return False
            elif key_id:
                # Key ID was provided but is not recognized in trusted keys registry
                return False
            else:
                trusted_pem = self.get_public_key_pem()

            if not trusted_pem:
                return False
                
            pub_key = serialization.load_pem_public_key(trusted_pem.encode('utf-8'))
            pub_key.verify(signature_bytes, data)
            return True
        except Exception:
            return False

signature_service = DigitalSignatureService()
