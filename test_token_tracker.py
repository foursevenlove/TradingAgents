from types import SimpleNamespace
from uuid import uuid4

from tradingagents.utils.token_tracker import TokenTracker, token_tracking_context


def test_token_tracker_groups_usage_by_stage():
    tracker = TokenTracker("task-1")
    run_id = uuid4()

    with token_tracking_context("News Analyst", [tracker]):
        tracker.on_llm_start(
            {},
            ["新闻分析 prompt"],
            run_id=run_id,
            invocation_params={"model": "qwen-test"},
        )
        tracker.on_llm_end(
            SimpleNamespace(llm_output={"token_usage": {"prompt_tokens": 100, "completion_tokens": 25}}),
            run_id=run_id,
        )

    stats = tracker.get_stats()
    assert stats["total_tokens"] == 125
    assert stats["models"]["qwen-test"]["calls"] == 1
    assert stats["models"]["qwen-test"]["input"] == 100
    assert stats["by_stage"]["News Analyst"]["calls"] == 1
    assert stats["by_stage"]["News Analyst"]["total"] == 125
    assert stats["by_stage"]["News Analyst"]["models"]["qwen-test"]["output"] == 25


def test_token_tracker_keeps_estimate_when_usage_missing():
    tracker = TokenTracker("task-2")
    run_id = uuid4()

    tracker.on_llm_start(
        {},
        ["长" * 100],
        run_id=run_id,
        invocation_params={"model": "no-usage-model"},
        metadata={"token_stage": "Risk Judge"},
    )
    tracker.on_llm_end(
        SimpleNamespace(generations=[[SimpleNamespace(text="结果" * 20)]]),
        run_id=run_id,
    )

    stats = tracker.get_stats()
    assert stats["total_tokens"] == 0
    assert stats["total_estimated_tokens"] > 0
    assert stats["by_stage"]["Risk Judge"]["estimated_total"] > 0
    assert stats["by_stage"]["Risk Judge"]["observed_token_calls"] == 0
