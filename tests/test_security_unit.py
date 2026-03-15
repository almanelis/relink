from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify_roundtrip():
    password = "my_super_secret_123"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong_password", password_hash) is False


def test_decode_invalid_token_returns_none():
    assert decode_access_token("definitely.not.a.valid.token") is None


def test_create_and_decode_access_token():
    token = create_access_token("student@example.com")
    subject = decode_access_token(token)
    assert subject == "student@example.com"
