from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def create_access_token(*, subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": subject, "exp": expires_at, "type": "user"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_agent_access_token(*, environment_id: str, user_id: int) -> str:
    """Emite um JWT exclusivo para chamadas autenticadas da API Local."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    return jwt.encode(
        {
            "sub": "environment",
            "environment_id": environment_id,
            "user_id": user_id,
            "exp": expires_at,
            "type": "agent",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
