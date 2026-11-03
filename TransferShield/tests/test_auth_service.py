from jose import jwt,JWSError
from app.core import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Merchant
from app.schemas import MerchantCreate
from app.services import AuthService
from app.core.security import verify_password


# Create an isolated test database
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def setup_function():
    """Create fresh database tables before each test."""
    Base.metadata.create_all(bind=engine)


def teardown_function():
    """Remove database tables after each test."""
    Base.metadata.drop_all(bind=engine)


def test_register_merchant():
    db = TestingSessionLocal()

    merchant_data = MerchantCreate(
        business_name="Test Business",
        email="test@example.com",
        password="SecurePassword123",
    )

    service = AuthService(db)
    merchant = service.register_merchant(merchant_data)

    assert merchant.id is not None
    assert merchant.business_name == "Test Business"
    assert merchant.email == "test@example.com"
    assert merchant.status is True

    # The password must not be stored as plaintext
    assert merchant.password_hash != "SecurePassword123"

    # The stored hash must successfully verify the original password
    assert verify_password(
        "SecurePassword123",
        merchant.password_hash,
    )

    db.close()


def test_register_duplicate_email():
    db = TestingSessionLocal()

    service = AuthService(db)

    first_merchant = MerchantCreate(
        business_name="First Business",
        email="same@example.com",
        password="Password123",
    )

    second_merchant = MerchantCreate(
        business_name="Second Business",
        email="same@example.com",
        password="Password456",
    )

    service.register_merchant(first_merchant)

    try:
        service.register_merchant(second_merchant)
        assert False, "Expected ValueError for duplicate email"
    except ValueError as error:
        assert str(error) == "A merchant with this email already exists"

    db.close()


def test_login_merchant():
    db = TestingSessionLocal()

    service = AuthService(db)

    merchant_data = MerchantCreate(
        business_name="Login Business",
        email="login@example.com",
        password="SecurePassword123",
    )

    service.register_merchant(merchant_data)

    access_token = service.login_merchant(
        "login@example.com",
        "SecurePassword123",
    )

    assert access_token is not None
    assert isinstance(access_token, str)

    # Verify that the JWT contains the correct merchant ID
    payload = jwt.decode(
        access_token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert payload["sub"] == "1"

    db.close()


def test_login_wrong_password():
    db = TestingSessionLocal()

    service = AuthService(db)

    merchant_data = MerchantCreate(
        business_name="Login Business",
        email="wrong-password@example.com",
        password="CorrectPassword123",
    )

    service.register_merchant(merchant_data)

    try:
        service.login_merchant(
            "wrong-password@example.com",
            "WrongPassword123",
        )
        assert False, "Expected ValueError for incorrect password"
    except ValueError as error:
        assert str(error) == "Invalid email or password"

    db.close()


def test_login_unknown_email():
    db = TestingSessionLocal()

    service = AuthService(db)

    try:
        service.login_merchant(
            "doesnotexist@example.com",
            "SomePassword123",
        )
        assert False, "Expected ValueError for unknown email"
    except ValueError as error:
        assert str(error) == "Invalid email or password"

    db.close()
