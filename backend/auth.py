import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv(Path(__file__).resolve().parent / ".env")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)

if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")

if not 1 <= ACCESS_TOKEN_EXPIRE_MINUTES <= 15:
    raise ValueError(
        "ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 15"
    )

if REFRESH_TOKEN_EXPIRE_DAYS < 1:
    raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def create_token_id() -> str:
    return secrets.token_urlsafe(24)


def create_access_token(
    user_id: int,
    role: str,
    session_id: int,
    token_id: str
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "jti": token_id,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "sub", "sid", "jti"]}
    )