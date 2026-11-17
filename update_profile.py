#!/usr/bin/env python3
"""Refresh dynamic values in the MOREE GitHub profile SVGs."""
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import html
import json
import os
import re
import urllib.request

BIRTH_DATE = date(2010, 2, 4)  # 15 Bahman 1388
USERNAME = "MorsalMashayekhi"
API_URL = "https://api.github.com/graphql"

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

def graphql(token, query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "MOREE-profile-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + payload["errors"][0].get("message", "unknown error"))
    return payload["data"]

def github_stats():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not available")
    
    query = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        followers { totalCount }
        contributionsCollection {
          totalCommitContributions
          totalRepositoriesWithContributedCommits
        }
        repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100, after: $cursor) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { stargazerCount }
        }
      }
    }
    """
    data = graphql(token, query, {"login": USERNAME})
    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {USERNAME}")

    repositories = user["repositories"]
    repo_count = repositories["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in repositories["nodes"])
    page = repositories["pageInfo"]

    # Fetch every page so stars are not silently limited to the first 100 repositories.
    while page["hasNextPage"]:
        data = graphql(token, query, {"login": USERNAME, "cursor": page["endCursor"]})
        repositories = data["user"]["repositories"]
        stars += sum(repo["stargazerCount"] for repo in repositories["nodes"])
        page = repositories["pageInfo"]

    contributions = user["contributionsCollection"]
    return {
        "repo_data": repo_count,
        "contrib_data": contributions["totalRepositoriesWithContributedCommits"],
        "star_data": stars,
        "commit_data": contributions["totalCommitContributions"],
        "follower_data": user["followers"]["totalCount"],
    }

def replace_tspan(svg, element_id, value):
    # The values in the SVG are <tspan> elements, not standalone <text> elements.
    pattern = rf'(<tspan\\b[^>]*\\bid="{re.escape(element_id)}"[^>]*>).*?(</tspan>)'
    updated, count = re.subn(
        pattern,
        lambda match: match.group(1) + html.escape(str(value)) + match.group(2),
        svg,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Missing SVG tspan id: {element_id}")
    return updated

today = datetime.now(ZoneInfo("Asia/Tehran")).date()
uptime = elapsed_age(BIRTH_DATE, today)

stats = github_stats()

for filename in ("dark_mode.svg", "light_mode.svg"):
    path = Path(filename)
    svg = path.read_text(encoding="utf-8")
    svg = replace_tspan(svg, "age_data", uptime)
    for element_id, value in stats.items():
        svg = replace_tspan(svg, element_id, value)
    path.write_text(svg, encoding="utf-8")

print(f"Updated uptime and GitHub stats: {stats}")
