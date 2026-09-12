import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USER", "Ayank-ssh")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/contributions.svg")

USER_QUERY = """
query($login:String!) {
  user(login:$login) {
    createdAt
  }
}
"""

CALENDAR_QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { contributionCount date }
        }
      }
    }
  }
}
"""

def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "ayank-profile-contribution-sync",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]

account = gql(USER_QUERY, {"login": LOGIN})
created_at = account.get("createdAt", "")
if not created_at:
    raise RuntimeError("GitHub did not return the account creation date.")

start_year = datetime.fromisoformat(created_at.replace("Z", "+00:00")).year
today = date.today()
all_days = []

for year in range(start_year, today.year + 1):
    # Each request covers exactly one calendar year, staying within
    # GitHub's contribution-calendar date-range limit.
    u = gql(
        CALENDAR_QUERY,
        {
            "login": LOGIN,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year + 1}-01-01T00:00:00Z",
        },
    )
    calendar = u["contributionsCollection"]["contributionCalendar"]
    all_days.extend(
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    )

# GitHub's contribution calendar is naturally a one-year view. Query every
# calendar year from the account creation year through the current year.
today = date.today()
start_year = today.year
created = None
all_days = []

# First request: account creation + current year.
first = gql(
    f"{today.year-1}-01-01T00:00:00Z",
    f"{today.year+1}-01-01T00:00:00Z",
)
created = first.get("createdAt", "")
if created:
    start_year = datetime.fromisoformat(created.replace("Z", "+00:00")).year

for year in range(start_year, today.year + 1):
    u = gql(
        f"{year}-01-01T00:00:00Z",
        f"{year+1}-01-01T00:00:00Z",
    )
    days = [
        day
        for week in u["contributionsCollection"]["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    all_days.extend(days)

# Deduplicate and limit to dates through today.
by_date = {
    d["date"]: int(d["contributionCount"])
    for d in all_days
    if d["date"] <= today.isoformat()
}
if not by_date:
    raise RuntimeError("No contribution data returned from GitHub.")

positive = sorted(v for v in by_date.values() if v > 0)

def quartiles(values):
    if not values:
        return [0, 0, 0]
    return [
        values[max(0, math.ceil(len(values) * p) - 1)]
        for p in (0.25, 0.50, 0.75)
    ]

q1, q2, q3 = quartiles(positive)
palette = ["#16181d", "#3b1017", "#65121d", "#a61b2b", "#ff3b30"]

def color(n):
    if n <= 0:
        return palette[0]
    if n <= q1:
        return palette[1]
    if n <= q2:
        return palette[2]
    if n <= q3:
        return palette[3]
    return palette[4]

cell, gap = 11, 3
year_gap = 34
left = 42
top = 34
panel_w = 53 * (cell + gap)
panel_h = 7 * (cell + gap) + 28
years = list(range(start_year, today.year + 1))
cols = 2
rows = math.ceil(len(years) / cols)
width = left + cols * panel_w + 16
height = 18 + rows * (panel_h + year_gap)

total = sum(by_date.values())
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — contribution history</title>',
    f'<desc>{total} contributions across {years[0]}–{years[-1]}.</desc>',
    '<rect width="100%" height="100%" rx="14" fill="#0b0d10"/>',
]

weekday_labels = {1: "M", 3: "W", 5: "F"}

for idx, year in enumerate(years):
    col = idx % cols
    row = idx // cols
    x0 = 18 + col * panel_w
    y0 = 12 + row * (panel_h + year_gap)

    parts.append(f'<text x="{x0}" y="{y0+13}" fill="#f2f4f7" font-size="12" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-weight="600">{year}</text>')

    # Find the first Sunday of the calendar area that contains Jan 1.
    jan1 = date(year, 1, 1)
    start = jan1 - timedelta(days=(jan1.weekday() + 1) % 7)

    # 53 columns is enough for the year plus alignment.
    for week in range(53):
        for rowday in range(7):
            d = start + timedelta(days=week*7 + rowday)
            if d.year != year or d > today:
                continue
            x = x0 + 19 + week * (cell + gap)
            y = y0 + 22 + rowday * (cell + gap)
            n = by_date.get(d.isoformat(), 0)
            c = color(n)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{c}">'
                f'<title>{d.isoformat()}: {n} contribution{"s" if n != 1 else ""}</title></rect>'
            )

    for r, lab in weekday_labels.items():
        y = y0 + 22 + r * (cell + gap) + 9
        parts.append(
            f'<text x="{x0}" y="{y}" fill="#707a84" font-size="9" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{lab}</text>'
        )

parts.append(f'<text x="{left}" y="{height-10}" fill="#9aa4ad" font-size="10" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{total} total contributions</text>')
for i, c in enumerate(palette):
    parts.append(f'<rect x="{width-135+i*17}" y="{height-18}" width="11" height="11" rx="2" fill="{c}"/>')
parts.append(f'<text x="{width-151}" y="{height-9}" fill="#707a84" font-size="9" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">Less</text>')
parts.append(f'<text x="{width-40}" y="{height-9}" fill="#707a84" font-size="9" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">More</text>')
parts.append("</svg>")

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Wrote {OUT} with {len(by_date)} days and {total} contributions.")
