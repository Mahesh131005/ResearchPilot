import uuid
import pytest
from httpx import AsyncClient

from app.core.security import validate_password_strength
from app.core.config import settings

def test_password_strength_validation():
    # Too short (< 10)
    valid, msg = validate_password_strength("Short1!")
    assert not valid
    assert "at least 10" in msg

    # Missing uppercase
    valid, msg = validate_password_strength("lowercase123!")
    assert not valid
    assert "uppercase" in msg

    # Missing lowercase
    valid, msg = validate_password_strength("UPPERCASE123!")
    assert not valid
    assert "lowercase" in msg

    # Missing digit
    valid, msg = validate_password_strength("NoDigitsHere!!")
    assert not valid
    assert "digit" in msg

    # Missing symbol
    valid, msg = validate_password_strength("NoSymbols12345")
    assert not valid
    assert "special symbol" in msg

    # Valid password
    valid, msg = validate_password_strength("ValidPassword123!")
    assert valid
    assert msg == "Password meets security requirements"

@pytest.mark.asyncio
async def test_user_registration_and_duplicate_prevention(async_client: AsyncClient):
    email = f"register_{uuid.uuid4().hex[:8]}@test.local"
    password = "StrongPassword123!"

    # 1. Successful registration
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["must_change_password"] is False

    # 2. Reject duplicate email
    dup_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]

@pytest.mark.asyncio
async def test_user_login_validation(async_client: AsyncClient):
    email = f"login_{uuid.uuid4().hex[:8]}@test.local"
    password = "SecurePassword2026!"

    # Register
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )

    # 1. Correct login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # 2. Wrong password
    bad_pw = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999!"}
    )
    assert bad_pw.status_code == 401
    assert "Invalid email or password" in bad_pw.json()["detail"]

    # 3. Nonexistent user
    non_user = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_999@test.local", "password": password}
    )
    assert non_user.status_code == 401

@pytest.mark.asyncio
async def test_token_refresh_and_rotation(async_client: AsyncClient):
    email = f"refresh_{uuid.uuid4().hex[:8]}@test.local"
    password = "PasswordForRefresh1!"

    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    refresh_token_1 = reg.json()["refresh_token"]

    # 1. Refresh token
    ref_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1}
    )
    assert ref_resp.status_code == 200
    data = ref_resp.json()
    assert "access_token" in data
    refresh_token_2 = data["refresh_token"]
    assert refresh_token_2 != refresh_token_1

    # 2. Token reuse detection: Reusing old token 1 must trigger reuse detection
    reuse_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1}
    )
    assert reuse_resp.status_code == 401
    assert "Token reuse detected" in reuse_resp.json()["detail"]

    # 3. All tokens revoked after reuse detection: token 2 should now also be revoked
    re_ref = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2}
    )
    assert re_ref.status_code == 401

@pytest.mark.asyncio
async def test_logout_revocation(async_client: AsyncClient):
    email = f"logout_{uuid.uuid4().hex[:8]}@test.local"
    password = "LogoutPassword123!"

    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    access_token = reg.json()["access_token"]
    refresh_token = reg.json()["refresh_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_resp.status_code == 200

    # Refresh must now fail
    ref_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert ref_resp.status_code == 401

@pytest.mark.asyncio
async def test_first_login_password_change_flow(async_client: AsyncClient):
    # Log in as initial admin who has must_change_password=True
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD
        }
    )
    assert login_resp.status_code == 200
    admin_tokens = login_resp.json()
    admin_access = admin_tokens["access_token"]

    # If must_change_password is true, accessing platform features returns 403
    if admin_tokens["must_change_password"]:
        blocked_resp = await async_client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {admin_access}"}
        )
        assert blocked_resp.status_code == 403
        assert "Password change required" in blocked_resp.json()["detail"]

        # Change password to new strong password
        new_pw = "ResearchPilot!AdminUpdated2026"
        change_resp = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": settings.INITIAL_ADMIN_PASSWORD,
                "new_password": new_pw
            },
            headers={"Authorization": f"Bearer {admin_access}"}
        )
        assert change_resp.status_code == 200
        new_tokens = change_resp.json()
        assert new_tokens["must_change_password"] is False

        # Access documents now succeeds
        ok_resp = await async_client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
        )
        assert ok_resp.status_code == 200

        # Change back for subsequent tests
        await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": new_pw,
                "new_password": settings.INITIAL_ADMIN_PASSWORD
            },
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
        )
