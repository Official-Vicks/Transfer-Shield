from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class MerchantCreate(BaseModel):
    business_name: str
    email: EmailStr
    password: str


class MerchantResponse(BaseModel):
    id: int
    business_name: str
    email: EmailStr
    status: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MerchantLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str