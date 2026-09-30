
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


from app.core.auth  import get_current_user
from app.core.dependencies import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.entities import User
from app.schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED,)
def signup(request: SignupRequest, db: Annotated[Session, Depends(get_db)],) -> User:
    email = str(request.email).strip().lower()

    user = User(
        email=email,
        password_hash=hash_password(request.password),
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from exc

    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Annotated[Session, Depends(get_db)],) -> TokenResponse:
    email  = str(request.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )


    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user