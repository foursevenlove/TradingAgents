#!/usr/bin/env python3
"""验证 major_news 分层新闻架构的 demo 脚本。

测试内容：
1. major_news 3天数据量和内容质量
2. 行业关键词提取（通过 get_sw_industry）
3. 行业关键词过滤 major_news 的效果
4. 与现有 news 快讯的对比

用法:
    python test_major_news_demo.py <ticker> [days]

示例:
    python test_major_news_demo.py 688347.SH 3
    python test_major_news_demo.py 600519.SH 3
"""
import sys
import os
import time
from datetime import datetime, timedelta

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
    """获取股票名称"""
    try:
        df = pro.stock_basic(ts_code=ticker, fields='ts_code,name,industry')
        if not df.empty:
            return df.iloc[0]['name'], df.iloc[0].get('industry', '')
    except Exception as e:
        print(f"  获取股票名称失败: {e}")
    return None, None


def get_sw_industry_info(ticker):
    """通过已有的 route_to_vendor 获取申万行业分类"""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        result = route_to_vendor("get_sw_industry", ticker)
        return result
    except Exception as e:
        return f"获取失败: {e}"


def test_major_news_volume(pro, days=3):
    """测试1: major_news 数据量"""
    print(f"\n{'='*60}")
    print(f"测试1: major_news {days}天数据量")
    print(f"{'='*60}")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    start_str = f"{start_dt.strftime('%Y-%m-%d')} 00:00:00"
    end_str = f"{end_dt.strftime('%Y-%m-%d')} 23:59:59"

    print(f"时间范围: {start_str} ~ {end_str}")

    # major_news 单次最大400条，需要分段
    all_data = []
    current = start_dt

    segment_hours = 12  # major_news 数据量较少，用12小时分段
    call_count = 0

    while current < end_dt:
        seg_end = min(current + timedelta(hours=segment_hours), end_dt)
        seg_start_str = current.strftime("%Y-%m-%d %H:%M:%S")
        seg_end_str = seg_end.strftime("%Y-%m-%d %H:%M:%S")

        try:
            df = pro.major_news(
                src='',
                start_date=seg_start_str,
                end_date=seg_end_str,
                fields='title,content,pub_time,src'
            )
            call_count += 1
            if not df.empty:
                all_data.append(df)
                print(f"  [{seg_start_str} ~ {seg_end_str}] → {len(df)} 条")
            else:
                print(f"  [{seg_start_str} ~ {seg_end_str}] → 0 条")
        except Exception as e:
            print(f"  [{seg_start_str} ~ {seg_end_str}] → 错误: {e}")

        current = seg_end
        time.sleep(0.3)

    if all_data:
        merged = pd.concat(all_data, ignore_index=True)
        merged = merged.drop_duplicates(subset=['title'], keep='first')
        print(f"\n  总计: {len(merged)} 条（去重后），API调用 {call_count} 次")

        # 数据源分布
        if 'src' in merged.columns:
            print(f"\n  数据源分布:")
            for src, count in merged['src'].value_counts().items():
                print(f"    {src}: {count} 条")

        # 内容长度统计
        if 'content' in merged.columns:
            lengths = merged['content'].str.len()
            print(f"\n  内容长度统计:")
            print(f"    平均: {lengths.mean():.0f} 字")
            print(f"    中位数: {lengths.median():.0f} 字")
            print(f"    最长: {lengths.max():.0f} 字")
            print(f"    最短: {lengths.min():.0f} 字")

        # 展示前3条标题
        print(f"\n  前5条标题:")
        for i, row in merged.head(5).iterrows():
            title = str(row.get('title', ''))[:80]
            pub_time = str(row.get('pub_time', ''))[:19]
            src = str(row.get('src', ''))
            print(f"    [{pub_time}] [{src}] {title}")

        return merged
    else:
        print("  没有获取到任何数据")
        return pd.DataFrame()


def test_industry_keywords(pro, ticker):
    """测试2: 行业关键词提取"""
    print(f"\n{'='*60}")
    print(f"测试2: 行业关键词提取 ({ticker})")
    print(f"{'='*60}")

    # 2a: 股票基本信息
    name, industry = get_stock_name(pro, ticker)
    print(f"  股票名称: {name}")
    print(f"  tushare行业: {industry}")

    # 2b: 申万行业分类
    sw_info = get_sw_industry_info(ticker)
    print(f"\n  申万行业分类:")
    # 只打印前500字符
    print(f"  {str(sw_info)[:500]}")

    # 2c: 构建关键词集合
    keywords = set()
    if name:
        keywords.add(name)
    keywords.add(ticker.split('.')[0])
    if industry:
        keywords.add(industry)

    # 从申万分类中提取关键词
    sw_str = str(sw_info)
    for line in sw_str.split('\n'):
        for field in ['一级行业', '二级行业', '三级行业', 'industry_name',
                       'level1', 'level2', 'level3']:
            if field in line:
                # 提取冒号后面的值
                parts = line.split(':')
                if len(parts) > 1:
                    val = parts[-1].strip().strip('"').strip("'")
                    if val and len(val) > 1:
                        keywords.add(val)

    print(f"\n  提取的关键词集合: {keywords}")
    return keywords, name


