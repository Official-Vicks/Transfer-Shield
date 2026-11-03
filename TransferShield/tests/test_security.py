from app.core import hash_password, verify_password

def test_password_hashing():
    password = "MySecurePassword123"


    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("WrongPassword", hashed_password)

test_password_hashing()