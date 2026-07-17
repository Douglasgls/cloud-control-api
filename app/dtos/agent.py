from pydantic import BaseModel, Field


class AgentAuthenticationDTO(BaseModel):
    environment_token: str = Field(min_length=1, max_length=1024)


class AgentAuthenticationResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
