"""CLI commands for stock recommendation."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from tradingagents.recommendation import DailyRecommender, ThemeExtractor, StockScreener, WeeklyRecommender

console = Console()

recommend_app = typer.Typer(
    name="recommend",
    help="股票推荐命令：每日热点追踪、每周深度推荐",
)


@recommend_app.command("daily")
def recommend_daily(
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="交易日期 (YYYY-MM-DD)，默认为今天"
    ),
    max_themes: int = typer.Option(5, "--themes", "-t", help="最大主题数量"),
    max_stocks: int = typer.Option(5, "--stocks", "-s", help="每个主题最大股票数"),
    min_amount: float = typer.Option(1e8, "--amount", "-a", help="最小成交额（元）"),
    with_analysis: bool = typer.Option(
        False, "--analyze", help="运行深度分析验证（使用市场+新闻分析师）"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="输出文件路径（保存为Markdown）"
    ),
    json_output: bool = typer.Option(False, "--json", help="输出JSON格式"),
):
    """每日股票推荐：基于当日新闻热点+涨停股池筛选。

    流程：
    1. 从Tushare获取当日财经新闻
    2. LLM提取投资主题（只给方向，不给股票代码）
    3. 从当日涨幅榜筛选高成交量股票
    4. 将主题关键词匹配到行业，筛选相关股票
    5. 可选：运行深度分析验证（市场+新闻分析师）

    示例：
        python -m cli.main recommend daily
        python -m cli.main recommend daily --date 2026-05-10 --themes 3 --stocks 5
        python -m cli.main recommend daily --analyze  # 启用深度分析验证
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    console.print(f"\n[bold cyan]每日股票推荐[/bold cyan] - {trade_date}")
    console.print(f"最大主题: {max_themes}, 每主题最大股票: {max_stocks}")
    if with_analysis:
        console.print("[yellow]启用深度分析验证（市场+新闻分析师）[/yellow]")

    # Generate recommendations
    recommender = DailyRecommender()
    result = recommender.generate_recommendations(
        trade_date=trade_date,
        max_themes=max_themes,
        max_stocks_per_theme=max_stocks,
        min_amount=min_amount,
        with_deep_analysis=with_analysis,
    )

    # Display themes
    console.print("\n[bold green]今日热点主题[/bold green]")
    themes_table = Table(show_header=True, header_style="bold magenta")
    themes_table.add_column("主题", style="cyan")
    themes_table.add_column("置信度", style="green")
    themes_table.add_column("关键词", style="yellow")

    for theme in result["themes"]:
        themes_table.add_row(
            theme.get("name", ""),
            f"{theme.get('confidence', 0):.0%}",
            ", ".join(theme.get("keywords", [])),
        )

    console.print(themes_table)

    # Display stocks
    console.print("\n[bold green]推荐股票[/bold green]")
    for theme_name, stocks in result["stocks"].items():
        if not stocks:
            continue

        console.print(f"\n[cyan]{theme_name}[/cyan]")
        stocks_table = Table(show_header=True, header_style="bold blue")
        stocks_table.add_column("代码", style="green")
        stocks_table.add_column("名称", style="white")
        stocks_table.add_column("价格", style="yellow")
        stocks_table.add_column("涨幅", style="red")
        stocks_table.add_column("行业", style="dim")

        # Add analysis columns if enabled
        if with_analysis:
            stocks_table.add_column("决策", style="magenta")
            stocks_table.add_column("置信度", style="cyan")

        for stock in stocks:
            row_data = [
                stock.get("code", ""),
                stock.get("name", ""),
                f"{stock.get('price', 0):.2f}",
                f"{stock.get('change_pct', 0):.2f}%",
                stock.get("industry", "")[:20],
            ]
            if with_analysis:
                row_data.extend([
                    stock.get("decision", "-"),
                    f"{stock.get('confidence', 0):.0%}",
                ])
            stocks_table.add_row(*row_data)

        console.print(stocks_table)

    # Output
    if json_output:
        import json
        json_result = {
            "themes": result["themes"],
            "stocks": result["stocks"],
            "analysis": result.get("analysis", {}),
            "timestamp": result["timestamp"],
            "trade_date": result["trade_date"],
        }
        output_content = json.dumps(json_result, ensure_ascii=False, indent=2)
    else:
        output_content = result["summary"]

    if output:
        output_path = Path(output)
        output_path.write_text(output_content, encoding="utf-8")
        console.print(f"\n[green]已保存到: {output_path}[/green]")

    console.print("\n[dim]" + "="*50 + "[/dim]")
    console.print("[dim]免责声明: 本推荐仅供参考，不构成投资建议。[/dim]")


