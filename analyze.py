#!/usr/bin/env python3
"""
TradingAgents 非交互式命令行工具

用法:
    python analyze.py --ticker 000001
    python analyze.py --ticker 000001 --date 2026-03-22
    python analyze.py --ticker 000001 --depth 3
    python analyze.py --ticker 000001 --analysts market,news,fundamentals

参数:
    --ticker: 股票代码（必需），如 000001.SZ, 600000.SH
    --date: 分析日期（可选），格式 YYYY-MM-DD，默认今天
    --depth: 研究深度（可选），1-5，默认2
    --analysts: 分析师列表（可选），逗号分隔，默认全部
                可选: market, social, news, fundamentals
    --provider: LLM提供商（可选），默认 minimax
    --shallow: 快速思考模型（可选），默认根据provider自动选择
    --deep: 深度思考模型（可选），默认根据provider自动选择
"""

import argparse
import datetime
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from cli.stats_handler import StatsCallbackHandler

# Analyst order (same as CLI)
ANALYST_ORDER = ["market", "social", "news", "fundamentals"]

# Default models for each provider
DEFAULT_MODELS = {
    "minimax": {
        "shallow": "MiniMax-M2.5",
        "deep": "MiniMax-M2.7",
        "url": "https://api.minimax.chat/v1"
    },
    "aliyun_coding_plan": {
        "shallow": "kimi-k2.5",
        "deep": "kimi-k2.5",
        "url": "https://coding.dashscope.aliyuncs.com/v1"
    },
}


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="TradingAgents 非交互式股票分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--ticker",
        required=True,
        help="股票代码，如 000001, 600000"
    )

    parser.add_argument(
        "--date",
        default=datetime.datetime.now().strftime("%Y-%m-%d"),
        help="分析日期，格式 YYYY-MM-DD（默认: 今天）"
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        choices=[1, 2, 3, 4, 5],
        help="研究深度，1-5（默认: 2）"
    )

    parser.add_argument(
        "--analysts",
        default="market,social,news,fundamentals",
        help="分析师列表，逗号分隔（默认: 全部）"
    )

    parser.add_argument(
        "--provider",
        default="minimax",
        choices=list(DEFAULT_MODELS.keys()),
        help="LLM提供商（默认: minimax）"
    )

    parser.add_argument(
        "--shallow",
        help="快速思考模型（可选，默认根据provider自动选择）"
    )

    parser.add_argument(
        "--deep",
        help="深度思考模型（可选，默认根据provider自动选择）"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式，只输出最终结果路径"
    )

    return parser.parse_args()


def validate_ticker(ticker: str) -> bool:
    """验证股票代码格式"""
    if not ticker:
        return False
    return True


def validate_date(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_analysts(analysts_str: str) -> list:
    """解析分析师列表"""
    analysts = [a.strip().lower() for a in analysts_str.split(",")]
    valid_analysts = [a for a in analysts if a in ANALYST_ORDER]

    if not valid_analysts:
        print(f"错误: 无效的分析师列表。可选: {', '.join(ANALYST_ORDER)}")
        sys.exit(1)

    # 按照预定义顺序排序
    return [a for a in ANALYST_ORDER if a in valid_analysts]


def run_analysis_non_interactive(args):
    """运行非交互式分析"""

    # 验证参数
    if not validate_ticker(args.ticker):
        print(f"错误: 无效的股票代码: {args.ticker}")
        sys.exit(1)

    if not validate_date(args.date):
        print(f"错误: 无效的日期格式: {args.date}，应为 YYYY-MM-DD")
        sys.exit(1)

    # 解析分析师列表
    selected_analysts = parse_analysts(args.analysts)

    # 获取模型配置
    provider_config = DEFAULT_MODELS.get(args.provider.lower())
    shallow_model = args.shallow or provider_config["shallow"]
    deep_model = args.deep or provider_config["deep"]
    backend_url = provider_config["url"]

    if not args.quiet:
        print(f"\n{'='*60}")
        print(f"TradingAgents 股票分析")
        print(f"{'='*60}")
        print(f"股票代码: {args.ticker}")
        print(f"分析日期: {args.date}")
        print(f"研究深度: {args.depth}")
        print(f"分析师: {', '.join(selected_analysts)}")
        print(f"LLM提供商: {args.provider}")
        print(f"快速模型: {shallow_model}")
        print(f"深度模型: {deep_model}")
        print(f"{'='*60}\n")

    # 创建配置
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = args.depth
    config["max_risk_discuss_rounds"] = args.depth
    config["quick_think_llm"] = shallow_model
    config["deep_think_llm"] = deep_model
    config["backend_url"] = backend_url
    config["llm_provider"] = args.provider.lower()

    # 创建统计回调处理器
    stats_handler = StatsCallbackHandler()

    # 初始化图
    if not args.quiet:
        print("正在初始化分析图...")

    graph = TradingAgentsGraph(
        selected_analysts,
        config=config,
        debug=False,  # 非交互模式关闭debug
        callbacks=[stats_handler],
    )

    # 创建结果目录
    results_dir = Path(config["results_dir"]) / args.ticker / args.date
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"结果目录: {results_dir}")
        print("\n开始分析...\n")

    # 运行分析
    try:
        result, signal = graph.propagate(
            company_name=args.ticker,
            trade_date=args.date
        )

        # 保存最终报告
        final_report_path = results_dir / f"{args.ticker}_{args.date}_final_report.md"

        # 从结果中提取最终报告 - 从final_trade_decision中获取
        if result and "final_trade_decision" in result:
            with open(final_report_path, "w", encoding="utf-8") as f:
                f.write(result["final_trade_decision"])

        if not args.quiet:
            print(f"\n{'='*60}")
            print("分析完成！")
            print(f"交易信号: {signal}")
            print(f"{'='*60}")
            print(f"最终报告: {final_report_path}")
            print(f"详细报告: {report_dir}")
            print(f"{'='*60}\n")
        else:
            # 静默模式只输出报告路径
            print(final_report_path)

        return 0

    except KeyboardInterrupt:
        print("\n\n分析被用户中断")
        return 1
    except Exception as e:
        print(f"\n错误: 分析失败")
        print(f"错误信息: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """主函数"""
    args = parse_arguments()
    return run_analysis_non_interactive(args)


if __name__ == "__main__":
    sys.exit(main())
