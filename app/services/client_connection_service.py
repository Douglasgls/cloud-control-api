from typing import Optional

from sqlalchemy.orm import Session

from app.dto.client_connection import (
    ClientConnectionRequestDTO,
    ClientConnectionResponseDTO,
)
from app.services.client_connection_resolver import ClientConnectionResolver
from app.services.connection_audit_service import ConnectionAuditService
from app.services.connection_provision_service import ConnectionProvisionService
from app.services.connection_response_builder import ConnectionResponseBuilder
from app.services.container_access_authorization_service import (
    ContainerAccessAuthorizationService,
)


class ClientConnectionService:
    """High-level coordinator for client connection authorization workflow."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.resolver = ClientConnectionResolver(db)
        self.authorization_service = ContainerAccessAuthorizationService()
        self.provision_service = ConnectionProvisionService(db)
        self.audit_service = ConnectionAuditService(db)
        self.response_builder = ConnectionResponseBuilder()

    def connect(
        self,
        request: ClientConnectionRequestDTO,
        client_ip: Optional[str] = None,
    ) -> ClientConnectionResponseDTO:
        context = self.resolver.resolve(request.access_token)
        validation_result = self.authorization_service.authorize(context)

        connection = None
        preauth_key = None

        if validation_result.allowed:
            connection, preauth_key = self.provision_service.provision(context)

        self.audit_service.record_attempt(
            result=validation_result,
            raw_token=request.access_token,
            ip_address=client_ip,
        )

        return self.response_builder.build(
            result=validation_result,
            context=context,
            connection=connection,
            preauth_key=preauth_key,
        )

