#!/usr/bin/env python3
"""测试三层新闻架构的独立脚本。

分别调用 get_company_news / get_industry_news / get_policy_news，
展示每层的数据量、来源分布和内容样本。

用法:
    python test_three_layer_news.py <ticker> [start_date] [end_date]

示例:
    python test_three_layer_news.py 688347.SH
    python test_three_layer_news.py 600519.SH 2026-04-28 2026-05-01
"""
import sys
import os
import csv
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from tradingagents.dataflows.interface import route_to_vendor


def parse_csv_header(text: str):
    """提取 CSV 中的 header 注释行。"""
    return [line for line in text.split('\n') if line.startswith('#')]


def parse_csv_rows(text: str):
    """解析 CSV 数据行。"""
    lines = [line for line in text.split('\n') if line.strip() and not line.startswith('#')]
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO('\n'.join(lines)))
    return list(reader)


def print_layer(name: str, result: str, max_samples: int = 3):
    """打印单层结果。"""
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")

    header = parse_csv_header(result)
    for line in header:
        print(f"  {line}")

    rows = parse_csv_rows(result)
    print(f"\n  数据行数: {len(rows)}")

    if rows:
        print(f"\n  前 {min(max_samples, len(rows))} 条样本:")
        for i, row in enumerate(rows[:max_samples], 1):
            title = row.get('title', '')[:70]
            source = row.get('data_source', '')
            dt = row.get('datetime', row.get('pub_time', ''))[:19]
            summary = row.get('summary', '')
            print(f"\n  [{i}] [{source}] {dt}")
            print(f"      标题: {title}")
            if summary:
                print(f"      摘要: {summary[:120]}{'...' if len(summary) > 120 else ''}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    start_date = sys.argv[2] if len(sys.argv) > 2 else None
    end_date = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"{'='*70}")
    print(f"三层新闻架构测试: {ticker}")
    print(f"{'='*70}")

    # 第一层
    print("\n[调用 get_company_news ...]")
    r1 = route_to_vendor("get_company_news", ticker, start_date, end_date)
    print_layer("第一层 · 公司直接相关新闻", r1)

    # 第二层
    print("\n[调用 get_industry_news ...]")
    r2 = route_to_vendor("get_industry_news", ticker, start_date, end_date)
    print_layer("第二层 · 产业链/行业新闻", r2)

    # 第三层
    print("\n[调用 get_policy_news ...]")
    r3 = route_to_vendor("get_policy_news", ticker, 3)
    print_layer("第三层 · 政策新闻", r3)

    print(f"\n{'='*70}")
    print("测试完成")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
