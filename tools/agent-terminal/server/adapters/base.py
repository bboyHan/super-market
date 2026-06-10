"""Platform adapter interface for integrating with third-party credential platforms."""

from abc import ABC, abstractmethod
from typing import Optional


class PlatformAdapter(ABC):
    """Abstract base class for platform-specific credential collection adapters."""

    name: str = "base"

    @abstractmethod
    async def login(self, credentials: dict) -> bool:
        """Log into the platform with provided credentials.
        
        Returns True if login was successful.
        """
        ...

    @abstractmethod
    async def check_login(self) -> bool:
        """Check if the current session is still logged in.
        
        Returns True if session is valid.
        """
        ...

    @abstractmethod
    async def generate(self, product_id: str, quantity: int) -> list[dict]:
        """Generate or collect credentials for a given product.
        
        Returns a list of resource dicts with keys: value, resource_type, metadata.
        """
        ...

    @abstractmethod
    async def get_balance(self) -> float:
        """Get the current account balance or available credits.
        
        Returns the balance as a float.
        """
        ...
