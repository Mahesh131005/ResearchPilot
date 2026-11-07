from abc import ABC, abstractmethod
from typing import List, Optional, Type, TypeVar, Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class EmbeddingProvider(ABC):
    """Abstract interface for generating dense vector embeddings."""

    @property
    def is_live(self) -> bool:
        """Returns True if the provider connects to a live remote API."""
        return False

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text chunks."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Generates an embedding vector for a single search query."""
        pass


class LLMProvider(ABC):
    """Abstract interface for interacting with large language models."""

    @property
    def is_live(self) -> bool:
        """Returns True if the provider connects to a live remote API."""
        return False

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generates a text completion for a prompt."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        """Generates a validated structured response conforming to a Pydantic schema."""
        pass

