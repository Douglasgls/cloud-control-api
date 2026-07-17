from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.password import verify_password
from app.dtos.auth import LoginDTO, LoginResponseDTO, UserResponseDTO
from app.repositories.user_repository import UserRepository


class AuthenticationService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def login(self, data: LoginDTO) -> LoginResponseDTO:
        user = self.users.get_by_email(str(data.email).lower())
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha inválidos.",
            )
        return LoginResponseDTO(
            access_token=create_access_token(subject=str(user.id)),
            user=UserResponseDTO.model_validate(user),
        )
