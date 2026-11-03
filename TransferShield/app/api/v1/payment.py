"""API endpoints for merchants payment requests"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas import (
    PaymentCreate, PaymentResponse, PaymentCheckoutResponse
)
from app.models import Merchant, Payment
from app.core.dependencies import get_current_merchant
from decimal import Decimal
from app.services.payment_service import PaymentService
from app.services.paystack_provider import PaystackError

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: PaymentCreate,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db)
):
    """Create a payment request for the authenticated merchant"""
    payment_service = PaymentService(db)

    try:
        payment = payment_service.create_payment(payment_data, current_merchant.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    
    return payment

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db)
):
    """Retrieve payment belonging to an authenticated merchant"""
    payment_service = PaymentService(db)
    payment = payment_service.get_payment_by_id_and_merchant(payment_id, current_merchant.id)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    return payment

@router.post(
    "/{payment_id}/checkout",
    response_model=PaymentCheckoutResponse
)
async def initialize_payment_checkout(
    payment_id: int,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db)
):
    """Initialize Paystack checkout for a merchant's payment."""
    payment_service = PaymentService(db)

    try:
        return await payment_service.initialize_checkout(payment_id, current_merchant.id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )from error
    except PaystackError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error)
        )from error