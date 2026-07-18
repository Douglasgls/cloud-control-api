from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dtos.agent import AgentAuthenticationDTO, AgentAuthenticationResponseDTO
from app.services.agent_authentication_service import AgentAuthenticationService

router = APIRouter(prefix="/agent", tags=["Agent"])
DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/auth",
    response_model=AgentAuthenticationResponseDTO,
    summary="Autenticar a API Local pelo token do Environment",
    description=(
        "Troca o environment_token permanente por um JWT curto de Agent. "
        "Quando expirar, a API Local deve chamar esta rota novamente."
    ),
)
def authenticate_agent(
    data: AgentAuthenticationDTO, db: DBSession
) -> AgentAuthenticationResponseDTO:
    return AgentAuthenticationService(db).authenticate(data)
