from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, Optional
from pydantic import BaseModel

from app.core.security import verify_password, create_access_token
from app.core.security.jwt import create_refresh_token, decode_token
from app.core.security.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


class TokenWithRefresh(TokenResponse):
    refresh_token: str
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/token", response_model=TokenWithRefresh)
@router.post("/login", response_model=TokenWithRefresh, include_in_schema=False)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    from app.core.config import settings
    access_token = create_access_token(
        subject=str(user.id),
        extra={"role": user.role.value, "email": user.email},
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    return TokenWithRefresh(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenWithRefresh)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange refresh token for a new access token."""
    from jose import JWTError
    try:
        payload = decode_token(body.refresh_token, token_type="refresh")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {e}")

    user_id = payload.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    from app.core.config import settings
    access_token = create_access_token(
        subject=str(user.id),
        extra={"role": user.role.value, "email": user.email},
    )
    new_refresh = create_refresh_token(subject=str(user.id))
    return TokenWithRefresh(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
        "full_name": current_user.full_name,
    }
