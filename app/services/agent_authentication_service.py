import hashlib

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_agent_access_token
from app.core.config import get_settings
from app.dtos.agent import AgentAuthenticationDTO, AgentAuthenticationResponseDTO
from app.repositories.environment_repository import EnvironmentRepository


class AgentAuthenticationService:
    """Troca o token permanente do Environment por um JWT curto do Agent."""

    def __init__(self, db: Session) -> None:
        self.environments = EnvironmentRepository(db)

    def authenticate(self, data: AgentAuthenticationDTO) -> AgentAuthenticationResponseDTO:
        token_hash = hashlib.sha256(data.environment_token.encode("utf-8")).hexdigest()
        environment = self.environments.get_by_token_hash(token_hash)
        if environment is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Environment token inválido.",
            )

        settings = get_settings()
        return AgentAuthenticationResponseDTO(
            access_token=create_agent_access_token(
                environment_id=environment.id, user_id=environment.user_id
            ),
            expires_in=settings.jwt_access_token_expires_in,
        )
