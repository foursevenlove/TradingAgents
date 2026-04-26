import os
from typing import Any, Optional, Dict, List, Union

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from .base_client import BaseLLMClient
from .validators import validate_model, get_provider_config


class AlibabaChatOpenAI(ChatOpenAI):
    """Custom ChatOpenAI that supports DashScope's enable_thinking via extra_body."""

    enable_thinking: bool = False
    max_thinking_tokens: Optional[int] = None

    def __init__(self, enable_thinking: bool = False, max_thinking_tokens: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.enable_thinking = enable_thinking
        self.max_thinking_tokens = max_thinking_tokens

    def _create_chat_completion(
        self,
        messages: List[Dict],
        **kwargs: Any,
    ) -> Any:
        """Override to add extra_body for DashScope's enable_thinking."""
        # Add extra_body for DashScope
        if self.enable_thinking:
            kwargs.setdefault("extra_body", {})
            kwargs["extra_body"]["enable_thinking"] = True
            # Limit thinking tokens to prevent 28MB overflow error
            if self.max_thinking_tokens:
                kwargs["extra_body"]["max_thinking_tokens"] = self.max_thinking_tokens

        return super()._create_chat_completion(messages, **kwargs)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Override to pass extra_body through."""
        # Add extra_body for DashScope
        if self.enable_thinking:
            kwargs.setdefault("extra_body", {})
            kwargs["extra_body"]["enable_thinking"] = True
            # Limit thinking tokens to prevent 28MB overflow error
            if self.max_thinking_tokens:
                kwargs["extra_body"]["max_thinking_tokens"] = self.max_thinking_tokens

        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class AlibabaClient(BaseLLMClient):
    """Client for Alibaba Cloud Bailian (DashScope) LLM provider.

    Supports enable_thinking parameter for deep reasoning mode.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        enable_thinking: bool = False,
        max_thinking_tokens: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.enable_thinking = enable_thinking
        self.max_thinking_tokens = max_thinking_tokens

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance for Alibaba Bailian."""
        llm_kwargs = {"model": self.model}

        config = get_provider_config("alibaba")

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url
        else:
            llm_kwargs["base_url"] = config.get(
                "default_base_url",
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

        api_key_env = config.get("api_key_env", "DASHSCOPE_API_KEY")
        api_key = os.environ.get(api_key_env) or os.environ.get("ALIBABA_API_KEY")
        if api_key:
            llm_kwargs["api_key"] = api_key

        for key in ("timeout", "max_retries", "api_key", "callbacks",
                    "http_client", "http_async_client", "temperature"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        if "timeout" not in llm_kwargs:
            llm_kwargs["timeout"] = 180

        llm_kwargs["enable_thinking"] = self.enable_thinking
        llm_kwargs["max_thinking_tokens"] = self.max_thinking_tokens

        return AlibabaChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("alibaba", self.model)