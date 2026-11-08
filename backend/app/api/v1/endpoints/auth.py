from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.api.deps import get_db, get_current_user, require_admin
from app.core.config import settings
from app.core.security import (
    validate_password_strength,
    hash_password,
    verify_password,
    hash_token,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.research import User, RefreshToken
from app.services.billing_service import BillingService
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User, db_session: AsyncSession) -> tuple[str, str, RefreshToken]:
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "tier": user.tier,
    })
    refresh_token = create_refresh_token({
        "sub": str(user.id),
    })
    token_hash = hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    return access_token, refresh_token, token_record


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # 1. Enforce password complexity
    is_valid, msg = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # 2. Check email uniqueness
    email_clean = data.email.lower().strip()
    stmt = select(User).where(User.email == email_clean)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    # 3. Create user
    user = User(
        email=email_clean,
        hashed_password=hash_password(data.password),
        role="member",
        tier="free",
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()

    # 4. Initialize user wallet with complimentary starter credit
    await BillingService.get_or_create_wallet(db, user.id)

    # 5. Issue tokens
    access_token, refresh_token, token_record = _issue_tokens(user, db)
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        must_change_password=False
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    email_clean = data.email.lower().strip()
    stmt = select(User).where(User.email == email_clean)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator."
        )

    access_token, refresh_token, token_record = _issue_tokens(user, db)
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        must_change_password=user.must_change_password
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    # 1. Decode JWT structure
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 2. Look up hashed token in DB
    t_hash = hash_token(data.refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
    result = await db.execute(stmt)
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not recognized",
            headers={"WWW-Authenticate": "Bearer"}
        )

    now = datetime.now(timezone.utc)

    # 3. Detect token reuse: if already revoked, revoke all tokens for this user!
    if stored_token.revoked_at is not None:
        revoke_stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == stored_token.user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.execute(revoke_stmt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All active sessions have been terminated for security. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 4. Check expiration
    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        stored_token.revoked_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 5. Fetch user & check active
    user_stmt = select(User).where(User.id == stored_token.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 6. Rotate token: revoke current token and issue new pair
    stored_token.revoked_at = now

    new_access, new_refresh, new_record = _issue_tokens(user, db)
    db.add(new_record)
    await db.flush()

    stored_token.replaced_by_token_id = new_record.id
    await db.commit()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        must_change_password=user.must_change_password
    )


@router.post("/logout")
async def logout(
    data: Optional[RefreshTokenRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    if data and data.refresh_token:
        t_hash = hash_token(data.refresh_token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == t_hash,
            RefreshToken.user_id == current_user.id
        )
        result = await db.execute(stmt)
        token = result.scalar_one_or_none()
        if token and token.revoked_at is None:
            token.revoked_at = now
            await db.commit()
    else:
        # Revoke all tokens for current user
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.execute(stmt)
        await db.commit()

    return {"message": "Successfully logged out"}


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Verify current password
    if not current_user.hashed_password or not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # 2. Enforce new password complexity
    is_valid, msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # 3. Update password & clear must_change_password flag
    current_user.hashed_password = hash_password(data.new_password)
    current_user.must_change_password = False

    # 4. Revoke existing refresh tokens
    now = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(stmt)

    # 5. Issue new token pair
    access_token, refresh_token, token_record = _issue_tokens(current_user, db)
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        must_change_password=False
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# Admin user management (Non-destructive: account deactivation & role management)
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.id == admin.id and data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account"
        )

    if data.is_active is not None:
        target_user.is_active = data.is_active
        if not data.is_active:
            # Revoke all tokens for deactivated user
            now = datetime.now(timezone.utc)
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == target_user.id)
                .where(RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )

    if data.role is not None:
        if data.role not in ("admin", "member"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        target_user.role = data.role

    if data.tier is not None:
        if data.tier not in ("free", "pro", "enterprise"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tier")
        target_user.tier = data.tier

    await db.commit()
    await db.refresh(target_user)
    return target_user