def test_keyword_filter(major_df, keywords, company_name, ticker):
    """测试3: 关键词过滤 major_news"""
    print(f"\n{'='*60}")
    print(f"测试3: 关键词过滤 major_news")
    print(f"{'='*60}")

    if major_df.empty:
        print("  没有 major_news 数据可供过滤")
        return

    print(f"  总新闻数: {len(major_df)}")
    print(f"  使用关键词: {keywords}")

    keywords_lower = [k.lower() for k in keywords]

    def match_level(row):
        """返回匹配级别: 3=公司名, 2=行业, 1=弱相关, 0=无关"""
        title = str(row.get('title', '')).lower()
        content = str(row.get('content', '')).lower()
        text = title + ' ' + content

        # 公司名/代码直接匹配
        code = ticker.split('.')[0]
        if company_name and company_name.lower() in text:
            return 3
        if code in text:
            return 3

        # 行业关键词匹配
        for kw in keywords_lower:
            if kw in text and kw != code and kw != (company_name or '').lower():
                return 2

        return 0

    major_df = major_df.copy()
    major_df['match_level'] = major_df.apply(match_level, axis=1)

    # 统计
    level_3 = major_df[major_df['match_level'] == 3]
    level_2 = major_df[major_df['match_level'] == 2]
    level_0 = major_df[major_df['match_level'] == 0]

    print(f"\n  匹配结果:")
    print(f"    公司直接相关 (level 3): {len(level_3)} 条")
    print(f"    行业相关 (level 2): {len(level_2)} 条")
    print(f"    无关 (level 0): {len(level_0)} 条")

    # 展示公司直接相关
    if not level_3.empty:
        print(f"\n  公司直接相关新闻:")
        for i, row in level_3.head(5).iterrows():
            title = str(row.get('title', ''))[:80]
            content_preview = str(row.get('content', ''))[:100]
            print(f"    标题: {title}")
            print(f"    摘要: {content_preview}...")
            print()

    # 展示行业相关
    if not level_2.empty:
        print(f"\n  行业相关新闻 (前5条):")
        for i, row in level_2.head(5).iterrows():
            title = str(row.get('title', ''))[:80]
            content_preview = str(row.get('content', ''))[:100]
            print(f"    标题: {title}")
            print(f"    摘要: {content_preview}...")
            print()

    return major_df[major_df['match_level'] > 0]


def test_compare_with_news(pro, ticker, days=3):
    """测试4: 与现有 news 快讯对比"""
    print(f"\n{'='*60}")
    print(f"测试4: 与 news 快讯对比")
    print(f"{'='*60}")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start_str = f"{start_dt.strftime('%Y-%m-%d')} 00:00:00"
    end_str = f"{end_dt.strftime('%Y-%m-%d')} 23:59:59"

    # 只拉 sina（数据量最大的源）做对比
    try:
        df = pro.news(src='sina', start_date=start_str, end_date=end_str)
        if not df.empty:
            print(f"  news(sina) {days}天: {len(df)} 条快讯")
            # 用公司名过滤
            name, _ = get_stock_name(pro, ticker)
            code = ticker.split('.')[0]
            keywords = [code]
            if name:
                keywords.append(name)

            filtered = df[df.apply(
                lambda r: any(
                    k.lower() in str(r.get('title', '')).lower() + str(r.get('content', '')).lower()
                    for k in keywords
                ), axis=1
            )]
            print(f"  关键词过滤后: {filtered} 条")

            if not filtered.empty:
                print(f"\n  快讯示例 (前3条):")
                for i, row in filtered.head(3).iterrows():
                    title = str(row.get('title', ''))[:80]
                    content = str(row.get('content', ''))[:60]
                    print(f"    标题: {title}")
                    print(f"    内容: {content}")
                    print()
        else:
            print(f"  news(sina) 返回空")
    except Exception as e:
        print(f"  news(sina) 调用失败: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print(f"{'='*60}")
    print(f"major_news 分层架构验证 Demo")
    print(f"股票: {ticker} | 天数: {days}")
    print(f"{'='*60}")

    pro = get_pro()

    # 测试1: major_news 数据量
    major_df = test_major_news_volume(pro, days)

    # 测试2: 行业关键词提取
    keywords, company_name = test_industry_keywords(pro, ticker)

    # 测试3: 关键词过滤
    if not major_df.empty:
        filtered = test_keyword_filter(major_df, keywords, company_name, ticker)

    # 测试4: 与 news 快讯对比
    test_compare_with_news(pro, ticker, days)

    print(f"\n{'='*60}")
    print("验证完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
