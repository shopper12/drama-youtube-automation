from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("Configure the OpenAI provider")


class GeminiProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("Configure the Gemini provider")
