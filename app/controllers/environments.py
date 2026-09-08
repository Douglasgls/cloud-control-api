from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.dtos.environment import CreateEnvironmentDTO, EnvironmentResponseDTO, EnvironmentSummaryDTO
from app.models.user import User
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/environments", tags=["Environments"])
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=list[EnvironmentSummaryDTO],
    summary="Listar ambientes do usuário autenticado",
)
def list_environments(
    db: DBSession, current_user: CurrentUser
) -> list[EnvironmentSummaryDTO]:
    return EnvironmentService(db).list_by_owner(owner=current_user)


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


@router.delete(
    "/{environment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir ambiente",
    description="Remove um ambiente pertencente ao usuário autenticado e limpa os recursos associados.",
)
def delete_environment(
    environment_id: str, db: DBSession, current_user: CurrentUser
) -> None:
    EnvironmentService(db).delete(owner=current_user, environment_id=environment_id)


