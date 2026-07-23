class HeadscaleError(Exception):
    """Base exception for all Headscale integration operations."""
    pass


class HeadscaleConnectionError(HeadscaleError):
    """Raised when the connection to the Headscale REST API fails (e.g. timeout, DNS issue)."""
    pass


class HeadscaleAuthenticationError(HeadscaleError):
    """Raised when authentication credentials (API key) are invalid (401/403)."""
    pass


class HeadscaleRequestError(HeadscaleError):
    """Raised when the Headscale API returns an error response (status code >= 400)."""
    def __init__(self, message: str, status_code: int, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class HeadscaleNotFoundError(HeadscaleRequestError):
    """Raised when a specific resource is not found on the Headscale server (404)."""
    pass
