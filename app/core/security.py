from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from app.core.config import get_settings


password_hasher = PasswordHasher()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError):
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )