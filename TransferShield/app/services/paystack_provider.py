"""Paystack provider integration for TransferShield"""

from typing import Optional, Dict, Any
from decimal import Decimal
from app.core import settings
import httpx

PAYSTACK_BASE_URL = "https://api.paystack.co"

class PaystackError(Exception):
    """Raised when Paystack initialization fails"""

class PaystackProvider:
    """Client for initiating Paystack transactions"""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None
    ):
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY
        self.client = client
    
    async def initialize_transaction(
        self,
        email: str,
        amount: Decimal,
        currency: str,
        reference: str
    ) -> Dict[str, Any]:
        """Initialize a transaction and return Paystack checkout details."""
        if not self.secret_key:
            raise PaystackError("Paystack secret is not configured")
        
        if amount <= Decimal("0"):
            raise ValueError("Payment amount must be greater than zero")
        
        if not email.strip():
            raise ValueError("Customer email is required")
        
        #Transfershield stores payment amount in NGN, paystack expects kobo
        if currency.upper() != "NGN":
            raise ValueError("This integration currently supports NGN only")
        
        amount_in_kobo = amount * Decimal("100")

        if amount_in_kobo != amount_in_kobo.to_integral_value():
            raise ValueError("Payment amount cannot have fractions of a kobo")
        
        payload = {
            "email": email,
            "amount": str(int(amount_in_kobo)),
            "currency": currency.upper(),
            "reference": reference
        }

        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

        try:
            if self.client is not None:
                response = await self.client.post(
                    PAYSTACK_BASE_URL + "/transaction/initialize",
                    json=payload,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        PAYSTACK_BASE_URL + "/transaction/initialize",
                        json=payload,
                        headers=headers,
                    )
                
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as error:
            raise PaystackError(
                "Paystack rejected the transaction initialization request"
            ) from error
        except httpx.RequestError as error:
            raise PaystackError(
                "Could not connect to paystack"
            ) from error
        except ValueError as error:
            #includes malformed JSON responses
            raise PaystackError(
                "Paystack returned an invalid response"
            ) from error
        
        if not isinstance(result, dict) or result.get("status") is not True:
            raise PaystackError("Paystack could not initialize the transaction")
        
        data = result.get("data")

        if not isinstance(data, dict):
            raise PaystackError("Paystack response is missing transaction data")
        
        authorization_url = data.get("authorization_url")
        provider_reference = data.get("reference")

        if not authorization_url or not provider_reference:
            raise PaystackError("Paystack response is missing checkout details")
        
        return {
            "authorization_url": authorization_url,
            "access_code": data.get("access_code"),
            "reference": provider_reference
        }