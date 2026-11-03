"""Business logic for TransferShield authentication and merchant accounts."""

from sqlalchemy.orm import Session
from app.models import Merchant
from app.schemas import MerchantCreate
from app.core import (
    create_access_token, hash_password, verify_password
    )


class AuthService:
    '''This method handles all authentication logic'''

    def __init__(self, db: Session):
        self.db = db

    def register_merchant(self, merchant_data: MerchantCreate) -> Merchant:
        existing_merchant = (
            self.db.query(Merchant).filter(Merchant.email == merchant_data.email).first()
            )

        if existing_merchant:
            raise ValueError("A merchant with this email already exists")
        
        hashed_password = hash_password(merchant_data.password)

        # Create a new merchant object
        merchant = Merchant(
            business_name=merchant_data.business_name,
            email=merchant_data.email,
            password_hash=hashed_password
        )

        try:
            self.db.add(merchant)
            self.db.commit()
            self.db.refresh(merchant)
        except Exception:
            self.db.rollback()
            raise
            
        return merchant

    def login_merchant(self, email: str, password: str) -> str:
        """Authenticate a merchant and return an access token."""

        merchant = self.db.query(Merchant).filter(Merchant.email == email).first()

        if not merchant:
            raise ValueError("Invalid email or password")
        
        if not verify_password(password, merchant.password_hash):
            raise ValueError("Invalid email or password")
        
        access_token = create_access_token(
            {"sub": str(merchant.id)}
            )
        
        return access_token