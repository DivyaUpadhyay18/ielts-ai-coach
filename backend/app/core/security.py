"""
Security utilities for JWT authentication, password hashing, and rate limiting.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# JWT Constants
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Longer-lived refresh token


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> Optional[str]:
    """
    Validate password strength.
    Returns an error message if invalid, None if valid.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if len(password) > 128:
        return "Password must be less than 128 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number"
    if not any(c in "!@#$%^&*(),.?\":{}|<>_~`[]';/\\" for c in password):
        return "Password must contain at least one special character"
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException if token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    secret_key = settings.JWT_SECRET_KEY if expected_type == "access" else settings.JWT_REFRESH_SECRET_KEY
    
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        if token_type != expected_type:
            raise credentials_exception
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


def create_tokens(user_id: str, email: str) -> Tuple[str, str]:
    """
    Create both access and refresh tokens for a user.
    Returns (access_token, refresh_token).
    """
    token_data = {"sub": user_id, "email": email}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return access_token, refresh_token
