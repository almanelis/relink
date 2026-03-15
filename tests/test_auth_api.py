import pytest


@pytest.mark.asyncio
async def test_register_and_login_flow(client):
    register_resp = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "12345678"},
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["access_token"]
    assert token

    # повторная регистрация того же email должна честно отвалиться.
    duplicate_resp = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "12345678"},
    )
    assert duplicate_resp.status_code == 409
    assert duplicate_resp.json()["detail"] == "Email already registered"

    login_resp = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "12345678"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_with_invalid_password_returns_401(client):
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "12345678"},
    )

    bad_login_resp = await client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "i_am_wrong"},
    )
    assert bad_login_resp.status_code == 401
    assert bad_login_resp.json()["detail"] == "Invalid credentials"
