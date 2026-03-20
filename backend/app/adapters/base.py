from abc import ABC, abstractmethod
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    prompt: str
    params: dict = {}
    reference_images: list[str] = []
    reference_audio: str | None = None


class GenerateResult(BaseModel):
    file_url: str
    duration: float | None = None
    metadata: dict = {}


class BaseModelAdapter(ABC):
    """All AI model adapters must implement this interface."""

    name: str = ""

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> GenerateResult:
        ...

    async def check_health(self) -> bool:
        return True
