"""Parsing helpers for recommendation news payloads."""

import csv
import io
from typing import Dict, List


def parse_recommendation_news_csv(csv_string: str) -> List[Dict]:
    """Parse vendor recommendation-news CSV into normalized dictionaries."""
    if not csv_string or "No news" in csv_string:
        return []

    data_lines = [
        line
        for line in csv_string.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(data_lines)))
    rows = []
    for row in reader:
        rows.append({
            "title": (row.get("title") or "").strip(),
            "content": (row.get("content") or "").strip(),
            "datetime": (row.get("datetime") or row.get("pub_time") or "").strip(),
            "data_source": (row.get("data_source") or row.get("source") or "").strip(),
        })
    return rows
