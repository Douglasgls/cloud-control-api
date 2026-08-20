from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HeadscaleNodeResponseDTO(BaseModel):
    id: str
    headscale_node_id: str
    environment_id: str
    hostname: str
    given_name: Optional[str] = None
    tailscale_ip: Optional[str] = None
    online: bool = False
    last_seen: Optional[datetime] = None
    registered: bool = False
