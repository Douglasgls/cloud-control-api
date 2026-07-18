from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.environment import Environment


class EnvironmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        name: str,
        description: str | None,
        environment_token_hash: str,
    ) -> Environment:
        environment = Environment(
            user_id=user_id,
            name=name,
            description=description,
            environment_token_hash=environment_token_hash,
        )
        self.db.add(environment)
        self.db.flush()
        return environment

    def get_by_id(self, environment_id: str) -> Environment | None:
        return self.db.get(Environment, environment_id)

    def get_by_token_hash(self, token_hash: str) -> Environment | None:
        return self.db.scalar(
            select(Environment).where(Environment.environment_token_hash == token_hash)
        )

    def update_status(self, environment_id: str, status_online: bool, last_ping: datetime | None = None) -> Environment | None:
        environment = self.get_by_id(environment_id)
        if environment:
            environment.status_online = status_online
            if last_ping:
                environment.last_ping = last_ping
            self.db.commit()
            self.db.refresh(environment)
        return environment
