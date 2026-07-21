from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dto.client_connection import (
    ClientConnectionRequestDTO,
    ClientConnectionResponseDTO,
    ValidationCode,
)
from app.services.client_connection_service import ClientConnectionService

router = APIRouter(prefix="/client", tags=["Client"])
DBSession = Annotated[Session, Depends(get_db)]

STATUS_CODE_MAP = {
    ValidationCode.TOKEN_NOT_FOUND: status.HTTP_401_UNAUTHORIZED,
    ValidationCode.TOKEN_REVOKED: status.HTTP_401_UNAUTHORIZED,
    ValidationCode.TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
    ValidationCode.ENVIRONMENT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ValidationCode.CONTAINER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ValidationCode.NODE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ValidationCode.ENVIRONMENT_OFFLINE: status.HTTP_403_FORBIDDEN,
    ValidationCode.CONTAINER_OFFLINE: status.HTTP_403_FORBIDDEN,
    ValidationCode.NODE_OFFLINE: status.HTTP_403_FORBIDDEN,
    ValidationCode.TAILSCALE_NOT_INSTALLED: status.HTTP_403_FORBIDDEN,
    ValidationCode.TAILSCALE_SERVICE_STOPPED: status.HTTP_403_FORBIDDEN,
}


@router.post(
    "/connect",
    response_model=ClientConnectionResponseDTO,
    summary="Authorize client connection to a published container",
    description="Validates token, environment, published container, node, and tailscale status before authorizing client connection.",
)
def connect_client(
    data: ClientConnectionRequestDTO,
    request: Request,
    db: DBSession,
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    service = ClientConnectionService(db)
    response_dto = service.connect(data, client_ip=client_ip)

    if not response_dto.authorized:
        http_status = STATUS_CODE_MAP.get(response_dto.code, status.HTTP_400_BAD_REQUEST)
        return JSONResponse(
            status_code=http_status,
            content=response_dto.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_dto.model_dump(),
    )
