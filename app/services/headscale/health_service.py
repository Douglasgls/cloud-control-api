import logging
from typing import Optional
from app.core.config import get_settings
from app.integrations.headscale import IHeadscaleClient, RestHeadscaleClient

logger = logging.getLogger(__name__)


class HeadscaleHealthService:
    def __init__(self, client: Optional[IHeadscaleClient] = None) -> None:
        if client is not None:
            self.client = client
        else:
            settings = get_settings()
            self.client = RestHeadscaleClient(
                base_url=settings.headscale_url,
                api_key=settings.headscale_api_key,
                timeout=float(settings.headscale_timeout),
            )

    def check(self) -> bool:
        logger.info("Performing Headscale API health check")
        is_healthy = self.client.health_check()
        if is_healthy:
            logger.info("Headscale API is healthy and accessible")
        else:
            logger.error("Headscale API is unhealthy or inaccessible")
        return is_healthy
