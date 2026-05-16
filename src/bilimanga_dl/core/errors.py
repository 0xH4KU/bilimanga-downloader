"""Domain error types used across the application."""

from __future__ import annotations


class BilimangaError(RuntimeError):
    """Base class for user-meaningful application errors."""


class ConfigurationError(BilimangaError):
    """Raised when runtime configuration is invalid or inconsistent."""


class RemoteSiteError(BilimangaError):
    """Raised when remote site access fails in a user-meaningful way."""


class PartialDownloadError(BilimangaError):
    """Raised when a chapter download completed only partially."""


class ConversionError(BilimangaError):
    """Raised when archive or PDF conversion cannot produce a valid output."""
