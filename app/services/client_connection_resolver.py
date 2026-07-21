from sqlalchemy.orm import Session

from app.dto.client_connection import AuthorizedConnectionContext
from app.repositories.environment_repository import EnvironmentRepository
from app.repositories.published_container_repository import PublishedContainerRepository
from app.repositories.published_node_repository import PublishedNodeRepository
from app.services.access_token_resolver import AccessTokenResolver


class ClientConnectionResolver:
    """Loads all required entities for connection authorization and constructs AuthorizedConnectionContext."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.token_resolver = AccessTokenResolver(db)
        self.container_repo = PublishedContainerRepository(db)
        self.environment_repo = EnvironmentRepository(db)
        self.node_repo = PublishedNodeRepository(db)

    def resolve(self, raw_token: str) -> AuthorizedConnectionContext:
        token_hash, access_token = self.token_resolver.resolve(raw_token)

        published_container = None
        environment = None
        published_node = None

        if access_token is not None:
            published_container = self.container_repo.get_by_id(access_token.published_container_id)
            if published_container is not None:
                environment = self.environment_repo.get_by_id(published_container.environment_id)
                published_node = self.node_repo.get_by_container_id(published_container.id)

        return AuthorizedConnectionContext(
            raw_token=raw_token,
            token_hash=token_hash,
            access_token=access_token,
            published_container=published_container,
            environment=environment,
            published_node=published_node,
        )
