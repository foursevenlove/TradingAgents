#!/usr/bin/env python3
"""测试单个分析师的独立脚本。

用法:
    python test_analyst.py <analyst_type> <ticker> [trade_date]

示例:
    python test_analyst.py news 600519.SH
    python test_analyst.py market 000001.SZ 2025-01-15
    python test_analyst.py fundamentals 600000.SH
    python test_analyst.py social 300750.SZ

支持的 analyst_type: news, market, fundamentals, social
"""
import sys
import os

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件中的环境变量
from dotenv import load_dotenv
load_dotenv()

from tradingagents.llm_clients import create_llm_client
from tradingagents.llm_clients.validators import get_default_settings
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator

# 导入四个分析师创建函数
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst

# 导入工具
from tradingagents.agents.utils.agent_utils import (
    get_stock_data, get_indicators,
    get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_pledge_ratio,
    get_news, get_global_news,
    get_company_news, get_industry_news, get_policy_news,
)
from tradingagents.agents.utils.news_data_tools import get_cctv_news, get_insider_transactions
from tradingagents.agents.utils.ashare_market_tools import (
    get_north_bound_flow, get_margin_trading, get_limit_up_down_stats,
    get_dragon_tiger_list, get_block_trade, get_institutional_holdings,
)
from tradingagents.agents.utils.industry_tools import (
    get_sw_industry, get_industry_peers, get_industry_performance,
)
from langchain_core.messages import ToolMessage


ANALYST_CREATORS = {
    "news": create_news_analyst,
    "market": create_market_analyst,
    "fundamentals": create_fundamentals_analyst,
    "social": create_social_media_analyst,
}

# 工具函数映射（用于手动执行）
TOOL_FUNC_MAP = {
    "get_news": get_news,
    "get_global_news": get_global_news,
    "get_cctv_news": get_cctv_news,
    "get_company_news": get_company_news,
    "get_industry_news": get_industry_news,
    "get_policy_news": get_policy_news,
    "get_insider_transactions": get_insider_transactions,
    "get_stock_data": get_stock_data,
    "get_indicators": get_indicators,
    "get_fundamentals": get_fundamentals,
    "get_balance_sheet": get_balance_sheet,
    "get_cashflow": get_cashflow,
    "get_income_statement": get_income_statement,
    "get_pledge_ratio": get_pledge_ratio,
    "get_north_bound_flow": get_north_bound_flow,
    "get_margin_trading": get_margin_trading,
    "get_limit_up_down_stats": get_limit_up_down_stats,
    "get_dragon_tiger_list": get_dragon_tiger_list,
    "get_block_trade": get_block_trade,
    "get_institutional_holdings": get_institutional_holdings,
    "get_sw_industry": get_sw_industry,
    "get_industry_peers": get_industry_peers,
    "get_industry_performance": get_industry_performance,
}


def _create_llm():
    """创建 quick_thinking_llm。"""
    settings = get_default_settings()
    provider = settings.get("provider", "alibaba")
    model = settings.get("quick_think_llm", "deepseek-v4-flash")
    kwargs = {"temperature": 0.1}

    # provider-specific kwargs
    if provider in ("alibaba", "bailian", "dashscope"):
        enable_thinking = DEFAULT_CONFIG.get("enable_thinking")
        if enable_thinking:
            kwargs["enable_thinking"] = True
            max_tokens = DEFAULT_CONFIG.get("max_thinking_tokens")
            if max_tokens:
                kwargs["max_thinking_tokens"] = max_tokens

    client = create_llm_client(provider, model, **kwargs)
    return client.get_llm()


def _run_analyst(analyst_type, ticker, trade_date):
    """运行单个分析师并输出报告。"""
    print(f"\n{'='*60}")
    print(f"分析师: {analyst_type} | 标的: {ticker} | 日期: {trade_date}")
    print(f"{'='*60}\n")

    llm = _create_llm()
    creator = ANALYST_CREATORS[analyst_type]
    analyst_node = creator(llm)

    # 构造初始 state
    propagator = Propagator()
    state = propagator.create_initial_state(ticker, trade_date)

    # 初始化 messages（分析师需要）
    from langchain_core.messages import HumanMessage
    state["messages"] = [HumanMessage(content=ticker)]

    max_rounds = 2
    for i in range(max_rounds):
        print(f"[Round {i+1}] Analyst node running...")
        result = analyst_node(state)

        # 更新 state
        if "messages" in result:
            state["messages"] = result["messages"]

        # 检查是否有 tool_calls
        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", None)

        if not tool_calls:
            print(f"[Round {i+1}] No tool calls — analysis complete.\n")
            break

        print(f"[Round {i+1}] Tool calls: {[tc['name'] for tc in tool_calls]}\n")

        # 手动执行工具
        tool_messages = []
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            tool_id = tc["id"]

            print(f"  → Executing {tool_name}({tool_args})")
            try:
                func = TOOL_FUNC_MAP[tool_name]
                # LangChain StructuredTool needs .invoke() not direct call
                if hasattr(func, 'invoke'):
                    output = func.invoke(tool_args)
                else:
                    output = func(**tool_args)
            except Exception as e:
                output = f"Error: {type(e).__name__}: {str(e)}"
                print(f"  ✗ Failed: {output}")
            else:
                out_str = str(output)
                # Truncate very large outputs to avoid JSON overflow
                MAX_LEN = 500000
                if len(out_str) > MAX_LEN:
                    out_str = out_str[:MAX_LEN] + f"\n\n... [truncated: {len(out_str)} chars total]"
                    output = out_str
                print(f"  ✓ Success ({len(out_str)} chars)")

            tool_messages.append(ToolMessage(content=str(output), tool_call_id=tool_id))

        state["messages"] = state["messages"] + tool_messages
        print()

    # 输出最终报告
    report_key = {
        "news": "news_report",
        "market": "market_report",
        "fundamentals": "fundamentals_report",
        "social": "sentiment_report",
    }[analyst_type]

    report = result.get(report_key, "")
    if not report and hasattr(last_msg, 'content'):
        report = last_msg.content

    print(f"\n{'='*60}")
    print(f"FINAL REPORT ({report_key})")
    print(f"{'='*60}\n")
    print(report if report else "(empty report)")
    print(f"\n{'='*60}\n")

    return report


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    analyst_type = sys.argv[1].lower()
    ticker = sys.argv[2]
    trade_date = sys.argv[3] if len(sys.argv) > 3 else None

    if analyst_type not in ANALYST_CREATORS:
        print(f"错误: 不支持的分析师类型 '{analyst_type}'")
        print(f"支持的类型: {', '.join(ANALYST_CREATORS.keys())}")
        sys.exit(1)

    if trade_date is None:
        from datetime import date
        trade_date = date.today().isoformat()

    _run_analyst(analyst_type, ticker, trade_date)


if __name__ == "__main__":
    main()
