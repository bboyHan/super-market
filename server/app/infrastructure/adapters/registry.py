from __future__ import annotations

from typing import Any

from loguru import logger

from app.infrastructure.adapters.base import PlatformAdapter


class AdapterRegistry:
    """Registry for all platform adapters.

    Allows dynamic registration and lookup of supplier adapters.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        """Register a platform adapter by its name."""
        if adapter.name in self._adapters:
            logger.warning("Adapter already registered, overwriting | name={}", adapter.name)
        self._adapters[adapter.name] = adapter
        logger.info("Adapter registered | name={}", adapter.name)

    def unregister(self, name: str) -> None:
        """Remove an adapter by name."""
        self._adapters.pop(name, None)
        logger.info("Adapter unregistered | name={}", name)

    def get(self, name: str) -> PlatformAdapter | None:
        """Get an adapter by name."""
        return self._adapters.get(name)

    def list_available(self) -> list[str]:
        """Return names of all registered adapters."""
        return list(self._adapters.keys())

    async def submit_order(self, adapter_name: str, **kwargs: Any) -> dict[str, Any]:
        """Submit an order via a named adapter."""
        adapter = self._adapters.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter '{adapter_name}' not found")
        return await adapter.submit_order(**kwargs)

    async def check_all_health(self) -> dict[str, bool]:
        """Check availability of all registered adapters."""
        result: dict[str, bool] = {}
        for name, adapter in self._adapters.items():
            try:
                result[name] = await adapter.is_available()
            except Exception:
                result[name] = False
        return result
