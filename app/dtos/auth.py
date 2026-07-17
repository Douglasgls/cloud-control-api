from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterDTO(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O nome não pode ser vazio.")
        return value


class LoginDTO(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


class LoginResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponseDTO
