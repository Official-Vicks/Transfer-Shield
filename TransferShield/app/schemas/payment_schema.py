from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
from decimal import Decimal
from typing import Optional

class PaymentCreate(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    currency: str = Field(default='NGN', min_length=3, max_length=3)
    customer_email: EmailStr
    description: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None

class PaymentResponse(BaseModel):
    id: int
    merchant_id: int
    reference: str
    customer_email: Optional[str] = None
    provider_reference: Optional[str] = None
    amount: Decimal
    currency: str
    description: Optional[str]
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaymentCheckoutResponse(BaseModel):
    payment_id: int
    provider_reference: str
    authorization_url: str
    access_code: Optional[str] = None
    status: str