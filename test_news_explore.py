#!/usr/bin/env python3
"""探索 news 接口的关键词命中分布和追溯策略。

测试内容：
1. 分段拉取 news(sina) 3天，统计每个时间段的关键词命中数
2. 继续往前追溯（超过3天），看命中数是否增加
3. 对比不同股票的命中率差异（热门股 vs 冷门股）
4. 探索 major_news 的命中分布

用法:
    python test_news_explore.py <ticker> [days]

示例:
    python test_news_explore.py 688347.SH 3
    python test_news_explore.py 600667.SH 3
"""
import sys
import os
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import tushare as ts
import pandas as pd


def get_pro():
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        print("ERROR: TUSHARE_TOKEN not set")
        sys.exit(1)
    return ts.pro_api(token)


def get_stock_name(pro, ticker):
    try:
        df = pro.stock_basic(ts_code=ticker, fields='ts_code,name,industry')
        if not df.empty:
            return df.iloc[0]['name'], df.iloc[0].get('industry', '')
    except Exception as e:
        print(f"  获取股票名称失败: {e}")
    return None, None


def strip_html(text):
    """简单去除HTML标签"""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', str(text))


def match_keywords(row, keywords_lower):
    """检查一行是否匹配关键词，返回匹配到的关键词"""
    title = str(row.get('title', '')).lower()
    content = strip_html(str(row.get('content', ''))).lower()
    text = title + ' ' + content
    matched = []
    for kw in keywords_lower:
        if kw in text:
            matched.append(kw)
    return matched


# ============================================================
# 测试1: news 分段拉取，关键词命中的时间分布
# ============================================================
def test_news_segment_distribution(pro, ticker, company_name, keywords, days=3):
    print(f"\n{'='*60}")
    print(f"测试1: news(sina) 分段拉取 {days}天 — 关键词命中时间分布")
    print(f"关键词: {keywords}")
    print(f"{'='*60}")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    segment_hours = 6
    current = start_dt
    keywords_lower = [k.lower() for k in keywords]

    total_news = 0
    total_hits = 0
    segment_stats = []
    all_hits = []

    while current < end_dt:
        seg_end = min(current + timedelta(hours=segment_hours), end_dt)
        seg_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
        seg_end_str = seg_end.strftime("%Y-%m-%d %H:%M:%S")

        try:
            df = pro.news(src='sina', start_date=seg_start_str, end_date=seg_end_str)
            count = len(df) if not df.empty else 0
            hits = 0

            if not df.empty:
                for _, row in df.iterrows():
                    matched = match_keywords(row, keywords_lower)
                    if matched:
                        hits += 1
                        all_hits.append({
                            'title': str(row.get('title', ''))[:80],
                            'datetime': str(row.get('datetime', ''))[:19],
                            'matched_kw': matched,
                        })

            total_news += count
            total_hits += hits
            segment_stats.append({
                'segment': f"{seg_start_str[:16]} ~ {seg_end_str[:16]}",
                'count': count,
                'hits': hits,
                'hit_rate': f"{hits/count*100:.1f}%" if count > 0 else "N/A",
            })

            marker = " ★" if hits > 0 else ""
            print(f"  {seg_start_str[:16]} ~ {seg_end_str[:16]}: "
                  f"{count:>5} 条, 命中 {hits}{marker}")

        except Exception as e:
            print(f"  {seg_start_str[:16]} ~ {seg_end_str[:16]}: 错误 {e}")

        current = seg_end
        time.sleep(0.3)

    print(f"\n  汇总: 总 {total_news} 条, 命中 {total_hits} 条, "
          f"命中率 {total_hits/total_news*100:.2f}%" if total_news > 0 else "")

    if all_hits:
        print(f"\n  命中的新闻:")
        for h in all_hits[:10]:
            print(f"    [{h['datetime']}] {h['title']}")
            print(f"      匹配: {h['matched_kw']}")

    return total_news, total_hits, all_hits


