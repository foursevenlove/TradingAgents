"""LLM token usage tracking callback for LangChain."""
from typing import Dict, Any, Optional, List
from uuid import UUID
from collections import defaultdict

from langchain_core.callbacks import BaseCallbackHandler


class TokenTracker(BaseCallbackHandler):
    """LangChain callback handler that tracks LLM token usage per task."""

    def __init__(self, task_id: str = "default"):
        super().__init__()
        self.task_id = task_id
        self._tokens: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
        self._call_count: Dict[str, int] = defaultdict(int)

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
        model = kwargs.get("invocation_params", {}).get("model", "unknown")
        self._call_count[model] += 1

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
        model = kwargs.get("invocation_params", {}).get("model", "unknown")

        # Try to extract token usage from response
        try:
            # OpenAI-compatible response structure
            if hasattr(response, "llm_output") and response.llm_output:
                token_usage = response.llm_output.get("token_usage", {})
                if token_usage:
                    self._tokens[model]["input"] += token_usage.get("prompt_tokens", 0)
                    self._tokens[model]["output"] += token_usage.get("completion_tokens", 0)

            # Alternative: check response.generations
            elif hasattr(response, "generations") and response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        if hasattr(gen, "generation_info") and gen.generation_info:
                            token_usage = gen.generation_info.get("token_usage", {})
                            if token_usage:
                                self._tokens[model]["input"] += token_usage.get("prompt_tokens", 0)
                                self._tokens[model]["output"] += token_usage.get("completion_tokens", 0)
        except Exception:
            pass  # Token tracking is optional, don't break on errors

    def get_stats(self) -> Dict[str, Any]:
        """Get token usage statistics."""
        total_input = sum(t["input"] for t in self._tokens.values())
        total_output = sum(t["output"] for t in self._tokens.values())
        return {
            "task_id": self.task_id,
            "models": dict(self._tokens),
            "call_count": dict(self._call_count),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
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