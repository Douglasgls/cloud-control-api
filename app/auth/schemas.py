from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    type: str


class AgentTokenPayload(TokenPayload):
    environment_id: str
    user_id: int
