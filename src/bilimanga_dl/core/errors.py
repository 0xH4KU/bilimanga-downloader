"""Domain error types used across the application."""

from __future__ import annotations


class BilimangaError(RuntimeError):
    """Base class for user-meaningful application errors."""


class ConfigurationError(BilimangaError):
    """Raised when runtime configuration is invalid or inconsistent."""


class RemoteSiteError(BilimangaError):
    """Raised when remote site access fails in a user-meaningful way."""


class HttpTimeoutError(RemoteSiteError):
    """Raised when an HTTP request exceeds its timeout."""

    def __init__(self, *, url: str, message: str | None = None) -> None:
        self.url = url
        super().__init__(message or f"HTTP request timed out for {url}.")


class HttpStatusError(RemoteSiteError):
    """Raised when an HTTP response returns a non-success status code."""

    def __init__(self, *, status_code: int, url: str, message: str | None = None) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(message or f"HTTP {status_code} for {url}.")


class HttpTransportError(RemoteSiteError):
    """Raised when HTTP transport fails before a response is available."""

    def __init__(self, *, url: str, message: str | None = None) -> None:
        self.url = url
        super().__init__(message or f"HTTP transport failed for {url}.")


class BrowserTimeoutError(BilimangaError):
    """Raised when a bounded browser operation exceeds its timeout."""


class PartialDownloadError(BilimangaError):
    """Raised when a chapter download completed only partially."""


class ConversionError(BilimangaError):
    """Raised when archive or PDF conversion cannot produce a valid output."""
