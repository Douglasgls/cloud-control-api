from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.published_container import PublishedContainer


class PublishedContainerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_api_local_id(self, environment_id: str, api_local_id: str) -> PublishedContainer | None:
        return self.db.scalar(
            select(PublishedContainer).where(
                PublishedContainer.environment_id == environment_id,
                PublishedContainer.api_local_container_id == api_local_id
            )
        )

    def create(
        self,
        *,
        environment_id: str,
        api_local_id: str,
        name: str,
        container_number: int = 0,
        status: str = "unknown"
    ) -> PublishedContainer:
        container = PublishedContainer(
            environment_id=environment_id,
            api_local_container_id=api_local_id,
            name=name,
            container_number=container_number,
            status=status
        )
        self.db.add(container)
        self.db.flush()
        return container

    def update(
        self,
        container: PublishedContainer,
        *,
        name: str,
        container_number: int,
        status: str
    ) -> PublishedContainer:
        container.name = name
        container.container_number = container_number
        container.status = status
        self.db.flush()
        return container
