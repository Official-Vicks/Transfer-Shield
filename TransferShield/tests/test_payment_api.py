"""API tests for TransferShield payment endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_merchant
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Merchant
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
def api_setup():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    merchant_a = Merchant(
        business_name="Merchant A",
        email="merchant_a@example.com",
        password_hash="test-hash-a",
    )
    merchant_b = Merchant(
        business_name="Merchant B",
        email="merchant_b@example.com",
        password_hash="test-hash-b",
    )

    db.add_all([merchant_a, merchant_b])
    db.commit()
    db.refresh(merchant_a)
    db.refresh(merchant_b)

    current_merchant_id = {"value": merchant_a.id}

    def override_get_db():
        yield db

    def override_current_merchant():
        return db.query(Merchant).filter(
            Merchant.id == current_merchant_id["value"]
        ).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_merchant] = (
        override_current_merchant
    )

    client = TestClient(app)

    try:
        yield client, db, merchant_a, merchant_b, current_merchant_id
    finally:
        app.dependency_overrides.clear()
        client.close()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_payment_successfully(api_setup):
    client, _, merchant_a, _, _ = api_setup

    response = client.post(
        "/api/v1/payments",
        json={
            "reference": "ORD-API-001",
            "amount": "2500.00",
            "currency": "NGN",
            "customer_email": "customer@example.com",
            "description": "Test order",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["merchant_id"] == merchant_a.id
    assert data["reference"] == "ORD-API-001"
    assert data["customer_email"] == "customer@example.com"
    assert Decimal(data["amount"]) == Decimal("2500.00")
    assert data["status"] == "PENDING"


def test_duplicate_reference_is_rejected(api_setup):
    client, _, _, _, _ = api_setup

    payload = {
        "reference": "ORD-API-002",
        "amount": "1000.00",
        "currency": "NGN",
        "customer_email": "customer@example.com",
    }

    first_response = client.post("/api/v1/payments", json=payload)
    second_response = client.post("/api/v1/payments", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_same_reference_allowed_for_different_merchants(api_setup):
    client, _, _, merchant_b, current_merchant_id = api_setup

    payload = {
        "reference": "SHARED-ORDER-001",
        "amount": "1000.00",
        "currency": "NGN",
        "customer_email": "customer@example.com",
    }

    first_response = client.post("/api/v1/payments", json=payload)
    assert first_response.status_code == 201

    current_merchant_id["value"] = merchant_b.id

    second_response = client.post("/api/v1/payments", json=payload)

    assert second_response.status_code == 201
    assert (
        second_response.json()["merchant_id"]
        == merchant_b.id
    )


def test_merchant_can_retrieve_own_payment(api_setup):
    client, _, _, _, _ = api_setup

    create_response = client.post(
        "/api/v1/payments",
        json={
            "reference": "ORD-API-003",
            "amount": "1500.00",
            "currency": "NGN",
            "customer_email": "customer@example.com",
        },
    )

    payment_id = create_response.json()["id"]

    response = client.get(f"/api/v1/payments/{payment_id}")

    assert response.status_code == 200
    assert response.json()["reference"] == "ORD-API-003"


def test_merchant_cannot_retrieve_another_merchants_payment(api_setup):
    client, _, _, merchant_b, current_merchant_id = api_setup

    create_response = client.post(
        "/api/v1/payments",
        json={
            "reference": "PRIVATE-ORDER-001",
            "amount": "5000.00",
            "currency": "NGN",
            "customer_email": "customer@example.com",
        },
    )

    assert create_response.status_code == 201
    payment_id = create_response.json()["id"]

    current_merchant_id["value"] = merchant_b.id

    response = client.get(f"/api/v1/payments/{payment_id}")

    assert response.status_code == 404


def test_expired_payment_request_is_rejected(api_setup):
    client, _, _, _, _ = api_setup

    expired_time = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    ).isoformat()

    response = client.post(
        "/api/v1/payments",
        json={
            "reference": "ORD-API-004",
            "amount": "1000.00",
            "currency": "NGN",
            "customer_email": "customer@example.com",
            "expires_at": expired_time,
        },
    )

    assert response.status_code == 409


def test_checkout_endpoint_successfully_initializes_payment(
    api_setup, monkeypatch
):
    client, _, merchant_a, _, _ = api_setup

    create_response = client.post(
        "/api/v1/payments",
        json={
            "reference": "ORD-API-CHECKOUT-001",
            "amount": "2500.00",
            "currency": "NGN",
            "customer_email": "customer@example.com",
        },
    )

    assert create_response.status_code == 201
    payment_id = create_response.json()["id"]

    async def fake_initialize(self, email, amount, currency, reference):
        return {
            "authorization_url": "https://checkout.example.com/pay",
            "access_code": "test-access-code",
            "reference": reference,
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaystackProvider.initialize_transaction",
        fake_initialize,
    )

    response = client.post(
        f"/api/v1/payments/{payment_id}/checkout"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["payment_id"] == payment_id
    assert data["authorization_url"] == (
        "https://checkout.example.com/pay"
    )
    assert data["access_code"] == "test-access-code"
    assert data["status"] == "PENDING"
    assert data["provider_reference"].startswith("TS-")


def test_merchant_cannot_initialize_another_merchants_checkout(
    api_setup, monkeypatch
):
    client, _, merchant_a, merchant_b, current_merchant_id = api_setup

    create_response = client.post(
        "/api/v1/payments",
        json={
            "reference": "ORD-API-PRIVATE-CHECKOUT",
            "amount": "1000.00",
            "customer_email": "customer@example.com",
        },
    )

    assert create_response.status_code == 201
    payment_id = create_response.json()["id"]

    async def fake_initialize(self, email, amount, currency, reference):
        raise AssertionError("Provider must not be called")

    monkeypatch.setattr(
        "app.services.payment_service.PaystackProvider.initialize_transaction",
        fake_initialize,
    )

    current_merchant_id["value"] = merchant_b.id

    response = client.post(
        f"/api/v1/payments/{payment_id}/checkout"
    )

    assert response.status_code == 404