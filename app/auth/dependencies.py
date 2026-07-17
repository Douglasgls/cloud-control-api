from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.auth.schemas import AgentTokenPayload, TokenPayload
from app.core.database import get_db
from app.models.environment import Environment
from app.models.user import User
from app.repositories.environment_repository import EnvironmentRepository
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de autenticação inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = TokenPayload.model_validate(decode_access_token(credentials.credentials))
        if payload.type != "user":
            raise ValueError("Token não é de usuário")
        user_id = int(payload.sub)
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise unauthorized
    return user


def get_current_agent(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Environment:
    """Dependência para as futuras rotas /agent que aceitam somente JWT de Agent."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token do agent inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = AgentTokenPayload.model_validate(decode_access_token(credentials.credentials))
        if payload.type != "agent" or payload.sub != "environment":
            raise ValueError("Token não é de agent")
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized

    environment = EnvironmentRepository(db).get_by_id(payload.environment_id)
    if environment is None or environment.user_id != payload.user_id:
        raise unauthorized
    return environment
