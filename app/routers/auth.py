
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-used-only-for-timing")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    email = str(request.email).lower()

    existing_user = await db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    if len(request.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=422,
            detail="Password is too long",
        )

    password_hash = await run_in_threadpool(
        hash_password,
        request.password,
    )

    user = User(
        email=email,
        hashed_password=password_hash,
    )

    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        ) from None

    await db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    email = str(request.email).lower()

    user = await db.scalar(
        select(User).where(User.email == email)
    )

    if user is None:
        await run_in_threadpool(
            verify_password,
            request.password,
            _DUMMY_PASSWORD_HASH,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    valid_password = await run_in_threadpool(
        verify_password,
        request.password,
        user.hashed_password,
    )

    if not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
    )
