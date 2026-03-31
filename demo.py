"""
CDR Forensic Chatbot — Demo Script for Judges
=============================================
Run this script to see the query engine in action without launching the UI.
"""

import pandas as pd
import sys
import os

import re
from datetime import datetime, timedelta

# ── Inline copies of parse_query / filter_df (no streamlit dependency) ──────
PHONE_RE = re.compile(r"\b(\d{10,15})\b")
DATE_KEYWORDS = {
    "today": 0, "yesterday": 1, "last week": 7, "last month": 30,
    "last 3 days": 3, "last 24 hours": 1, "past week": 7, "past month": 30,
}

def parse_query(query):
    q = query.lower()
    phones = list(dict.fromkeys(PHONE_RE.findall(query)))
    days_back = None
    for kw, days in sorted(DATE_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in q:
            days_back = days
            break
    after_match = re.search(r"after\s+(\d{4}-\d{2}-\d{2})", q)
    before_match = re.search(r"before\s+(\d{4}-\d{2}-\d{2})", q)
    start_date = pd.to_datetime(after_match.group(1)) if after_match else None
    end_date   = pd.to_datetime(before_match.group(1)) if before_match else None
    if days_back is not None and start_date is None:
        end_date   = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
        start_date = end_date - pd.Timedelta(days=days_back)
    dur_sec = None
    dur_match = re.search(r"(longer|more)\s+than\s+(\d+)\s*(second|minute|min|sec)", q)
    if dur_match:
        val  = int(dur_match.group(2))
        unit = dur_match.group(3)
        dur_sec = val * 60 if "min" in unit else val
    return {"phones": phones, "start_date": start_date, "end_date": end_date, "min_duration": dur_sec}

def filter_df(df, params):
    result = df.copy()
    phones = params.get("phones", [])
    if phones:
        mask = pd.Series([False] * len(result), index=result.index)
        for p in phones:
            mask |= (result["caller"] == p) | (result["receiver"] == p)
        result = result[mask]
    if params.get("start_date") is not None:
        result = result[result["timestamp"] >= params["start_date"]]
    if params.get("end_date") is not None:
        result = result[result["timestamp"] <= params["end_date"]]
    if params.get("min_duration") is not None:
        result = result[result["duration"] >= params["min_duration"]]
    return result.sort_values("timestamp", ascending=False)

# Load sample data
df = pd.read_csv("sample_cdr.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["caller"] = df["caller"].astype(str).str.strip()
df["receiver"] = df["receiver"].astype(str).str.strip()
df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0).astype(int)

DEMO_QUERIES = [
    "Show calls from 9876543210 last month",
    "Calls between 9876543210 and 9123456789",
    "Show calls from 9000011111 longer than 200 seconds last month",
    "All calls yesterday",
    "Show calls from 9123456789 after 2024-12-01",
]

print("=" * 70)
print("  CDR FORENSIC CHATBOT — DEMO SCRIPT")
print("=" * 70)
print(f"  Dataset: {len(df)} records  |  "
      f"{df['timestamp'].min().date()} → {df['timestamp'].max().date()}")
print("=" * 70)

for q in DEMO_QUERIES:
    print(f"\n🗣️  QUERY: \"{q}\"")
    params = parse_query(q)
    filtered = filter_df(df, params)

    print(f"   Parsed → phones: {params['phones']} | "
          f"start: {params['start_date']} | end: {params['end_date']} | "
          f"min_dur: {params['min_duration']}")
    print(f"   Results: {len(filtered)} records")

    if not filtered.empty:
        print(filtered[["timestamp", "caller", "receiver", "duration"]]
              .head(5)
              .to_string(index=False))
        if len(filtered) > 5:
            print(f"   ... and {len(filtered) - 5} more records.")

print("\n" + "=" * 70)
print("✅ Demo complete. Launch the full UI with:  streamlit run app.py")
print("=" * 70)
