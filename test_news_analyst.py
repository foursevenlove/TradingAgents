#!/usr/bin/env python3
"""专门测试新闻分析师的独立脚本。

用法:
    python test_news_analyst.py <ticker> [trade_date]

示例:
    python test_news_analyst.py 688347.SH
    python test_news_analyst.py 600519.SH 2026-04-30
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from tradingagents.llm_clients import create_llm_client
from tradingagents.llm_clients.validators import get_default_settings
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.utils.agent_utils import (
    get_company_news,
    get_industry_news,
    get_policy_news,
)
from langchain_core.messages import ToolMessage, HumanMessage


def _create_llm():
    """创建 quick_thinking_llm。"""
    settings = get_default_settings()
    provider = settings.get("provider", "alibaba")
    model = settings.get("quick_think_llm", "deepseek-v4-flash")
    kwargs = {"temperature": 0.1}

    if provider in ("alibaba", "bailian", "dashscope"):
        enable_thinking = DEFAULT_CONFIG.get("enable_thinking")
        if enable_thinking:
            kwargs["enable_thinking"] = True
            max_tokens = DEFAULT_CONFIG.get("max_thinking_tokens")
            if max_tokens:
                kwargs["max_thinking_tokens"] = max_tokens

    client = create_llm_client(provider, model, **kwargs)
    return client.get_llm()


TOOL_FUNC_MAP = {
    "get_company_news": get_company_news,
    "get_industry_news": get_industry_news,
    "get_policy_news": get_policy_news,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    trade_date = sys.argv[2] if len(sys.argv) > 2 else None

    if trade_date is None:
        from datetime import date
        trade_date = date.today().isoformat()

    print(f"{'='*70}")
    print(f"新闻分析师测试: {ticker} | 日期: {trade_date}")
    print(f"{'='*70}")

    llm = _create_llm()
    analyst_node = create_news_analyst(llm)

    propagator = Propagator()
    state = propagator.create_initial_state(ticker, trade_date)
    state["messages"] = [HumanMessage(content=ticker)]

    max_rounds = 4
    for i in range(max_rounds):
        print(f"\n[Round {i+1}] Analyst node running...")
        result = analyst_node(state)

        if "messages" in result:
            state["messages"] = result["messages"]

        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", None)

        if not tool_calls:
            print(f"[Round {i+1}] No tool calls — analysis complete.")
            break

        print(f"[Round {i+1}] Tool calls: {[tc['name'] for tc in tool_calls]}")

        tool_messages = []
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            tool_id = tc["id"]

            print(f"\n  → Executing {tool_name}({tool_args})")
            try:
                func = TOOL_FUNC_MAP[tool_name]
                if hasattr(func, 'invoke'):
                    output = func.invoke(tool_args)
                else:
                    output = func(**tool_args)
            except Exception as e:
                output = f"Error: {type(e).__name__}: {str(e)}"
                print(f"  ✗ Failed: {output}")
            else:
                out_str = str(output)
                MAX_LEN = 500000
                if len(out_str) > MAX_LEN:
                    out_str = out_str[:MAX_LEN] + f"\n\n... [truncated: {len(out_str)} chars total]"
                    output = out_str
                print(f"  ✓ Success ({len(out_str)} chars)")

            tool_messages.append(
                ToolMessage(content=str(output), tool_call_id=tool_id, name=tool_name)
            )

        state["messages"] = state["messages"] + tool_messages

    # 输出最终报告
    report = result.get("news_report", "")
    if not report and hasattr(last_msg, 'content'):
        report = last_msg.content

    print(f"\n{'='*70}")
    print("FINAL REPORT (news_report)")
    print(f"{'='*70}\n")
    print(report if report else "(empty report)")
    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
