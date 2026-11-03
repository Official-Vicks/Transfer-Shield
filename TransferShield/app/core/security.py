"""Security utilities for password hashing and JWT authentication."""

from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from app.core import settings
from jose import jwt

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password using the configured password hashing algorithm."""
    return password_hash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored password hash."""
    return password_hash.verify(password, hashed_password)

def create_access_token(data: dict) -> str:
    '''Create a signed JWT access token'''

    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload.update({"exp": expire})

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )