"""Business Logic For Transfer Shield Payment Requests"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Payment
from datetime import datetime, timezone
from decimal import Decimal
from app.schemas import PaymentCreate
from uuid import uuid4
from app.services.paystack_provider import PaystackProvider, PaystackError

class PaymentService:
    """Handles Payment Request Creation And Related Business Rules"""

    def __init__(self, db: Session):
        self.db = db

    def create_payment(self, payment_data: PaymentCreate, merchant_id: int) -> Payment:
        """Create a pending payment request for a merchant."""

        # validate the amount
        if payment_data.amount <= Decimal("0"):
            raise ValueError("Payment amount must be greater than zero")
        
        # validate the optional exipry time
        expires_at = payment_data.expires_at

        if expires_at is not None:
            if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                raise ValueError("Expiration time must include a timezone")
            
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("Timezone must be in the future")
            
        # check whether this merchant already uses the reference
        existing_payment = (
            self.db.query(Payment)
            .filter(
                Payment.merchant_id == merchant_id,
                Payment.reference == payment_data.reference
            ).first()
        )
        
        if existing_payment:
            raise ValueError("Payment with this reference already exists")
        
        # construct payment
        payment = Payment(
            merchant_id=merchant_id,
            reference=payment_data.reference,
            amount=payment_data.amount,
            customer_email=payment_data.customer_email,
            currency=payment_data.currency,
            description=payment_data.description,
            expires_at=expires_at,
            status="PENDING"
        )

        # persist payment
        try:
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
        except IntegrityError as error:
            self.db.rollback()
            raise ValueError("A payment with this reference already exists") from error
        except Exception:
            self.db.rollback()
            raise
        return payment
    
    def get_payment_by_id_and_merchant(self, payment_id: int, merchant_id: int):
        """Retrieve payments belonging to authenticated merchant"""
        payment = (
            self.db.query(Payment)
            .filter(
                Payment.id == payment_id,
                Payment.merchant_id == merchant_id
            ).first()
        )
        return payment
    
    async def initialize_checkout(
        self,
        payment_id: int,
        merchant_id: int
    ) -> dict:
        """Initialize Paystack checkout for an eligible merchant payment."""

        payment = self.get_payment_by_id_and_merchant(payment_id, merchant_id)

        if payment is None:
            raise LookupError("Payment not found")
        
        if payment.status != "PENDING":
            raise ValueError("Only pending payments can be checked out")
        
        if payment.provider_reference is not None:
            raise ValueError("Checkout has already been initialized")
        
        if payment.expires_at is not None:
            expires_at = payment.expires_at

            # SQLite may return a naive datetime even when the column was declared with timezone=True.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            # should reject expired payments
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("Payment request has expired")
        
        # generate randon provider reference
        provider_reference = f"TS-{uuid4().hex}"
        provider = PaystackProvider()

        checkout = await provider.initialize_transaction(
            email=payment.customer_email,
            amount=payment.amount,
            currency=payment.currency,
            reference=provider_reference
        )

        # Persist the provider reference only after successful initialization.
        payment.provider_reference = checkout["reference"]
        
        try:
            self.db.commit()
            self.db.refresh(payment)
        except Exception:
            self.db.rollback()
            raise

        return {
            "payment_id": payment.id,
            "provider_reference": payment.provider_reference,
            "authorization_url": checkout["authorization_url"],
            "access_code": checkout.get("access_code"),
            "status": payment.status
        }