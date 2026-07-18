import hashlib
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.dtos.environment import CreateEnvironmentDTO, EnvironmentResponseDTO
from app.models.user import User
from app.repositories.environment_repository import EnvironmentRepository


class EnvironmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.environments = EnvironmentRepository(db)

    def create(self, *, owner: User, data: CreateEnvironmentDTO) -> EnvironmentResponseDTO:
        # 32 bytes aleatórios, codificados em URL-safe Base64, como um token de acesso.
        environment_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(environment_token.encode("utf-8")).hexdigest()
        environment = self.environments.create(
            user_id=owner.id,
            name=data.name.strip(),
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

    def update_status(self, environment_id: str, status_online: bool, last_ping: datetime | None = None) -> None:
        self.environments.update_status(environment_id, status_online, last_ping)
