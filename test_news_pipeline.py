#!/usr/bin/env python3
"""Comprehensive tests for news fetching and the news analyst node.

Usage:
    python test_news_pipeline.py 600000.SH --trade-date 2026-05-15
    python test_news_pipeline.py 600000.SH --trade-date 2026-05-15 --live
    python test_news_pipeline.py 600000.SH --trade-date 2026-05-15 --live --route
    python test_news_pipeline.py 600000.SH --start-date 2026-05-12 --end-date 2026-05-15 --live --with-llm

By default the script runs deterministic checks that do not call external APIs.
Use --live to call direct Tushare/Akshare implementations, and --route to also
exercise route_to_vendor.
"""

from __future__ import annotations

import argparse
import csv
import ast
import importlib
import importlib.util
import io
import os
import sys
import traceback
import types
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable

import pandas as pd
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda


ROOT = Path(__file__).resolve().parent
NEWS_ANALYST_PATH = ROOT / "tradingagents" / "agents" / "analysts" / "news_analyst.py"
REQUIRED_TOOLS = ("get_company_news", "get_industry_news", "get_policy_news")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


class CheckRecorder:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.results.append(CheckResult(name, True, detail))
        print(f"  PASS {name}{': ' + detail if detail else ''}")

    def fail(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name, False, detail))
        print(f"  FAIL {name}: {detail}")

    def require(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail or "assertion failed")

    def summary(self) -> int:
        passed = sum(1 for r in self.results if r.ok)
        failed = len(self.results) - passed
        print("\n" + "=" * 80)
        print(f"SUMMARY: {passed} passed, {failed} failed")
        print("=" * 80)
        return 0 if failed == 0 else 1


def section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT / ".env")


def parse_csv_rows(raw: str) -> list[dict[str, str]]:
    data_lines = [
        line
        for line in str(raw).splitlines()
        if line.strip() and not line.startswith("#") and line.strip() != "No data available"
    ]
    if not data_lines:
        return []
    try:
        return list(csv.DictReader(io.StringIO("\n".join(data_lines))))
    except Exception:
        return []


def header_lines(raw: str) -> list[str]:
    return [line for line in str(raw).splitlines() if line.startswith("#")]


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except Exception:
            continue
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def validate_rows_in_range(
    recorder: CheckRecorder,
    label: str,
    rows: list[dict[str, str]],
    start_date: str,
    end_date: str,
) -> None:
    if not rows:
        recorder.ok(f"{label} date range", "no rows returned")
        return

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    date_keys = ("datetime", "pub_time", "Date", "date", "retrieved_date", "发布时间")
    checked = 0
    out_of_range = []

    for row in rows:
        raw_date = next((row.get(k) for k in date_keys if row.get(k)), "")
        parsed = parse_date(raw_date)
        if parsed is None:
            continue
        checked += 1
        if not (start <= parsed < end):
            title = row.get("title") or row.get("Title") or row.get("标题") or ""
            out_of_range.append(f"{raw_date} {title[:40]}")

    if checked == 0:
        recorder.ok(f"{label} date range", "rows had no parseable date column")
    else:
        recorder.require(
            not out_of_range,
            f"{label} date range",
            f"checked {checked} dated rows"
            if not out_of_range
            else f"out of range: {out_of_range[:3]}",
        )


def parse_keywords_from_header(raw: str) -> list[str]:
    for line in header_lines(raw):
        if line.startswith("# Keywords:"):
            _, _, value = line.partition(":")
            try:
                parsed = ast.literal_eval(value.strip())
                return [str(item) for item in parsed if str(item).strip()]
            except Exception:
                return [part.strip().strip("'\"") for part in value.split(",") if part.strip()]
    return []


def validate_company_keyword_relevance(
    recorder: CheckRecorder,
    label: str,
    raw: str,
    rows: list[dict[str, str]],
) -> None:
    keywords = parse_keywords_from_header(raw)
    if not keywords or not rows:
        recorder.ok(f"{label} company keyword relevance", "no keywords or rows to check")
        return

    normalized_keywords = [keyword.lower() for keyword in keywords if keyword]
    misses = []
    for row in rows:
        text = " ".join(str(value) for value in row.values()).lower()
        if not any(keyword in text for keyword in normalized_keywords):
            title = row.get("title") or row.get("Title") or row.get("标题") or ""
            misses.append(title[:60] or "<empty title>")

    recorder.require(
        not misses,
        f"{label} company keyword relevance",
        f"checked {len(rows)} rows"
        if not misses
        else f"rows without company keywords: {misses[:3]}",
    )