@recommend_app.command("themes")
def show_themes(
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="交易日期 (YYYY-MM-DD)"
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="新闻数量上限"),
):
    """仅显示今日热点主题（不筛选股票）。

    示例：
        python -m cli.main recommend themes
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    console.print(f"\n[bold cyan]今日热点主题[/bold cyan] - {trade_date}")

    extractor = ThemeExtractor()
    news = extractor.get_news_from_tushare(limit=limit)

    console.print(f"获取新闻: {len(news)} 条")

    themes = extractor.extract_themes(news)

    console.print(f"\n提取主题: {len(themes)} 个")

    for i, theme in enumerate(themes, 1):
        console.print(f"\n[bold]{i}. {theme.get('name')}[/bold]")
        console.print(f"  置信度: {theme.get('confidence', 0):.0%}")
        console.print(f"  理由: {theme.get('reason', '')}")
        console.print(f"  关键词: {', '.join(theme.get('keywords', []))}")
        console.print(f"  相关行业: {', '.join(theme.get('related_industries', []))}")


@recommend_app.command("top")
def show_top_gainers(
    min_amount: float = typer.Option(1e8, "--amount", "-a", help="最小成交额"),
    top_n: int = typer.Option(20, "--top", "-t", help="显示数量"),
):
    """仅显示今日涨幅榜（不按主题筛选）。

    示例：
        python -m cli.main recommend top --amount 500000000 --top 10
    """
    console.print("\n[bold cyan]今日涨幅榜[/bold cyan]")

    screener = StockScreener()
    stocks = screener.get_top_gainers(top_n=top_n)

    console.print(f"筛选条件: 成交额 >= {min_amount/1e8:.0f}亿")

    # Filter by amount
    filtered = stocks.copy()
    if "amount" in filtered.columns:
        filtered = filtered[filtered["amount"] >= min_amount]

    console.print(f"符合条件的股票: {len(filtered)} 只")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("排名", style="dim")
    table.add_column("代码", style="green")
    table.add_column("名称", style="white")
    table.add_column("价格", style="yellow")
    table.add_column("涨幅", style="red")
    table.add_column("成交额", style="blue")
    table.add_column("评分", style="cyan")

    for i, row in enumerate(filtered.itertuples(), 1):
        amount_val = getattr(row, "amount", 0) or 0
        table.add_row(
            str(i),
            getattr(row, "code", ""),
            getattr(row, "name", ""),
            f"{getattr(row, 'price', 0):.2f}",
            f"{getattr(row, 'change_pct', 0):.2f}%",
            f"{amount_val/1e8:.1f}亿",
            f"{getattr(row, 'score', 0):.1f}",
        )

    console.print(table)


@recommend_app.command("weekly")
def recommend_weekly(
    week_start: Optional[str] = typer.Option(
        None, "--week", "-w", help="周起始日期 (YYYY-MM-DD)，默认为本周一"
    ),
    max_themes: int = typer.Option(10, "--themes", "-t", help="最大主题数量"),
    max_stocks: int = typer.Option(5, "--stocks", "-s", help="每个主题最大股票数"),
    min_amount: float = typer.Option(5e8, "--amount", "-a", help="最小成交额（元）"),
    max_analysis: int = typer.Option(10, "--analyze", help="最多分析股票数量"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="输出文件路径（保存为Markdown）"
    ),
    json_output: bool = typer.Option(False, "--json", help="输出JSON格式"),
):
    """每周股票推荐：完整pipeline深度分析。

    流程：
    1. 汇聚本周财经新闻（5天）
    2. LLM提取投资主题（周度视角）
    3. 篛选周涨幅≥5%的高成交股票
    4. 将主题匹配到行业
    5. 运行完整分析（4分析师+完整辩论）

    示例：
        python -m cli.main recommend weekly
        python -m cli.main recommend weekly --week 2026-05-04 --themes 5
    """
    from datetime import timedelta

    if week_start is None:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime("%Y-%m-%d")

    week_end_date = datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=4)
    week_end = week_end_date.strftime("%Y-%m-%d")

    console.print(f"\n[bold cyan]每周股票推荐[/bold cyan] - {week_start} 至 {week_end}")
    console.print(f"最大主题: {max_themes}, 每主题最大股票: {max_stocks}")
    console.print(f"完整分析数量: {max_analysis} (全部4分析师)")

    # Generate recommendations
    recommender = WeeklyRecommender()
    result = recommender.generate_recommendations(
        week_start=week_start,
        max_themes=max_themes,
        max_stocks_per_theme=max_stocks,
        min_amount=min_amount,
        max_analysis_stocks=max_analysis,
    )

    # Display themes
    console.print("\n[bold green]本周热点主题[/bold green]")
    themes_table = Table(show_header=True, header_style="bold magenta")
    themes_table.add_column("主题", style="cyan")
    themes_table.add_column("置信度", style="green")
    themes_table.add_column("关键词", style="yellow")

    for theme in result["themes"]:
        themes_table.add_row(
            theme.get("name", ""),
            f"{theme.get('confidence', 0):.0%}",
            ", ".join(theme.get("keywords", [])),
        )

    console.print(themes_table)

    # Display stocks with analysis
    console.print("\n[bold green]推荐股票（完整分析）[/bold green]")
    for theme_name, stocks in result["stocks"].items():
        if not stocks:
            continue

        console.print(f"\n[cyan]{theme_name}[/cyan]")
        stocks_table = Table(show_header=True, header_style="bold blue")
        stocks_table.add_column("代码", style="green")
        stocks_table.add_column("名称", style="white")
        stocks_table.add_column("价格", style="yellow")
        stocks_table.add_column("涨幅", style="red")
        stocks_table.add_column("决策", style="magenta")
        stocks_table.add_column("置信度", style="cyan")

        for stock in stocks:
            stocks_table.add_row(
                stock.get("code", ""),
                stock.get("name", ""),
                f"{stock.get('price', 0):.2f}",
                f"{stock.get('change_pct', 0):.2f}%",
                stock.get("decision", "-"),
                f"{stock.get('confidence', 0):.0%}",
            )

        console.print(stocks_table)

    # Output
    if json_output:
        import json
        json_result = {
            "week_start": result["week_start"],
            "week_end": result["week_end"],
            "themes": result["themes"],
            "stocks": result["stocks"],
            "analysis": result["analysis"],
            "timestamp": result["timestamp"],
        }
        output_content = json.dumps(json_result, ensure_ascii=False, indent=2)
    else:
        output_content = result["summary"]

    if output:
        output_path = Path(output)
        output_path.write_text(output_content, encoding="utf-8")
        console.print(f"\n[green]已保存到: {output_path}[/green]")

    console.print("\n[dim]" + "="*50 + "[/dim]")
    console.print("[dim]免责声明: 本推荐仅供参考，不构成投资建议。[/dim]")