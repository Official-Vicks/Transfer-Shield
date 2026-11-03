'''Authentication API routes for Transfer Shield'''

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services import AuthService
from app.db.session import get_db
from app.core.dependencies import get_current_merchant
from app.models import Merchant
from app.schemas import (
    MerchantCreate, MerchantResponse, MerchantLogin, TokenResponse
    )

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.get(
    "/me",
    response_model=MerchantResponse
    )
def get_my_profile(
    current_merchant: Merchant = Depends(get_current_merchant)
):
    """Return the currently authenticated merchant."""
    return current_merchant

@router.post(
    "/register", 
    response_model=MerchantResponse, 
    status_code=status.HTTP_201_CREATED
    )
def register_merchant(
    merchant_data: MerchantCreate,
    db: Session = Depends(get_db)
):
    '''Register a new merchant account'''
    auth_service = AuthService(db)

    try:
        merchant = auth_service.register_merchant(merchant_data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )
    
    return merchant

@router.post(
    "/login",
    response_model=TokenResponse
)
def login_merchant(
    merchant_data: MerchantLogin,
    db: Session = Depends(get_db)
):
    """Authenticate a merchant and return an access token."""
    auth_service = AuthService(db)

    try:
        access_token = auth_service.login_merchant(
            merchant_data.email,
            merchant_data.password
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error)
        )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
