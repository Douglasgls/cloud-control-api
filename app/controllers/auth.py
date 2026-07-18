from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dtos.auth import LoginDTO, LoginResponseDTO, RegisterDTO, UserResponseDTO
from app.services.authentication_service import AuthenticationService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])
DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar usuário",
)
def register(data: RegisterDTO, db: DBSession) -> UserResponseDTO:
    return UserResponseDTO.model_validate(UserService(db).register(data))


@router.post("/login", response_model=LoginResponseDTO, summary="Autenticar usuário")
def login(data: LoginDTO, db: DBSession) -> LoginResponseDTO:
    return AuthenticationService(db).login(data)
