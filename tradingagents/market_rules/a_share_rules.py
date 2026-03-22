"""A-share market trading rules and regulations.

This module implements trading rules specific to the Chinese A-share market,
including T+1 trading system, price limit checks, trading hours, and cost calculations.
"""

from datetime import datetime, time
from typing import Dict, Tuple, Optional
from enum import Enum


class StockType(Enum):
    """A-share stock types with different price limit rules."""
    MAIN_BOARD = "main_board"  # 主板：±10%
    ST_STOCK = "st_stock"  # ST股票：±5%
    STAR_MARKET = "star_market"  # 科创板：±20%
    CHINEXT = "chinext"  # 创业板：±20%


def get_stock_type(symbol: str) -> StockType:
    """Determine stock type based on symbol.

    Args:
        symbol: Stock symbol (e.g., "000001.SZ", "600000.SH", "688001.SH")

    Returns:
        StockType enum value

    Examples:
        >>> get_stock_type("000001.SZ")
        StockType.MAIN_BOARD
        >>> get_stock_type("688001.SH")
        StockType.STAR_MARKET
    """
    symbol = symbol.upper().strip()

    # Extract code
    if "." in symbol:
        code, _ = symbol.split(".")
    else:
        code = symbol

    # Check for ST stocks (simplified - in reality need to check company status)
    if code.startswith("ST") or "*ST" in code:
        return StockType.ST_STOCK

    # STAR Market (科创板): 688xxx
    if code.startswith("688"):
        return StockType.STAR_MARKET

    # ChiNext (创业板): 300xxx
    if code.startswith("300"):
        return StockType.CHINEXT

    # Main board: 000xxx, 001xxx, 002xxx (Shenzhen), 600xxx, 601xxx, 603xxx (Shanghai)
    return StockType.MAIN_BOARD


def check_price_limit(
    current_price: float,
    prev_close: float,
    stock_type: StockType = StockType.MAIN_BOARD
) -> Dict[str, any]:
    """Check if price is within allowed limits.

    Args:
        current_price: Current or target price
        prev_close: Previous closing price
        stock_type: Type of stock (determines limit percentage)

    Returns:
        Dictionary with check results:
        - is_valid: bool, whether price is within limits
        - limit_up: float, upper price limit
        - limit_down: float, lower price limit
        - change_pct: float, percentage change
        - message: str, explanation message
    """
    # Determine price limit percentage based on stock type
    limit_pct = {
        StockType.MAIN_BOARD: 0.10,  # ±10%
        StockType.ST_STOCK: 0.05,  # ±5%
        StockType.STAR_MARKET: 0.20,  # ±20%
        StockType.CHINEXT: 0.20,  # ±20%
    }[stock_type]

    # Calculate price limits
    limit_up = round(prev_close * (1 + limit_pct), 2)
    limit_down = round(prev_close * (1 - limit_pct), 2)

    # Calculate change percentage
    change_pct = ((current_price - prev_close) / prev_close) * 100

    # Check if within limits
    is_valid = limit_down <= current_price <= limit_up

    # Generate message
    if not is_valid:
        if current_price > limit_up:
            message = f"价格{current_price}超过涨停板{limit_up}（涨幅{limit_pct*100}%）"
        else:
            message = f"价格{current_price}低于跌停板{limit_down}（跌幅{limit_pct*100}%）"
    else:
        message = f"价格{current_price}在合理范围内（涨跌幅{change_pct:.2f}%）"

    return {
        "is_valid": is_valid,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "change_pct": change_pct,
        "limit_pct": limit_pct * 100,
        "message": message,
    }


def check_trading_time(timestamp: Optional[datetime] = None) -> Dict[str, any]:
    """Check if current time is within trading hours.

    A-share trading hours:
    - Morning: 9:30 - 11:30
    - Afternoon: 13:00 - 15:00
    - Call auction: 9:15 - 9:25 (opening), 14:57 - 15:00 (closing)

    Args:
        timestamp: Datetime to check (default: current time)

    Returns:
        Dictionary with check results:
        - is_trading_time: bool
        - is_call_auction: bool
        - session: str, "morning", "afternoon", "call_auction", or "closed"
        - message: str
    """
    if timestamp is None:
        timestamp = datetime.now()

    current_time = timestamp.time()

    # Define trading sessions
    call_auction_open_start = time(9, 15)
    call_auction_open_end = time(9, 25)
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    call_auction_close_start = time(14, 57)
    afternoon_end = time(15, 0)

    # Check sessions
    if call_auction_open_start <= current_time < call_auction_open_end:
        return {
            "is_trading_time": True,
            "is_call_auction": True,
            "session": "call_auction_open",
            "message": "开盘集合竞价时间（9:15-9:25）",
        }
    elif morning_start <= current_time < morning_end:
        return {
            "is_trading_time": True,
            "is_call_auction": False,
            "session": "morning",
            "message": "上午交易时间（9:30-11:30）",
        }
    elif afternoon_start <= current_time < call_auction_close_start:
        return {
            "is_trading_time": True,
            "is_call_auction": False,
            "session": "afternoon",
            "message": "下午交易时间（13:00-14:57）",
        }
    elif call_auction_close_start <= current_time < afternoon_end:
        return {
            "is_trading_time": True,
            "is_call_auction": True,
            "session": "call_auction_close",
            "message": "收盘集合竞价时间（14:57-15:00）",
        }
    else:
        return {
            "is_trading_time": False,
            "is_call_auction": False,
            "session": "closed",
            "message": "非交易时间",
        }