# ============================================================
# 测试2: 往前追溯 — 从3天扩展到7天、14天
# ============================================================
def test_lookback_expansion(pro, ticker, company_name, keywords):
    print(f"\n{'='*60}")
    print(f"测试2: 往前追溯 — 扩展时间范围看命中数变化")
    print(f"{'='*60}")

    keywords_lower = [k.lower() for k in keywords]
    end_dt = datetime.now()

    # 测试不同天数范围
    test_ranges = [1, 3, 5, 7, 10, 14]
    results = []

    for days in test_ranges:
        start_dt = end_dt - timedelta(days=days)
        current = start_dt
        total = 0
        hits = 0

        while current < end_dt:
            seg_end = min(current + timedelta(hours=6), end_dt)
            seg_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
            seg_end_str = seg_end.strftime("%Y-%m-%d %H:%M:%S")

            try:
                df = pro.news(src='sina', start_date=seg_start_str, end_date=seg_end_str)
                if not df.empty:
                    total += len(df)
                    for _, row in df.iterrows():
                        if match_keywords(row, keywords_lower):
                            hits += 1
            except Exception:
                pass

            current = seg_end
            time.sleep(0.3)

        results.append({'days': days, 'total': total, 'hits': hits})
        print(f"  {days:>2}天: 总 {total:>6} 条, 命中 {hits:>3} 条, "
              f"命中率 {hits/total*100:.3f}%" if total > 0 else f"  {days:>2}天: 无数据")

    # 分析趋势
    print(f"\n  趋势分析:")
    for i in range(1, len(results)):
        prev = results[i-1]
        curr = results[i]
        new_hits = curr['hits'] - prev['hits']
        new_days = curr['days'] - prev['days']
        print(f"    {prev['days']}天→{curr['days']}天: "
              f"新增 {new_hits} 条命中 (新增 {new_days} 天)")

    return results


# ============================================================
# 测试3: major_news 同样的追溯测试
# ============================================================
def test_major_news_lookback(pro, ticker, company_name, keywords):
    print(f"\n{'='*60}")
    print(f"测试3: major_news 追溯测试")
    print(f"{'='*60}")

    keywords_lower = [k.lower() for k in keywords]
    end_dt = datetime.now()

    test_ranges = [1, 3, 5, 7]

    for days in test_ranges:
        start_dt = end_dt - timedelta(days=days)
        current = start_dt
        total = 0
        company_hits = 0
        industry_hits = 0

        code = ticker.split('.')[0]
        company_kw = [code]
        if company_name:
            company_kw.append(company_name.lower())

        while current < end_dt:
            seg_end = min(current + timedelta(hours=12), end_dt)
            seg_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
            seg_end_str = seg_end.strftime("%Y-%m-%d %H:%M:%S")

            try:
                df = pro.major_news(
                    src='', start_date=seg_start_str, end_date=seg_end_str,
                    fields='title,content,pub_time,src'
                )
                if not df.empty:
                    total += len(df)
                    for _, row in df.iterrows():
                        text = strip_html(
                            str(row.get('title', '')) + ' ' + str(row.get('content', ''))
                        ).lower()
                        # 公司直接命中
                        if any(k in text for k in company_kw):
                            company_hits += 1
                        # 行业命中
                        elif any(k in text for k in keywords_lower):
                            industry_hits += 1
            except Exception:
                pass

            current = seg_end
            time.sleep(0.3)

        print(f"  {days:>2}天: 总 {total:>5} 条, "
              f"公司命中 {company_hits}, 行业命中 {industry_hits}")


# ============================================================
# 测试4: 多数据源对比 — 哪个源命中率最高
# ============================================================
def test_source_comparison(pro, ticker, company_name, keywords, days=3):
    print(f"\n{'='*60}")
    print(f"测试4: 不同数据源命中率对比 ({days}天)")
    print(f"{'='*60}")

    sources = ['sina', 'eastmoney', '10jqka', 'cls', 'yicai', 'jinrongjie']
    keywords_lower = [k.lower() for k in keywords]

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start_str = f"{start_dt.strftime('%Y-%m-%d')} 00:00:00"
    end_str = f"{end_dt.strftime('%Y-%m-%d')} 23:59:59"

    for src in sources:
        try:
            df = pro.news(src=src, start_date=start_str, end_date=end_str)
            if df.empty:
                print(f"  {src:>12}: 0 条")
                continue

            total = len(df)
            hits = sum(1 for _, row in df.iterrows()
                       if match_keywords(row, keywords_lower))
            print(f"  {src:>12}: {total:>5} 条, 命中 {hits:>3}, "
                  f"命中率 {hits/total*100:.2f}%")
        except Exception as e:
            print(f"  {src:>12}: 错误 - {e}")

        time.sleep(0.3)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    pro = get_pro()
    company_name, industry = get_stock_name(pro, ticker)

    print(f"{'='*60}")
    print(f"news 接口深度探索")
    print(f"股票: {ticker} ({company_name}) | 行业: {industry}")
    print(f"{'='*60}")

    # 构建关键词
    code = ticker.split('.')[0]
    keywords = [code]
    if company_name:
        keywords.append(company_name)
    if industry:
        keywords.append(industry)

    print(f"关键词: {keywords}")

    # 测试1: 分段拉取命中分布
    total, hits, all_hits = test_news_segment_distribution(
        pro, ticker, company_name, keywords, days)

    # 测试2: 往前追溯
    test_lookback_expansion(pro, ticker, company_name, keywords)

    # 测试3: major_news 追溯
    test_major_news_lookback(pro, ticker, company_name, keywords)

    # 测试4: 数据源对比
    test_source_comparison(pro, ticker, company_name, keywords, days)

    print(f"\n{'='*60}")
    print("探索完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
