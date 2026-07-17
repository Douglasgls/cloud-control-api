from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateEnvironmentDTO(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=65535)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O nome não pode ser vazio.")
        return value


class EnvironmentResponseDTO(BaseModel):
    """Resposta exclusiva da criação; o token não pode ser recuperado depois."""

    model_config = ConfigDict(from_attributes=True)

    environment_id: str
    name: str
    description: str | None
    status_online: bool
    last_ping: datetime | None
    environment_token: str
