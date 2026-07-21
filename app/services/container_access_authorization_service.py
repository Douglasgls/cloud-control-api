from datetime import datetime, timezone
from typing import Optional

from app.dto.client_connection import (
    AuthorizedConnectionContext,
    ValidationCode,
    ValidationResult,
)


class ContainerAccessAuthorizationService:
    """Single source of truth for validating whether a client is authorized to access a published container.

    This service performs PURE validation against an AuthorizedConnectionContext without loading data
    or knowing anything about HTTP/DTO representations.
    """

    def authorize(self, context: AuthorizedConnectionContext) -> ValidationResult:
        result = (
            self._validate_token_exists(context)
            or self._validate_token_active(context)
            or self._validate_token_not_expired(context)
            or self._validate_environment_exists(context)
            or self._validate_environment_online(context)
            or self._validate_container_exists(context)
            or self._validate_container_running(context)
            or self._validate_node_exists(context)
            or self._validate_tailscale_installed(context)
            or self._validate_tailscale_service_running(context)
            or self._validate_node_online(context)
        )

        if result is not None:
            return result

        return ValidationResult(
            allowed=True,
            context=context,
        )

    def _validate_token_exists(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.access_token is None:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.TOKEN_NOT_FOUND,
                message="Access token not found.",
                context=context,
            )
        return None

    def _validate_token_active(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.access_token and not context.access_token.active:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.TOKEN_REVOKED,
                message="Access token has been revoked.",
                context=context,
            )
        return None

    def _validate_token_not_expired(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.access_token and context.access_token.expires_at is not None:
            expires_at = context.access_token.expires_at
            now = datetime.now(timezone.utc) if expires_at.tzinfo is not None else datetime.now()
            if expires_at <= now:
                return ValidationResult(
                    allowed=False,
                    code=ValidationCode.TOKEN_EXPIRED,
                    message="Access token has expired.",
                    context=context,
                )
        return None

    def _validate_environment_exists(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.environment is None:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.ENVIRONMENT_NOT_FOUND,
                message="Environment not found.",
                context=context,
            )
        return None

    def _validate_environment_online(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.environment and not context.environment.status_online:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.ENVIRONMENT_OFFLINE,
                message="Environment is offline.",
                context=context,
            )
        return None

    def _validate_container_exists(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.published_container is None:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.CONTAINER_NOT_FOUND,
                message="Published container not found.",
                context=context,
            )
        return None

    def _validate_container_running(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.published_container:
            status = (context.published_container.status or "").lower()
            if status != "running":
                return ValidationResult(
                    allowed=False,
                    code=ValidationCode.CONTAINER_OFFLINE,
                    message="Published container is offline.",
                    context=context,
                )
        return None

    def _validate_node_exists(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        print(context)
        if context.published_node is None:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.NODE_NOT_FOUND,
                message="Published node not found.",
                context=context,
            )
        return None

    def _validate_tailscale_installed(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.published_node and not context.published_node.installed:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.TAILSCALE_NOT_INSTALLED,
                message="Tailscale is not installed on node.",
                context=context,
            )
        return None

    def _validate_tailscale_service_running(
        self, context: AuthorizedConnectionContext
    ) -> Optional[ValidationResult]:
        if context.published_node and not context.published_node.service_running:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.TAILSCALE_SERVICE_STOPPED,
                message="Tailscale service is stopped on node.",
                context=context,
            )
        return None

    def _validate_node_online(self, context: AuthorizedConnectionContext) -> Optional[ValidationResult]:
        if context.published_node and not context.published_node.online:
            return ValidationResult(
                allowed=False,
                code=ValidationCode.NODE_OFFLINE,
                message="Published node is offline.",
                context=context,
            )
        return None
