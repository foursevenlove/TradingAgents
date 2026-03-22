import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model


class MiniMaxClient(BaseLLMClient):
    """Client for MiniMax LLM provider.

    MiniMax provides OpenAI-compatible API, so we use ChatOpenAI
    with custom base_url and api_key configuration.

    Supported models:
    - MiniMax-M2.7 (deep reasoning model)
    - MiniMax-M2.5 (fast reasoning model)
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance for MiniMax."""
        llm_kwargs = {"model": self.model}

        # Set MiniMax API endpoint (OpenAI-compatible)
        # Official endpoint: https://api.minimaxi.com/v1
        if self.base_url:
            llm_kwargs["base_url"] = self.base_url
        else:
            llm_kwargs["base_url"] = "https://api.minimaxi.com/v1"

        # Get API key from environment
        api_key = os.environ.get("MINIMAX_API_KEY")
        if api_key:
            llm_kwargs["api_key"] = api_key

        # Pass through additional kwargs (timeout, max_retries, http_client, etc.)
        for key in ("timeout", "max_retries", "api_key", "callbacks", "http_client", "http_async_client"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return ChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for MiniMax provider."""
        return validate_model("minimax", self.model)
