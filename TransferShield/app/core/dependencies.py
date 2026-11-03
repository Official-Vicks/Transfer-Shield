"""Reusable FastAPI dependencies for authenticated requests."""

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import HTTPException, status,Depends
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core import settings
from app.db.session import get_db
from app.models import Merchant

bearer_scheme = HTTPBearer()

def get_current_merchant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Merchant:
    """Return the merchant represented by a valid JWT."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        merchant_id = payload.get("sub")

        if merchant_id is None:
            raise credentials_exception

        merchant_id = int(merchant_id)

    except (JWTError, ValueError):
        raise credentials_exception

    merchant = (
        db.query(Merchant)
        .filter(Merchant.id == merchant_id)
        .first()
    )

    if merchant is None:
        raise credentials_exception

    return merchant