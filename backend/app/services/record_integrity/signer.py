"""Ed25519 asymmetric digital signature and verification service."""
import base64
from typing import Tuple
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

    def get_public_key_pem(self) -> str:
        """Returns public key in standard OpenSSL PEM format."""
        pem_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode('utf-8')

    def sign_fingerprint(self, fingerprint: str) -> str:
        """Signs a SHA-256 fingerprint hex string using Ed25519.
        Returns URL-safe Base64 encoded signature.
        """
        data = fingerprint.encode('utf-8')
        signature_bytes = self._private_key.sign(data)
        return base64.b64encode(signature_bytes).decode('utf-8')

    def verify_signature(self, fingerprint: str, signature_b64: str, public_key_pem: str = None) -> bool:
        """Cryptographically verifies that the signature corresponds to the fingerprint."""
        try:
            signature_bytes = base64.b64decode(signature_b64)
            data = fingerprint.encode('utf-8')
            
            if public_key_pem:
                pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
            else:
                pub_key = self._public_key
                
            pub_key.verify(signature_bytes, data)
            return True
        except Exception:
            return False

signature_service = DigitalSignatureService()
