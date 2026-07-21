from typing import Optional

from app.dto.client_connection import (
    AuthorizedConnectionContext,
    ClientConnectionResponseDTO,
    ConnectionInstructionsDTO,
    ValidationResult,
)


class ConnectionResponseBuilder:
    """Prepares the ClientConnectionResponseDTO containing client instructions based on authorization result and context."""

    def build(
        self,
        result: ValidationResult,
        context: Optional[AuthorizedConnectionContext] = None,
    ) -> ClientConnectionResponseDTO:
        target_context = context or result.context

        if result.allowed:
            # Future Headscale provision step will populate ConnectionInstructionsDTO fields
            # (e.g. login_server, preauth_key, hostname, expires_at) using target_context.
            instructions = ConnectionInstructionsDTO()
            return ClientConnectionResponseDTO(
                authorized=True,
                connection=instructions,
            )

        return ClientConnectionResponseDTO(
            authorized=False,
            code=result.code,
            message=result.message,
            connection=ConnectionInstructionsDTO(),
        )
