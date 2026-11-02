"""Role definitions and permission dependencies."""
from enum import Enum
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

class UserRole(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    AICTE_VERIFIER = "AICTE_VERIFIER"
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    AUTHORIZED_EXTERNAL_VERIFIER = "AUTHORIZED_EXTERNAL_VERIFIER"

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Lazy import to avoid circular dependencies
    from backend.app.models import User
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def require_roles(*allowed_roles: UserRole):
    def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' does not have sufficient permissions."
            )
        return current_user
    return role_checker
