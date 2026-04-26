import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model, get_provider_config


class MiniMaxClient(BaseLLMClient):
    """Client for MiniMax LLM provider.

    MiniMax provides OpenAI-compatible API, so we use ChatOpenAI
    with custom base_url and api_key configuration.

    Configuration is loaded from llm_models.json - edit that file to add/remove models.
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

        # Load config from llm_models.json
        config = get_provider_config("minimax")

        # Set API endpoint (use config default if not overridden)
        if self.base_url:
            llm_kwargs["base_url"] = self.base_url
        else:
            llm_kwargs["base_url"] = config.get("default_base_url", "https://api.minimaxi.com/v1")

        # Get API key from environment
        api_key_env = config.get("api_key_env", "MINIMAX_API_KEY")
        api_key = os.environ.get(api_key_env)
        if api_key:
            llm_kwargs["api_key"] = api_key

        # Pass through additional kwargs (timeout, max_retries, http_client, etc.)
        for key in ("timeout", "max_retries", "api_key", "callbacks", "http_client", "http_async_client", "temperature"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Default timeout: 5 minutes per request. MiniMax reasoning models can be slow
        # but if no response in 5 min it's almost certainly stuck.
        if "timeout" not in llm_kwargs:
            llm_kwargs["timeout"] = 300

        return ChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for MiniMax provider."""
        return validate_model("minimax", self.model)