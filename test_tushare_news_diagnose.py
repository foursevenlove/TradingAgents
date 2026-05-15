#!/usr/bin/env python3
"""Diagnose why Tushare company news returns no direct hits."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> int:
    load_env()

    import tushare as ts
    import akshare as ak

    ticker = "600000.SH"
    company = "浦发银行"
    code = "600000"
    start_dt = "2026-05-12 00:00:00"
    end_dt = "2026-05-15 23:59:59"
    sources = ["eastmoney", "sina", "10jqka", "cls", "yicai", "jinrongjie"]

    token = os.environ.get("TUSHARE_TOKEN")
    print(f"TUSHARE_TOKEN present: {bool(token)}")
    pro = ts.pro_api(token)

    print("\nstock_basic:")
    try:
        df_basic = pro.stock_basic(
            ts_code=ticker,
            fields="ts_code,name,fullname,industry,market,list_date",
        )
        print(df_basic.to_string(index=False))
    except Exception as exc:
        print(f"stock_basic error: {type(exc).__name__}: {exc}")

    print("\nTushare pro.news source summary:")
    total_rows = 0
    total_hits = 0
    for src in sources:
        try:
            df = pro.news(src=src, start_date=start_dt, end_date=end_dt)
        except Exception as exc:
            print(f"\nSRC={src} ERROR {type(exc).__name__}: {exc}")
            continue

        total_rows += len(df)
        print(f"\nSRC={src} rows={len(df)} cols={list(df.columns)}")
        if df.empty:
            continue

        title = df["title"].astype(str) if "title" in df.columns else pd.Series("", index=df.index)
        content = df["content"].astype(str) if "content" in df.columns else pd.Series("", index=df.index)
        text = title + " " + content
        mask = text.str.contains(company, na=False) | text.str.contains(code, na=False)
        hits = int(mask.sum())
        total_hits += hits
        print(f"keyword_hits={hits}")

        display_cols = [c for c in ["datetime", "title", "content"] if c in df.columns]
        sample = df.loc[mask, display_cols].head(5) if hits else df[display_cols].head(3)
        for _, row in sample.iterrows():
            dt = str(row.get("datetime", ""))[:19]
            title_value = str(row.get("title", ""))[:120]
            content_value = str(row.get("content", ""))[:160].replace("\n", " ")
            print(f"  [{dt}] {title_value}")
            if content_value and content_value != "nan":
                print(f"      {content_value}")

    print(f"\nTushare total_rows={total_rows}, total_keyword_hits={total_hits}")

    print("\nTushare announcement interfaces:")
    ann_start = start_dt[:10].replace("-", "")
    ann_end = end_dt[:10].replace("-", "")
    for method_name in ["anns_d", "anns"]:
        if not hasattr(pro, method_name):
            print(f"{method_name}: not available on pro client")
            continue
        try:
            method = getattr(pro, method_name)
            df_ann = method(ts_code=ticker, start_date=ann_start, end_date=ann_end)
            print(f"{method_name}: rows={len(df_ann)} cols={list(df_ann.columns)}")
            if not df_ann.empty:
                print(df_ann.head(10).to_string(index=False))
        except Exception as exc:
            print(f"{method_name}: {type(exc).__name__}: {exc}")

    print("\nAkshare stock_news_em sample:")
    try:
        df_ak = ak.stock_news_em(symbol=ticker)
        print(f"akshare rows={len(df_ak)} cols={list(df_ak.columns)}")
        print(df_ak.head(10).to_string(index=False))
    except Exception as exc:
        print(f"akshare error: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
