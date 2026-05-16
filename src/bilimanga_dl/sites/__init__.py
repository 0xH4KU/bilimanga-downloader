"""Site adapter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bilimanga_dl.core.errors import ConfigurationError

if TYPE_CHECKING:
    from bilimanga_dl.sites.base import SiteAdapter


_REGISTRY: dict[str, SiteAdapter] = {}


def register(adapter: SiteAdapter) -> None:
    """Register *adapter* under its declared name."""
    _REGISTRY[adapter.name] = adapter


def unregister(name: str) -> None:
    """Remove an adapter. No-op when absent."""
    _REGISTRY.pop(name, None)


def get_for_url(url: str) -> SiteAdapter | None:
    """Return the first adapter that claims *url*."""
    for adapter in _REGISTRY.values():
        if adapter.matches_url(url):
            return adapter
    return None


def get_by_name(name: str) -> SiteAdapter:
    """Return a registered adapter by name."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise ConfigurationError(f"Unknown site adapter: {name!r}") from exc


def get_active() -> SiteAdapter:
    """Return the sole active adapter."""
    if not _REGISTRY:
        raise ConfigurationError("No site adapter is registered.")
    if len(_REGISTRY) > 1:
        raise ConfigurationError(
            f"Multiple site adapters registered ({sorted(_REGISTRY)}); explicit selection is required.",
        )
    return next(iter(_REGISTRY.values()))


def all_adapters() -> tuple[SiteAdapter, ...]:
    """Return every registered adapter."""
    return tuple(_REGISTRY.values())


def clear() -> None:
    """Drop every registered adapter. Intended for tests."""
    _REGISTRY.clear()


from bilimanga_dl.sites import bilimanga as _bilimanga  # noqa: E402, F401

__all__ = [
    "all_adapters",
    "clear",
    "get_active",
    "get_by_name",
    "get_for_url",
    "register",
    "unregister",
]
