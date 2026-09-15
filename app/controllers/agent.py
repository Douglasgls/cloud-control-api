from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dtos.agent import AgentAuthenticationDTO, AgentAuthenticationResponseDTO
from app.services.agent_authentication_service import AgentAuthenticationService
from app.models.environment import Environment
from app.auth.dependencies import get_current_agent

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


@router.delete(
    "/unregister",
    status_code=204,
    summary="Desregistrar a API Local (Agent) da Cloud",
    description="Remove o Agent e seus recursos associados da Cloud de forma idempotente.",
)
def unregister_agent(
    db: DBSession,
    current_agent: Annotated[Environment, Depends(get_current_agent)],
) -> None:
    from app.services.environment_service import EnvironmentService
    EnvironmentService(db).unregister_agent(current_agent.id)

