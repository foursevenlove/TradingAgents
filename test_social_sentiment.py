#!/usr/bin/env python3
"""Deterministic tests for the free social-sentiment proxy pipeline."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda


ROOT = Path(__file__).resolve().parent
SOCIAL_ANALYST_PATH = (
    ROOT / "tradingagents" / "agents" / "analysts" / "social_media_analyst.py"
)


class FakeLLM:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools):
        self.bound_tool_names = [tool.name for tool in tools]
        return RunnableLambda(lambda _messages: self.response)


def load_social_analyst_isolated():
    fake_agent_utils = types.ModuleType("tradingagents.agents.utils.agent_utils")
    fake_agent_utils.get_news = SimpleNamespace(name="get_news")
    fake_agent_utils.get_social_sentiment = SimpleNamespace(name="get_social_sentiment")

    fake_modules = {
        "tradingagents": types.ModuleType("tradingagents"),
        "tradingagents.agents": types.ModuleType("tradingagents.agents"),
        "tradingagents.agents.utils": types.ModuleType("tradingagents.agents.utils"),
        "tradingagents.agents.utils.agent_utils": fake_agent_utils,
        "tradingagents.dataflows": types.ModuleType("tradingagents.dataflows"),
        "tradingagents.dataflows.config": types.ModuleType("tradingagents.dataflows.config"),
    }
    fake_modules["tradingagents.dataflows.config"].get_config = lambda: {}
    saved = {name: sys.modules.get(name) for name in fake_modules}

    try:
        sys.modules.update(fake_modules)
        spec = importlib.util.spec_from_file_location(
            "isolated_social_media_analyst", SOCIAL_ANALYST_PATH
        )
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_social_analyst_forces_free_social_tool_when_llm_skips_tools():
    module = load_social_analyst_isolated()
    fake_llm = FakeLLM(AIMessage(content="模型未调用工具"))
    analyst = module.create_social_media_analyst(fake_llm)

    result = analyst(
        {
            "trade_date": "2026-05-15",
            "company_of_interest": "600000.SH",
            "messages": [],
        }
    )

    assert fake_llm.bound_tool_names == ["get_social_sentiment"]
    forced_message = result["messages"][0]
    assert result["sentiment_report"] == ""
    assert [call["name"] for call in forced_message.tool_calls] == [
        "get_social_sentiment"
    ]
    assert forced_message.tool_calls[0]["args"] == {
        "ticker": "600000.SH",
        "start_date": "2026-05-12",
        "end_date": "2026-05-15",
    }


def test_social_analyst_emits_report_after_social_tool_executed():
    module = load_social_analyst_isolated()
    prior_call = {
        "name": "get_social_sentiment",
        "args": {
            "ticker": "600000.SH",
            "start_date": "2026-05-12",
            "end_date": "2026-05-15",
        },
        "id": "call_get_social_sentiment_test",
    }
    prior_ai = AIMessage(content="", tool_calls=[prior_call])
    tool_message = ToolMessage(
        content="# Free social sentiment proxy\nmetric,value\nrank,12",
        tool_call_id=prior_call["id"],
        name="get_social_sentiment",
    )

    fake_llm = FakeLLM(AIMessage(content="最终社交热度报告"))
    analyst = module.create_social_media_analyst(fake_llm)
    result = analyst(
        {
            "trade_date": "2026-05-15",
            "company_of_interest": "600000.SH",
            "messages": [prior_ai, tool_message],
        }
    )

    assert result["sentiment_report"] == "最终社交热度报告"


def test_dataflow_routes_social_sentiment_to_akshare_only():
    interface = importlib.import_module("tradingagents.dataflows.interface")

    assert interface.get_category_for_method("get_social_sentiment") == "news_data"
    assert list(interface.VENDOR_METHODS["get_social_sentiment"].keys()) == ["akshare"]
