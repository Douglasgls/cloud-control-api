from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.dtos.environment import CreateEnvironmentDTO, EnvironmentResponseDTO
from app.models.user import User
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/environments", tags=["Environments"])
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=EnvironmentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Criar ambiente e emitir seu token de instalação",
    description=(
        "O `environment_token` é exibido somente nesta resposta. "
        "Guarde-o para o futuro registro da API Local."
    ),
)
def create_environment(
    data: CreateEnvironmentDTO, db: DBSession, current_user: CurrentUser
) -> EnvironmentResponseDTO:
    return EnvironmentService(db).create(owner=current_user, data=data)
