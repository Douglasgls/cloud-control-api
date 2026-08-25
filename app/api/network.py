from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_optional
from app.db.database import get_db
from app.dtos.network_catalog import NetworkCatalogResponseDTO
from app.models.user import User
from app.services.network_catalog_service import NetworkCatalogService

router = APIRouter(prefix="/network", tags=["Network Discovery"])
DBSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/endpoints",
    response_model=NetworkCatalogResponseDTO,
    summary="Obter catálogo de endpoints de rede autorizados (.interno)",
    description="Retorna o catálogo central de endpoints e portas autorizadas para o usuário/cliente autenticado.",
)
def get_network_endpoints(
    db: DBSession,
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)] = None,
) -> NetworkCatalogResponseDTO:
    catalog_service = NetworkCatalogService(db)
    if current_user:
        return catalog_service.get_catalog_for_user(current_user.id)
    return catalog_service.get_global_catalog()
