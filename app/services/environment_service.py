import hashlib
import logging
import secrets
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dtos.environment import CreateEnvironmentDTO, EnvironmentResponseDTO, EnvironmentSummaryDTO
from app.models.user import User
from app.repositories.environment_repository import EnvironmentRepository

logger = logging.getLogger(__name__)


class EnvironmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.environments = EnvironmentRepository(db)

    def create(self, *, owner: User, data: CreateEnvironmentDTO) -> EnvironmentResponseDTO:
        name = data.name.strip()
        existing = self.environments.get_by_user_id_and_name(owner.id, name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe um ambiente cadastrado com o nome '{name}'.",
            )

        # 32 bytes aleatórios, codificados em URL-safe Base64, como um token de acesso.
        environment_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(environment_token.encode("utf-8")).hexdigest()
        environment = self.environments.create(
            user_id=owner.id,
            name=name,
            description=data.description,
            environment_token_hash=token_hash,
        )
        self.db.commit()
        self.db.refresh(environment)
        return EnvironmentResponseDTO(
            environment_id=environment.id,
            name=environment.name,
            description=environment.description,
            status_online=environment.status_online,
            last_ping=environment.last_ping,
            environment_token=environment_token,
        )

    def list_by_owner(self, owner: User) -> list[EnvironmentSummaryDTO]:
        envs = self.environments.get_by_user_id(owner.id)
        return [
            EnvironmentSummaryDTO(
                environment_id=env.id,
                name=env.name,
                description=env.description,
                status_online=env.status_online,
                last_ping=env.last_ping,
            )
            for env in envs
        ]

    def update_status(self, environment_id: str, status_online: bool, last_ping: datetime | None = None) -> None:
        self.environments.update_status(environment_id, status_online, last_ping)

    def delete(self, owner: User, environment_id: str) -> None:
        environment = self.environments.get_by_id(environment_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ambiente não encontrado.",
            )

        if environment.user_id != owner.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a este ambiente.",
            )

        try:
            from app.services.headscale.provisioning_service import HeadscaleProvisioningService
            provisioning_service = HeadscaleProvisioningService(self.db)
            provisioning_service.remove_environment(environment_id)
        except Exception as e:
            logger.warning(f"Erro ao remover ambiente '{environment_id}' do Headscale: {e}")

        self.environments.delete(environment)