def validate_industry_relation_fields(
    recorder: CheckRecorder,
    label: str,
    rows: list[dict[str, str]],
) -> None:
    if not rows:
        recorder.ok(f"{label} relation fields", "no rows returned")
        return

    required = {"direct_or_indirect", "relation_type", "impact_path", "summary"}
    missing = [field for field in required if field not in rows[0]]
    recorder.require(
        not missing,
        f"{label} relation fields",
        f"fields present: {sorted(required)}" if not missing else f"missing: {missing}",
    )


def summarize_result(label: str, raw: str, max_titles: int = 3) -> list[dict[str, str]]:
    print(f"\n[{label}]")
    for line in header_lines(raw)[:8]:
        print(f"  {line}")
    rows = parse_csv_rows(raw)
    print(f"  rows: {len(rows)}")
    for i, row in enumerate(rows[:max_titles], 1):
        title = row.get("title") or row.get("Title") or row.get("标题") or ""
        source = row.get("data_source") or row.get("Source") or row.get("来源") or ""
        dt = row.get("datetime") or row.get("pub_time") or row.get("Date") or row.get("retrieved_date") or ""
        print(f"  {i}. [{source}] {dt} {title[:90]}")
    if "No data available" in str(raw):
        print("  note: No data available")
    return rows


def load_news_analyst_isolated():
    """Load news_analyst.py without importing the full tradingagents package."""
    fake_agent_utils = types.ModuleType("tradingagents.agents.utils.agent_utils")
    for name in REQUIRED_TOOLS:
        setattr(fake_agent_utils, name, SimpleNamespace(name=name))

    fake_modules = {
        "tradingagents": types.ModuleType("tradingagents"),
        "tradingagents.agents": types.ModuleType("tradingagents.agents"),
        "tradingagents.agents.utils": types.ModuleType("tradingagents.agents.utils"),
        "tradingagents.agents.utils.agent_utils": fake_agent_utils,
    }
    saved = {name: sys.modules.get(name) for name in fake_modules}

    try:
        sys.modules.update(fake_modules)
        spec = importlib.util.spec_from_file_location("isolated_news_analyst", NEWS_ANALYST_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load {NEWS_ANALYST_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class FakeLLM:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools):
        self.bound_tool_names = [tool.name for tool in tools]
        return RunnableLambda(lambda _messages: self.response)


def run_news_analyst_unit_tests(recorder: CheckRecorder) -> None:
    section("Unit: news analyst control flow")
    module = load_news_analyst_isolated()

    start, end = module._get_news_date_range("2026-05-15")
    recorder.require((start, end) == ("2026-05-12", "2026-05-15"), "date window", f"{start} to {end}")

    fake_llm = FakeLLM(AIMessage(content="模型未调用工具"))
    analyst = module.create_news_analyst(fake_llm)
    state = {
        "trade_date": "2026-05-15",
        "company_of_interest": "600000.SH",
        "messages": [],
    }
    result = analyst(state)
    forced_message = result["messages"][0]
    forced_calls = forced_message.tool_calls
    forced_names = [call["name"] for call in forced_calls]
    recorder.require(forced_names == list(REQUIRED_TOOLS), "forced missing tool calls", str(forced_names))

    args_by_name = {call["name"]: call["args"] for call in forced_calls}
    recorder.require(
        args_by_name["get_company_news"] == {
            "ticker": "600000.SH",
            "start_date": "2026-05-12",
            "end_date": "2026-05-15",
        },
        "company news forced args",
        str(args_by_name["get_company_news"]),
    )
    recorder.require(
        args_by_name["get_policy_news"] == {
            "ticker": "600000.SH",
            "look_back_days": 3,
            "end_date": "2026-05-15",
        },
        "policy news forced args",
        str(args_by_name["get_policy_news"]),
    )

    prior_ai = AIMessage(content="", tool_calls=forced_calls)
    tool_messages = [
        ToolMessage(content="ok", tool_call_id=call["id"], name=call["name"])
        for call in forced_calls
    ]
    fake_llm_done = FakeLLM(AIMessage(content="最终新闻报告"))
    analyst_done = module.create_news_analyst(fake_llm_done)
    done_result = analyst_done(
        {
            "trade_date": "2026-05-15",
            "company_of_interest": "600000.SH",
            "messages": [prior_ai] + tool_messages,
        }
    )
    recorder.require(done_result["news_report"] == "最终新闻报告", "report after all tools executed")


def run_dataflow_unit_tests(recorder: CheckRecorder) -> None:
    section("Unit: dataflow safeguards")
    try:
        tushare_news = importlib.import_module("tradingagents.dataflows.tushare_news")
    except Exception as exc:
        recorder.fail("import tushare_news", repr(exc))
        return

    empty = pd.DataFrame()
    formatted = tushare_news._format_to_csv(empty, "# header")
    recorder.require(formatted.startswith("# header"), "empty csv keeps header", formatted)

    original_get_filter_llm = tushare_news._get_filter_llm
    try:
        tushare_news._get_filter_llm = lambda: None
        selected = tushare_news._llm_select_relevant_news(
            "600000.SH",
            "浦发银行",
            pd.DataFrame([{"title": "无关市场新闻", "content": "指数波动"}]),
            1,
        )
        recorder.require(selected == [], "company semantic fallback does not hard-fill unrelated candidates", str(selected))

        class EmptyPolicyLLM:
            def invoke(self, _prompt):
                return SimpleNamespace(content="")

        tushare_news._get_filter_llm = lambda: EmptyPolicyLLM()
        cctv = pd.DataFrame(
            [
                {"title": "体育文化新闻", "content": "无行业政策内容"},
                {"title": "外交新闻", "content": "无行业政策内容"},
            ]
        )
        filtered = tushare_news._llm_filter_policy_news(
            cctv,
            "600000.SH",
            {"company_name": "浦发银行", "level_1": "银行", "level_2": "股份制银行"},
        )
        recorder.require(filtered.empty, "empty policy LLM selection returns empty frame")
    finally:
        tushare_news._get_filter_llm = original_get_filter_llm


def safe_call(label: str, func: Callable, recorder: CheckRecorder):
    try:
        result = func()
        recorder.ok(f"{label} call")
        return result
    except Exception as exc:
        recorder.fail(f"{label} call", f"{type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)
        return None


def disable_filter_llm_if_needed(module, with_llm: bool):
    if with_llm:
        return None
    original = getattr(module, "_get_filter_llm", None)
    if original is not None:
        module._get_filter_llm = lambda: None
    return original


def restore_filter_llm(module, original) -> None:
    if original is not None:
        module._get_filter_llm = original


def run_live_direct_tests(
    recorder: CheckRecorder,
    ticker: str,
    start_date: str,
    end_date: str,
    with_llm: bool,
) -> None:
    section("Live: direct vendor implementations")
    load_dotenv_if_available()

    try:
        tushare_news = importlib.import_module("tradingagents.dataflows.tushare_news")
        akshare_news = importlib.import_module("tradingagents.dataflows.akshare_news")
    except Exception as exc:
        recorder.fail("import direct news modules", repr(exc))
        return

    original_llm = disable_filter_llm_if_needed(tushare_news, with_llm)
    try:
        r1 = safe_call(
            "tushare get_company_news",
            lambda: tushare_news.get_company_news(ticker, start_date, end_date),
            recorder,
        )
        if r1 is not None:
            rows = summarize_result("tushare company", r1)
            validate_rows_in_range(recorder, "tushare company", rows, start_date, end_date)
            validate_company_keyword_relevance(recorder, "tushare company", r1, rows)

        r2 = safe_call(
            "tushare get_industry_news",
            lambda: tushare_news.get_industry_news(ticker, start_date, end_date),
            recorder,
        )
        if r2 is not None:
            rows = summarize_result("tushare industry", r2)
            validate_rows_in_range(recorder, "tushare industry", rows, start_date, end_date)
            validate_industry_relation_fields(recorder, "tushare industry", rows)

        r3 = safe_call(
            "tushare get_policy_news",
            lambda: tushare_news.get_policy_news(ticker, 3, end_date),
            recorder,
        )
        if r3 is not None:
            rows = summarize_result("tushare policy", r3)
            validate_rows_in_range(recorder, "tushare policy", rows, start_date, end_date)
    finally:
        restore_filter_llm(tushare_news, original_llm)

    r4 = safe_call(
        "akshare get_company_news",
        lambda: akshare_news.get_company_news(ticker, start_date, end_date),
        recorder,
    )
    if r4 is not None:
        rows = summarize_result("akshare company", r4)
        validate_rows_in_range(recorder, "akshare company", rows, start_date, end_date)

    r5 = safe_call(
        "akshare get_industry_news",
        lambda: akshare_news.get_industry_news(ticker, start_date, end_date),
        recorder,
    )
    if r5 is not None:
        rows = summarize_result("akshare industry", r5)
        validate_rows_in_range(recorder, "akshare industry", rows, start_date, end_date)

    r6 = safe_call(
        "akshare get_policy_news",
        lambda: akshare_news.get_policy_news(ticker, 3, end_date),
        recorder,
    )
    if r6 is not None:
        rows = summarize_result("akshare policy", r6)
        validate_rows_in_range(recorder, "akshare policy", rows, start_date, end_date)


def run_route_tests(
    recorder: CheckRecorder,
    ticker: str,
    start_date: str,
    end_date: str,
) -> None:
    section("Live: route_to_vendor chain")
    load_dotenv_if_available()

    try:
        interface = importlib.import_module("tradingagents.dataflows.interface")
    except Exception as exc:
        recorder.fail("import route_to_vendor", f"{type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)
        return

    calls = [
        ("route get_company_news", lambda: interface.route_to_vendor("get_company_news", ticker, start_date, end_date)),
        ("route get_industry_news", lambda: interface.route_to_vendor("get_industry_news", ticker, start_date, end_date)),
        ("route get_policy_news", lambda: interface.route_to_vendor("get_policy_news", ticker, 3, end_date)),
    ]
    for label, func in calls:
        raw = safe_call(label, func, recorder)
        if raw is not None:
            rows = summarize_result(label, raw)
            validate_rows_in_range(recorder, label, rows, start_date, end_date)
            if label == "route get_company_news":
                validate_company_keyword_relevance(recorder, label, raw, rows)
            if label == "route get_industry_news":
                validate_industry_relation_fields(recorder, label, rows)


def derive_dates(args) -> tuple[str, str]:
    if args.start_date and args.end_date:
        return args.start_date, args.end_date
    end = args.end_date or args.trade_date or date.today().isoformat()
    end_day = datetime.strptime(end[:10], "%Y-%m-%d")
    start = args.start_date or (end_day - timedelta(days=3)).strftime("%Y-%m-%d")
    return start, end_day.strftime("%Y-%m-%d")


def parse_args():
    parser = argparse.ArgumentParser(description="Test news analyst and news fetching pipeline.")
    parser.add_argument("ticker", nargs="?", default="600000.SH", help="A-share ticker, e.g. 600000.SH")
    parser.add_argument("--trade-date", default=date.today().isoformat(), help="Analysis date, yyyy-mm-dd")
    parser.add_argument("--start-date", default=None, help="Override news start date, yyyy-mm-dd")
    parser.add_argument("--end-date", default=None, help="Override news end date, yyyy-mm-dd")
    parser.add_argument("--live", action="store_true", help="Call direct Tushare/Akshare news implementations")
    parser.add_argument("--route", action="store_true", help="Also test route_to_vendor")
    parser.add_argument("--with-llm", action="store_true", help="Allow LLM filtering/summarization during live tests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    start_date, end_date = derive_dates(args)

    print(f"ticker: {ticker}")
    print(f"date window: {start_date} to {end_date}")
    print(f"live: {args.live}; route: {args.route}; with_llm: {args.with_llm}")

    recorder = CheckRecorder()
    run_news_analyst_unit_tests(recorder)
    run_dataflow_unit_tests(recorder)

    if args.live:
        run_live_direct_tests(recorder, ticker, start_date, end_date, args.with_llm)

    if args.route:
        run_route_tests(recorder, ticker, start_date, end_date)

    return recorder.summary()


if __name__ == "__main__":
    raise SystemExit(main())
