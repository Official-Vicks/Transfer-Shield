"""Database model for merchant payment requests."""

from datetime import datetime, timezone
from app.db import Base
from sqlalchemy import String, Integer, DateTime, ForeignKey, Numeric, UniqueConstraint
from decimal import Decimal
from sqlalchemy.orm import mapped_column, Mapped
from typing import Optional

class Payment(Base):
    """Represents an expected payment created by a merchant."""

    __tablename__ = "payments"
    
    __table_args__ = (
        UniqueConstraint(
            "merchant_id",
            "reference",
            name="uq_payment_merchant_reference",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)

    reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    customer_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)

    provider_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")

    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )