"""LLM token usage tracking callback for LangChain."""
from contextlib import contextmanager
from contextvars import ContextVar
from math import ceil
from typing import Dict, Any, Optional, List
from uuid import UUID
from collections import defaultdict

from langchain_core.callbacks import BaseCallbackHandler


_CURRENT_STAGE: ContextVar[str] = ContextVar("token_tracking_stage", default="unattributed")
_CURRENT_CALLBACKS: ContextVar[tuple] = ContextVar("token_tracking_callbacks", default=())


def _empty_counter() -> Dict[str, int]:
    return {
        "calls": 0,
        "observed_token_calls": 0,
        "input": 0,
        "output": 0,
        "total": 0,
        "estimated_input": 0,
        "estimated_output": 0,
        "estimated_total": 0,
        "prompt_chars": 0,
        "completion_chars": 0,
    }


def _estimate_tokens_from_chars(char_count: int) -> int:
    """Approximate mixed Chinese/English token count when provider usage is absent."""
    if char_count <= 0:
        return 0
    return max(1, ceil(char_count / 2))


def get_current_token_stage() -> str:
    return _CURRENT_STAGE.get() or "unattributed"


def get_current_token_callbacks() -> List[Any]:
    return list(_CURRENT_CALLBACKS.get() or ())


def get_current_llm_config(metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Return LangChain invoke config carrying current callbacks and stage metadata."""
    callbacks = get_current_token_callbacks()
    stage = get_current_token_stage()
    merged_metadata = {"token_stage": stage}
    if metadata:
        merged_metadata.update(metadata)

    if not callbacks and not merged_metadata:
        return None
    config: Dict[str, Any] = {"metadata": merged_metadata}
    if callbacks:
        config["callbacks"] = callbacks
    return config


@contextmanager
def token_tracking_context(
    stage: str,
    callbacks: Optional[List[Any]] = None,
):
    """Set token attribution context for nested LangChain LLM calls."""
    stage_token = _CURRENT_STAGE.set(stage or "unattributed")
    callbacks_token = _CURRENT_CALLBACKS.set(tuple(callbacks or ()))
    try:
        yield
    finally:
        _CURRENT_STAGE.reset(stage_token)
        _CURRENT_CALLBACKS.reset(callbacks_token)


class TokenTracker(BaseCallbackHandler):
    """LangChain callback handler that tracks LLM token usage per task."""

    def __init__(self, task_id: str = "default"):
        super().__init__()
        self.task_id = task_id
        self._tokens: Dict[str, Dict[str, int]] = defaultdict(_empty_counter)
        self._call_count: Dict[str, int] = defaultdict(int)
        self._by_stage: Dict[str, Dict[str, Any]] = {}
        self._runs: Dict[UUID, Dict[str, Any]] = {}

    def _stage_bucket(self, stage: str) -> Dict[str, Any]:
        if stage not in self._by_stage:
            self._by_stage[stage] = {
                "calls": 0,
                "observed_token_calls": 0,
                "input": 0,
                "output": 0,
                "total": 0,
                "estimated_input": 0,
                "estimated_output": 0,
                "estimated_total": 0,
                "prompt_chars": 0,
                "completion_chars": 0,
                "models": defaultdict(_empty_counter),
            }
        return self._by_stage[stage]

    @staticmethod
    def _extract_model(kwargs: Dict[str, Any]) -> str:
        invocation_params = kwargs.get("invocation_params", {}) or {}
        return (
            invocation_params.get("model")
            or invocation_params.get("model_name")
            or invocation_params.get("model_id")
            or "unknown"
        )

    @staticmethod
    def _extract_stage(metadata: Optional[Dict[str, Any]]) -> str:
        if metadata and metadata.get("token_stage"):
            return str(metadata["token_stage"])
        return get_current_token_stage()

    @staticmethod
    def _extract_usage(response: Any) -> Optional[Dict[str, int]]:
        candidates = []
        if hasattr(response, "llm_output") and response.llm_output:
            candidates.append(response.llm_output.get("token_usage", {}))
            candidates.append(response.llm_output.get("usage", {}))

        if hasattr(response, "generations") and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if getattr(gen, "generation_info", None):
                        candidates.append(gen.generation_info.get("token_usage", {}))
                        candidates.append(gen.generation_info.get("usage", {}))
                    message = getattr(gen, "message", None)
                    if message is not None:
                        if getattr(message, "usage_metadata", None):
                            candidates.append(message.usage_metadata)
                        if getattr(message, "response_metadata", None):
                            candidates.append(message.response_metadata.get("token_usage", {}))
                            candidates.append(message.response_metadata.get("usage", {}))

        for usage in candidates:
            if not usage:
                continue
            input_tokens = (
                usage.get("prompt_tokens")
                or usage.get("input_tokens")
                or usage.get("prompt")
                or 0
            )
            output_tokens = (
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or usage.get("completion")
                or 0
            )
            try:
                input_tokens = int(input_tokens or 0)
                output_tokens = int(output_tokens or 0)
            except (TypeError, ValueError):
                continue
            if input_tokens or output_tokens:
                return {"input": input_tokens, "output": output_tokens}
        return None

    @staticmethod
    def _extract_completion_chars(response: Any) -> int:
        texts = []
        if hasattr(response, "generations") and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    text = getattr(gen, "text", None)
                    if text:
                        texts.append(str(text))
                    message = getattr(gen, "message", None)
                    if message is not None:
                        content = getattr(message, "content", None)
                        if content:
                            texts.append(str(content))
        return sum(len(text) for text in texts)

    @staticmethod
    def _add_counter(bucket: Dict[str, int], *, input_tokens: int, output_tokens: int,
                     estimated_input: int, estimated_output: int,
                     prompt_chars: int, completion_chars: int,
                     observed: bool) -> None:
        bucket["input"] += input_tokens
        bucket["output"] += output_tokens
        bucket["total"] += input_tokens + output_tokens
        bucket["estimated_input"] += estimated_input
        bucket["estimated_output"] += estimated_output
        bucket["estimated_total"] += estimated_input + estimated_output
        bucket["prompt_chars"] += prompt_chars
        bucket["completion_chars"] += completion_chars
        if observed:
            bucket["observed_token_calls"] += 1

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts."""
        model = self._extract_model(kwargs)
        stage = self._extract_stage(metadata)
        prompt_chars = sum(len(str(prompt)) for prompt in prompts or [])
        estimated_input = _estimate_tokens_from_chars(prompt_chars)

        self._call_count[model] += 1
        self._tokens[model]["calls"] += 1

        stage_bucket = self._stage_bucket(stage)
        stage_bucket["calls"] += 1
        stage_bucket["models"][model]["calls"] += 1

        self._runs[run_id] = {
            "model": model,
            "stage": stage,
            "prompt_chars": prompt_chars,
            "estimated_input": estimated_input,
        }

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends. Track token usage from response."""
        run_info = self._runs.pop(run_id, {})
        model = run_info.get("model") or self._extract_model(kwargs)
        stage = run_info.get("stage") or get_current_token_stage()
        prompt_chars = int(run_info.get("prompt_chars", 0))
        estimated_input = int(run_info.get("estimated_input", 0))
        completion_chars = self._extract_completion_chars(response)

        usage = self._extract_usage(response)
        if usage:
            input_tokens = usage["input"]
            output_tokens = usage["output"]
            estimated_input = input_tokens
            estimated_output = output_tokens
            observed = True
        else:
            input_tokens = 0
            output_tokens = 0
            estimated_output = _estimate_tokens_from_chars(completion_chars)
            observed = False

        self._add_counter(
            self._tokens[model],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_input=estimated_input,
            estimated_output=estimated_output,
            prompt_chars=prompt_chars,
            completion_chars=completion_chars,
            observed=observed,
        )

        stage_bucket = self._stage_bucket(stage)
        self._add_counter(
            stage_bucket,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_input=estimated_input,
            estimated_output=estimated_output,
            prompt_chars=prompt_chars,
            completion_chars=completion_chars,
            observed=observed,
        )
        self._add_counter(
            stage_bucket["models"][model],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_input=estimated_input,
            estimated_output=estimated_output,
            prompt_chars=prompt_chars,
            completion_chars=completion_chars,
            observed=observed,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get token usage statistics."""
        models = {model: dict(stats) for model, stats in self._tokens.items()}
        by_stage = {}
        for stage, stats in self._by_stage.items():
            stage_stats = {
                key: value for key, value in stats.items()
                if key != "models"
            }
            stage_stats["models"] = {
                model: dict(model_stats)
                for model, model_stats in stats["models"].items()
            }
            by_stage[stage] = stage_stats

        total_input = sum(t["input"] for t in models.values())
        total_output = sum(t["output"] for t in models.values())
        total_estimated_input = sum(t["estimated_input"] for t in models.values())
        total_estimated_output = sum(t["estimated_output"] for t in models.values())
        return {
            "task_id": self.task_id,
            "models": models,
            "by_stage": by_stage,
            "call_count": dict(self._call_count),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_estimated_input_tokens": total_estimated_input,
            "total_estimated_output_tokens": total_estimated_output,
            "total_estimated_tokens": total_estimated_input + total_estimated_output,
        }


# Global registry for token trackers per task
_token_trackers: Dict[str, TokenTracker] = {}


def get_token_tracker(task_id: str) -> TokenTracker:
    """Get or create a token tracker for a task."""
    if task_id not in _token_trackers:
        _token_trackers[task_id] = TokenTracker(task_id)
    return _token_trackers[task_id]


def remove_token_tracker(task_id: str):
    """Remove token tracker after task completes."""
    _token_trackers.pop(task_id, None)


def get_all_stats() -> Dict[str, Any]:
    """Get stats from all active trackers."""
    return {task_id: tracker.get_stats() for task_id, tracker in _token_trackers.items()}
