from datetime import datetime, timedelta, timezone
from decimal import Decimal

import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Merchant, Payment
from app.schemas import PaymentCreate
from app.services.payment_service import PaymentService
from app.services.paystack_provider import PaystackError


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def merchant(db):
    test_merchant = Merchant(
        business_name="Test Business",
        email="merchant@example.com",
        password_hash="test-password-hash",
    )
    db.add(test_merchant)
    db.commit()
    db.refresh(test_merchant)

    return test_merchant


def test_create_payment_successfully(db, merchant):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-1001",
        amount=Decimal("2500.00"),
        currency="NGN",
        customer_email="customer@example.com",
        description="Test order",
    )

    payment = service.create_payment(
        payment_data,
        merchant.id,
    )

    assert payment.id is not None
    assert payment.merchant_id == merchant.id
    assert payment.reference == "ORD-1001"
    assert payment.amount == Decimal("2500.00")
    assert payment.status == "PENDING"


def test_duplicate_reference_is_rejected(db, merchant):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-1002",
        customer_email="customer@example.com",
        amount=Decimal("1000.00"),
    )

    service.create_payment(payment_data, merchant.id)

    with pytest.raises(
        ValueError,
        match="reference already exists",
    ):
        service.create_payment(payment_data, merchant.id)


def test_expiration_must_be_in_the_future(db, merchant):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-1003",
        amount=Decimal("1000.00"),
        customer_email="customer@example.com",
        expires_at=datetime.now(timezone.utc)
        - timedelta(minutes=5),
    )

    with pytest.raises(
        ValueError,
        match="must be in the future",
    ):
        service.create_payment(payment_data, merchant.id)


def test_expiration_requires_timezone(db, merchant):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-1004",
        amount=Decimal("1000.00"),
        customer_email="customer@example.com",
        expires_at=datetime.now() + timedelta(hours=1),
    )

    with pytest.raises(
        ValueError,
        match="must include a timezone",
    ):
        service.create_payment(payment_data, merchant.id)


def test_initialize_checkout_successfully(db, merchant, monkeypatch):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-CHECKOUT-001",
        amount=Decimal("2500.00"),
        currency="NGN",
        customer_email="customer@example.com",
    )
    payment = service.create_payment(payment_data, merchant.id)

    async def fake_initialize(self, email, amount, currency, reference):
        assert email == "customer@example.com"
        assert amount == Decimal("2500.00")
        assert currency == "NGN"
        assert reference.startswith("TS-")

        return {
            "authorization_url": "https://checkout.example.com/pay",
            "access_code": "test-access-code",
            "reference": reference,
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaystackProvider.initialize_transaction",
        fake_initialize,
    )

    result = asyncio.run(
        service.initialize_checkout(payment.id, merchant.id)
    )

    db.refresh(payment)

    assert result["payment_id"] == payment.id
    assert result["authorization_url"] == (
        "https://checkout.example.com/pay"
    )
    assert result["access_code"] == "test-access-code"
    assert result["status"] == "PENDING"
    assert payment.provider_reference == result["provider_reference"]
    assert payment.provider_reference.startswith("TS-")
    assert payment.status == "PENDING"


def test_checkout_rejects_missing_payment(db, merchant):
    service = PaymentService(db)

    with pytest.raises(LookupError, match="Payment not found"):
        asyncio.run(
            service.initialize_checkout(99999, merchant.id)
        )


def test_checkout_rejects_expired_payment(db, merchant):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-CHECKOUT-EXPIRED",
        amount=Decimal("1000.00"),
        customer_email="customer@example.com",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    payment = service.create_payment(payment_data, merchant.id)

    payment.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    with pytest.raises(ValueError, match="expired"):
        asyncio.run(
            service.initialize_checkout(payment.id, merchant.id)
        )


def test_checkout_provider_failure_does_not_mark_payment_successful(
    db, merchant, monkeypatch
):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-CHECKOUT-FAIL",
        amount=Decimal("1000.00"),
        customer_email="customer@example.com",
    )
    payment = service.create_payment(payment_data, merchant.id)

    async def fake_initialize(self, email, amount, currency, reference):
        raise PaystackError("Simulated provider failure")

    monkeypatch.setattr(
        "app.services.payment_service.PaystackProvider.initialize_transaction",
        fake_initialize,
    )

    with pytest.raises(PaystackError):
        asyncio.run(
            service.initialize_checkout(payment.id, merchant.id)
        )

    db.refresh(payment)

    assert payment.status == "PENDING"
    assert payment.provider_reference is None


def test_checkout_cannot_be_initialized_twice(db, merchant, monkeypatch):
    service = PaymentService(db)

    payment_data = PaymentCreate(
        reference="ORD-CHECKOUT-REPEAT",
        amount=Decimal("1000.00"),
        customer_email="customer@example.com",
    )
    payment = service.create_payment(payment_data, merchant.id)
    call_count = {"value": 0}

    async def fake_initialize(self, email, amount, currency, reference):
        call_count["value"] += 1
        return {
            "authorization_url": "https://checkout.example.com/pay",
            "access_code": "test-access-code",
            "reference": reference,
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaystackProvider.initialize_transaction",
        fake_initialize,
    )

    asyncio.run(service.initialize_checkout(payment.id, merchant.id))

    with pytest.raises(ValueError, match="already been initialized"):
        asyncio.run(service.initialize_checkout(payment.id, merchant.id))

    assert call_count["value"] == 1