"""Database model for individual merchants"""

from app.db import Base
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, index=True, primary_key=True)

    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    
    email: Mapped[str] = mapped_column(String(255), index=True, unique=True, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )