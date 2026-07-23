from app.integrations.headscale.client import IHeadscaleClient, RestHeadscaleClient
from app.integrations.headscale.exceptions import (
    HeadscaleError,
    HeadscaleConnectionError,
    HeadscaleAuthenticationError,
    HeadscaleRequestError,
    HeadscaleNotFoundError,
)
from app.integrations.headscale.dto import (
    HeadscaleUserDTO,
    HeadscalePreAuthKeyDTO,
    HeadscaleNodeDTO,
)
from app.integrations.headscale.models import (
    HeadscaleUser,
    HeadscalePreAuthKey,
    HeadscaleNode,
)
from app.integrations.headscale.mapper import HeadscaleMapper

__all__ = [
    "IHeadscaleClient",
    "RestHeadscaleClient",
    "HeadscaleError",
    "HeadscaleConnectionError",
    "HeadscaleAuthenticationError",
    "HeadscaleRequestError",
    "HeadscaleNotFoundError",
    "HeadscaleUserDTO",
    "HeadscalePreAuthKeyDTO",
    "HeadscaleNodeDTO",
    "HeadscaleUser",
    "HeadscalePreAuthKey",
    "HeadscaleNode",
    "HeadscaleMapper",
]
