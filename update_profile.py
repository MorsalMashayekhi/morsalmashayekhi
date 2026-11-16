#!/usr/bin/env python3
"""Refresh dynamic values in the MOREE GitHub profile SVGs."""
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import urllib.request

BIRTH_DATE = date(2010, 2, 4)  # 15 Bahman 1388
USERNAME = "MorsalMashayekhi"

def elapsed_age(start, end):
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    if days < 0:
        from calendar import monthrange
        prev_month = end.month - 1 or 12
        prev_year = end.year if end.month > 1 else end.year - 1
        days += monthrange(prev_year, prev_month)[1]
        months -= 1
    if months < 0:
        months += 12
        years -= 1
    return f"{years} years, {months} months, {days} days"

def github_stats():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {}
    query = """query($login:String!) {
      user(login:$login) {
        repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100) {
          totalCount
          nodes { stargazerCount }
        }
        followers { totalCount }
        contributionsCollection {
          totalCommitContributions
          totalRepositoriesWithContributedCommits
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "MOREE-profile-updater"})
    with urllib.request.urlopen(req, timeout=25) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise RuntimeError("GitHub GraphQL did not return profile stats")
    user = payload["data"]["user"]
    repos = user["repositories"]
    return {
        "repos": repos["totalCount"],
        "contributed": user["contributionsCollection"]["totalRepositoriesWithContributedCommits"],
        "stars": sum(node["stargazerCount"] for node in repos["nodes"]),
        "contributions": user["contributionsCollection"]["totalCommitContributions"],
        "followers": user["followers"]["totalCount"],
    }

def replace_text(svg, element_id, value):
    pattern = rf'(<text id="{re.escape(element_id)}"[^>]*>).*?(</text>)'
    updated, count = re.subn(pattern, lambda m: m.group(1) + str(value) + m.group(2), svg, count=1)
    if count != 1:
        raise RuntimeError(f"Missing SVG text id: {element_id}")
    return updated

today = datetime.now(ZoneInfo("Asia/Tehran")).date()
uptime = elapsed_age(BIRTH_DATE, today)
stats = {}
try:
    stats = github_stats()
except Exception as exc:
    print(f"Stats refresh skipped: {exc}")

for filename in ("dark_mode.svg", "light_mode.svg"):
    path = Path(filename)
    svg = path.read_text(encoding="utf-8")
    svg = replace_text(svg, "uptime", uptime) if 'id="uptime"' in svg else svg
    for key, value in stats.items():
        svg = replace_text(svg, key, value)
    path.write_text(svg, encoding="utf-8")
print(f"Updated uptime: {uptime}; refreshed {len(stats)} GitHub stats.")
