
"""Tests for the Paystack provider integration."""

from decimal import Decimal

import httpx
import pytest

from app.services.paystack_provider import (
    PaystackError,
    PaystackProvider,
)


@pytest.mark.asyncio
async def test_initialize_transaction_successfully():
    def mock_response(request):
        assert request.url.path == "/transaction/initialize"
        assert request.headers["Authorization"] == "Bearer test_secret"

        payload = __import__("json").loads(request.content)
        assert payload["email"] == "customer@example.com"
        assert payload["amount"] == "250000"
        assert payload["currency"] == "NGN"
        assert payload["reference"] == "TS-TEST-001"

        return httpx.Response(
            200,
            json={
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": "https://checkout.paystack.com/test",
                    "access_code": "test-access-code",
                    "reference": "TS-TEST-001",
                },
            },
        )

    transport = httpx.MockTransport(mock_response)

    async with httpx.AsyncClient(transport=transport) as client:
        provider = PaystackProvider(
            secret_key="test_secret",
            client=client,
        )

        result = await provider.initialize_transaction(
            email="customer@example.com",
            amount=Decimal("2500.00"),
            currency="NGN",
            reference="TS-TEST-001",
        )

    assert result["authorization_url"] == "https://checkout.paystack.com/test"
    assert result["access_code"] == "test-access-code"
    assert result["reference"] == "TS-TEST-001"


@pytest.mark.asyncio
async def test_missing_secret_key_is_rejected():
    provider = PaystackProvider(secret_key="")

    with pytest.raises(PaystackError, match="not configured"):
        await provider.initialize_transaction(
            email="customer@example.com",
            amount=Decimal("1000.00"),
            currency="NGN",
            reference="TS-TEST-002",
        )


@pytest.mark.asyncio
async def test_non_positive_amount_is_rejected():
    provider = PaystackProvider(secret_key="test_secret")

    with pytest.raises(ValueError, match="greater than zero"):
        await provider.initialize_transaction(
            email="customer@example.com",
            amount=Decimal("0.00"),
            currency="NGN",
            reference="TS-TEST-003",
        )


@pytest.mark.asyncio
async def test_unsupported_currency_is_rejected():
    provider = PaystackProvider(secret_key="test_secret")

    with pytest.raises(ValueError, match="NGN only"):
        await provider.initialize_transaction(
            email="customer@example.com",
            amount=Decimal("1000.00"),
            currency="USD",
            reference="TS-TEST-004",
        )


@pytest.mark.asyncio
async def test_provider_failure_is_handled():
    def mock_response(request):
        return httpx.Response(
            400,
            json={"status": False, "message": "Invalid request"},
        )

    transport = httpx.MockTransport(mock_response)

    async with httpx.AsyncClient(transport=transport) as client:
        provider = PaystackProvider(
            secret_key="test_secret",
            client=client,
        )

        with pytest.raises(PaystackError, match="rejected"):
            await provider.initialize_transaction(
                email="customer@example.com",
                amount=Decimal("1000.00"),
                currency="NGN",
                reference="TS-TEST-005",
            )