def apply_t_plus_1_rule(
    holdings: Dict[str, Dict],
    symbol: str,
    action: str = "sell"
) -> Dict[str, any]:
    """Apply T+1 trading rule check.

    T+1 rule: Stocks bought today cannot be sold until the next trading day.

    Args:
        holdings: Dictionary of current holdings
            Format: {symbol: {"quantity": int, "buy_date": str, ...}}
        symbol: Stock symbol to check
        action: Trading action ("buy" or "sell")

    Returns:
        Dictionary with check results:
        - is_allowed: bool
        - message: str
        - buy_date: str (if applicable)
    """
    if action.lower() != "sell":
        return {
            "is_allowed": True,
            "message": "买入操作不受T+1限制",
        }

    if symbol not in holdings:
        return {
            "is_allowed": False,
            "message": f"未持有{symbol}，无法卖出",
        }

    holding = holdings[symbol]
    buy_date_str = holding.get("buy_date")

    if not buy_date_str:
        # If no buy date, assume it's old holding (can sell)
        return {
            "is_allowed": True,
            "message": "持仓可以卖出",
        }

    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()

    if buy_date >= today:
        return {
            "is_allowed": False,
            "message": f"T+1限制：{symbol}于{buy_date_str}买入，次日才能卖出",
            "buy_date": buy_date_str,
        }

    return {
        "is_allowed": True,
        "message": f"{symbol}可以卖出（买入日期：{buy_date_str}）",
        "buy_date": buy_date_str,
    }


def calculate_trading_cost(
    price: float,
    quantity: int,
    action: str = "buy"
) -> Dict[str, float]:
    """Calculate trading costs for A-share transactions.

    Costs include:
    - Commission (佣金): ~0.03% (both buy and sell, min 5 yuan)
    - Stamp duty (印花税): 0.1% (sell only)
    - Transfer fee (过户费): 0.001% (both buy and sell)

    Args:
        price: Stock price
        quantity: Number of shares (must be multiple of 100)
        action: "buy" or "sell"

    Returns:
        Dictionary with cost breakdown:
        - total_amount: float, total transaction amount
        - commission: float
        - stamp_duty: float
        - transfer_fee: float
        - total_cost: float
        - net_amount: float (amount after costs)
    """
    # Calculate base amount
    total_amount = price * quantity

    # Commission (佣金): typically 0.03%, minimum 5 yuan
    commission_rate = 0.0003
    commission = max(total_amount * commission_rate, 5.0)

    # Stamp duty (印花税): 0.1% on sell only
    stamp_duty_rate = 0.001
    stamp_duty = total_amount * stamp_duty_rate if action.lower() == "sell" else 0.0

    # Transfer fee (过户费): 0.001% both ways
    transfer_fee_rate = 0.00001
    transfer_fee = total_amount * transfer_fee_rate

    # Total cost
    total_cost = commission + stamp_duty + transfer_fee

    # Net amount
    if action.lower() == "buy":
        net_amount = total_amount + total_cost  # Pay more when buying
    else:
        net_amount = total_amount - total_cost  # Receive less when selling

    return {
        "total_amount": round(total_amount, 2),
        "commission": round(commission, 2),
        "stamp_duty": round(stamp_duty, 2),
        "transfer_fee": round(transfer_fee, 2),
        "total_cost": round(total_cost, 2),
        "net_amount": round(net_amount, 2),
        "cost_rate": round((total_cost / total_amount) * 100, 4),
    }


class AShareTradingRules:
    """Comprehensive A-share trading rules checker."""

    @staticmethod
    def validate_trade(
        symbol: str,
        action: str,
        price: float,
        quantity: int,
        prev_close: float,
        holdings: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, any]:
        """Validate a trade against all A-share rules.

        Args:
            symbol: Stock symbol
            action: "buy" or "sell"
            price: Target price
            quantity: Number of shares
            prev_close: Previous closing price
            holdings: Current holdings (for T+1 check)
            timestamp: Trade timestamp (default: now)

        Returns:
            Dictionary with validation results:
            - is_valid: bool, overall validity
            - violations: list of violation messages
            - warnings: list of warning messages
            - details: dict with detailed checks
        """
        violations = []
        warnings = []
        details = {}

        # 1. Check stock type
        stock_type = get_stock_type(symbol)
        details["stock_type"] = stock_type.value

        # 2. Check price limits
        price_check = check_price_limit(price, prev_close, stock_type)
        details["price_check"] = price_check
        if not price_check["is_valid"]:
            violations.append(price_check["message"])
        elif abs(price_check["change_pct"]) > price_check["limit_pct"] * 0.9:
            warnings.append(f"价格接近涨跌停板（{price_check['change_pct']:.2f}%）")

        # 3. Check trading time
        time_check = check_trading_time(timestamp)
        details["time_check"] = time_check
        if not time_check["is_trading_time"]:
            violations.append(time_check["message"])
        elif time_check["is_call_auction"]:
            warnings.append(time_check["message"])

        # 4. Check T+1 rule (for sell orders)
        if action.lower() == "sell" and holdings:
            t1_check = apply_t_plus_1_rule(holdings, symbol, action)
            details["t1_check"] = t1_check
            if not t1_check["is_allowed"]:
                violations.append(t1_check["message"])

        # 5. Check quantity (must be multiple of 100 for A-shares)
        if quantity % 100 != 0:
            violations.append(f"交易数量必须是100的整数倍，当前数量：{quantity}")

        # 6. Calculate costs
        cost_details = calculate_trading_cost(price, quantity, action)
        details["cost"] = cost_details
        if cost_details["cost_rate"] > 0.5:
            warnings.append(f"交易成本较高（{cost_details['cost_rate']:.2f}%）")

        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "details": details,
        }
