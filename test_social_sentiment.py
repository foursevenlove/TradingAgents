#!/usr/bin/env python3
"""Deterministic tests for the free social-sentiment proxy pipeline."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda


ROOT = Path(__file__).resolve().parent
SOCIAL_ANALYST_PATH = (
    ROOT / "tradingagents" / "agents" / "analysts" / "social_media_analyst.py"
)


class FakeLLM:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.bound_tool_names: list[str] = []
        self.invoked_messages = None

    def bind_tools(self, tools):
        self.bound_tool_names = [tool.name for tool in tools]

        def invoke(messages):
            self.invoked_messages = getattr(messages, "messages", messages)
            return self.response

        return RunnableLambda(invoke)


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


def test_social_analyst_filters_non_social_tool_messages_before_llm():
    module = load_social_analyst_isolated()
    market_tool = ToolMessage(
        content="融资余额20亿，市场工具结果不应进入社交分析师",
        tool_call_id="market_tool_call",
        name="get_margin_trading",
    )
    social_call = {
        "name": "get_social_sentiment",
        "args": {
            "ticker": "600000.SH",
            "start_date": "2026-05-12",
            "end_date": "2026-05-15",
        },
        "id": "call_get_social_sentiment_test",
    }
    social_ai = AIMessage(content="", tool_calls=[social_call])
    social_tool = ToolMessage(
        content="source,metric_name,current_value\n东方财富人气,当前排名,12",
        tool_call_id=social_call["id"],
        name="get_social_sentiment",
    )
    fake_llm = FakeLLM(AIMessage(content="最终社交热度报告"))
    analyst = module.create_social_media_analyst(fake_llm)

    analyst(
        {
            "trade_date": "2026-05-15",
            "company_of_interest": "600000.SH",
            "messages": [
                HumanMessage(content="600000.SH"),
                market_tool,
                social_ai,
                social_tool,
            ],
        }
    )

    assert market_tool not in fake_llm.invoked_messages
    assert social_ai in fake_llm.invoked_messages
    assert social_tool in fake_llm.invoked_messages


def test_dataflow_routes_social_sentiment_to_akshare_only():
    interface = importlib.import_module("tradingagents.dataflows.interface")

    assert interface.get_category_for_method("get_social_sentiment") == "news_data"
    assert list(interface.VENDOR_METHODS["get_social_sentiment"].keys()) == ["akshare"]


def test_social_rows_keep_structured_columns_and_all_rows():
    akshare_social = importlib.import_module("tradingagents.dataflows.akshare_social")
    df = pd.DataFrame(
        [
            {"代码": f"60000{i}", "名称": f"股票{i}", "排名": i}
            for i in range(1, 8)
        ]
    )

    rows = akshare_social._rows_from_frame(
        "测试来源",
        df,
        ticker="600001.SH",
        stock_code="600001",
        start_date="2026-05-12",
        end_date="2026-05-15",
    )

    assert len(rows) == 7
    assert rows[0]["source"] == "测试来源"
    assert rows[0]["metric_name"] == "row_0"
    assert rows[0]["代码"] == "600001"
    assert rows[0]["名称"] == "股票1"
    assert rows[0]["排名"] == 1
    assert rows[0]["is_target_stock"] == "是"
    assert rows[0]["requested_start_date"] == "2026-05-12"
    assert rows[0]["requested_end_date"] == "2026-05-15"
    assert "value" not in rows[0]
    assert "detail" not in rows[0]


def test_social_rows_pivot_item_value_tables_to_single_record():
    akshare_social = importlib.import_module("tradingagents.dataflows.akshare_social")
    df = pd.DataFrame(
        [
            {"item": "srcSecurityCode", "value": "SH688347"},
            {"item": "rank", "value": 700},
            {"item": "calcTime", "value": "2026-05-16 13:12:00"},
        ]
    )

    rows = akshare_social._rows_from_frame(
        "东方财富个股人气榜",
        df,
        ticker="688347.SH",
        stock_code="688347",
        start_date="2026-04-26",
        end_date="2026-04-29",
    )

    assert len(rows) == 1
    assert rows[0]["metric_name"] == "snapshot"
    assert rows[0]["srcSecurityCode"] == "SH688347"
    assert rows[0]["rank"] == 700
    assert rows[0]["data_time"] == "2026-05-16 13:12:00"
    assert rows[0]["is_target_stock"] == "是"
    assert rows[0]["is_in_requested_range"] == "否"


def test_social_rows_can_mark_target_scoped_sources_without_code_column():
    akshare_social = importlib.import_module("tradingagents.dataflows.akshare_social")
    df = pd.DataFrame([{"时间": "2026-05-16 00:00:00", "排名": 557}])

    rows = akshare_social._rows_from_frame(
        "东方财富人气实时变动",
        df,
        ticker="688347.SH",
        stock_code="688347",
        start_date="2026-04-26",
        end_date="2026-04-29",
        source_targets_ticker=True,
    )

    assert rows[0]["is_target_stock"] == "是"
    assert "未直接命中目标股票" not in rows[0]["limitation"]
