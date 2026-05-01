#!/usr/bin/env python3
"""测试 get_news 接口，标注每条新闻的筛选来源（关键词 vs LLM补充）。

用法:
    python test_get_news.py <ticker> [start_date] [end_date]

示例:
    python test_get_news.py 688347.SH
    python test_get_news.py 600519.SH 2026-04-28 2026-05-01
"""
import sys
import os
import csv
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from tradingagents.dataflows.tushare_news import get_news


def parse_result(raw: str):
    """解析 get_news 返回的 CSV 字符串，分离 header 和数据行。"""
    header_lines = []
    data_lines = []

    for line in raw.split('\n'):
        if line.startswith('#'):
            header_lines.append(line)
        elif line.strip():
            data_lines.append(line)

    # 解析 CSV 数据
    rows = []
    if data_lines:
        reader = csv.DictReader(io.StringIO('\n'.join(data_lines)))
        for row in reader:
            rows.append(row)

    # 从 header 提取元信息
    meta = {}
    for line in header_lines:
        if ':' in line:
            key, _, val = line[2:].partition(':')
            meta[key.strip()] = val.strip()

    return meta, rows


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    start_date = sys.argv[2] if len(sys.argv) > 2 else None
    end_date = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"调用 get_news({ticker}, {start_date}, {end_date}) ...")
    print()

    raw = get_news(ticker, start_date, end_date)
    meta, rows = parse_result(raw)

    # 打印元信息
    print("=" * 70)
    print("元信息")
    print("=" * 70)
    for k, v in meta.items():
        print(f"  {k}: {v}")

    # 提取关键词
    keywords_str = meta.get('Keywords used for filtering', '')
    keywords = [k.strip().strip("'\"") for k in keywords_str.strip('[]').split(',') if k.strip()]
    keywords_lower = [k.lower() for k in keywords]

    keyword_count = int(meta.get('Keyword-filtered results', '0'))
    llm_count_str = meta.get('LLM semantic supplement', '0')
    llm_count = int(llm_count_str) if llm_count_str.isdigit() else 0

    print(f"\n  关键词: {keywords}")
    print(f"  关键词命中: {keyword_count} 条")
    print(f"  LLM补充: {llm_count} 条")
    print(f"  最终结果: {len(rows)} 条")

    # 逐条标注
    print(f"\n{'=' * 70}")
    print("逐条分析")
    print("=" * 70)

    kw_items = []
    llm_items = []

    for i, row in enumerate(rows, 1):
        title = row.get('title', '') or ''
        content = row.get('content', '') or ''
        dt = row.get('datetime', row.get('pub_time', '')) or ''
        source = row.get('data_source', '') or ''
        text = (title + ' ' + content).lower()

        matched_kw = [kw for kw in keywords_lower if kw in text]

        if matched_kw:
            tag = "关键词"
            kw_items.append(i)
        else:
            tag = "LLM补充"
            llm_items.append(i)

        print(f"\n  [{i:>2}] [{tag}] [{source}] {dt[:19]}")
        print(f"       标题: {title[:80]}")
        if matched_kw:
            print(f"       命中: {matched_kw}")
        print(f"       内容: {content}")

    # 汇总
    print(f"\n{'=' * 70}")
    print("汇总")
    print("=" * 70)
    print(f"  关键词命中: {len(kw_items)} 条 — 编号 {kw_items}")
    print(f"  LLM补充:   {len(llm_items)} 条 — 编号 {llm_items}")
    print(f"  总计:      {len(rows)} 条")


if __name__ == "__main__":
    main()
