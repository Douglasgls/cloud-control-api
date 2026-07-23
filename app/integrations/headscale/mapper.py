from datetime import datetime, timezone
from typing import Optional
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


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str or dt_str.startswith("0001-01-01"):
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None


class HeadscaleMapper:
    @staticmethod
    def to_user(dto: HeadscaleUserDTO) -> HeadscaleUser:
        dt = parse_datetime(dto.createdAt)
        return HeadscaleUser(
            id=dto.id,
            name=dto.name,
            created_at=dt if dt is not None else datetime.now(timezone.utc),
        )

    @staticmethod
    def to_preauth_key(dto: HeadscalePreAuthKeyDTO) -> HeadscalePreAuthKey:
        dt = parse_datetime(dto.createdAt)
        user_name = (
            dto.user.name if hasattr(dto.user, "name")
            else (dto.user.get("name") if isinstance(dto.user, dict) else str(dto.user))
        )
        return HeadscalePreAuthKey(
            id=dto.id,
            user=user_name,
            key=dto.key,
            reusable=dto.reusable,
            ephemeral=dto.ephemeral,
            used=dto.used,
            created_at=dt if dt is not None else datetime.now(timezone.utc),
            expiration=parse_datetime(dto.expiration),
        )

    @staticmethod
    def to_node(dto: HeadscaleNodeDTO) -> HeadscaleNode:
        dt = parse_datetime(dto.createdAt)
        user_dt = parse_datetime(dto.user.createdAt)
        return HeadscaleNode(
            id=dto.id,
            name=dto.name,
            given_name=dto.givenName,
            user=HeadscaleUser(
                id=dto.user.id,
                name=dto.user.name,
                created_at=user_dt if user_dt is not None else datetime.now(timezone.utc),
            ),
            ip_addresses=dto.ipAddresses,
            online=dto.online,
            valid_tags=dto.validTags,
            forced_tags=dto.forcedTags,
            created_at=dt if dt is not None else datetime.now(timezone.utc),
            last_seen=parse_datetime(dto.lastSeen),
            expiry=parse_datetime(dto.expiry),
        )
