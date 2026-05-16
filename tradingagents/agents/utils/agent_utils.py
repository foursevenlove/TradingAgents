from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_pledge_ratio,
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
    get_company_news,
    get_industry_news,
    get_policy_news,
)
from tradingagents.agents.utils.social_data_tools import (
    get_social_sentiment,
)
from tradingagents.agents.utils.ashare_market_tools import (
    get_north_bound_flow,
    get_margin_trading,
    get_limit_up_down_stats,
    get_dragon_tiger_list,
    get_block_trade,
    get_institutional_holdings,
)
from tradingagents.agents.utils.industry_tools import (
    get_sw_industry,
    get_industry_peers,
    get_industry_performance,
)

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility.

        Only removes AI and Human messages to avoid ToolMessage ID conflicts.
        ToolMessages are handled separately by LangGraph's tool nodes.
        """
        messages = state.get("messages", [])

        # Only remove messages that have a valid id and are not ToolMessages
        # ToolMessages may have been processed by tool nodes and could cause ID conflicts
        removal_operations = []
        for m in messages:
            # Check if message has an id attribute and is not a ToolMessage
            if hasattr(m, "id") and m.id:
                msg_type = type(m).__name__
                # Skip ToolMessage as it may have been processed elsewhere
                if msg_type != "ToolMessage":
                    removal_operations.append(RemoveMessage(id=m.id))

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
