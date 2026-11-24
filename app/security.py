import hashlib
import hmac
import os
from datetime import datetime, timezone, timedelta
import jwt
from app.config import get_settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
    )
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3 or parts[0] != "scrypt":
            return False
        salt = bytes.fromhex(parts[1])
        target_key = parts[2]
        computed_key = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
        ).hex()
        return hmac.compare_digest(computed_key, target_key)
    except Exception:
        return False


def create_access_token(user_id: int, username: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.token_expire_seconds)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, str | int]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
