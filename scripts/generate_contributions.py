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
  user(login:$login) { createdAt }
}
"""

CALENDAR_QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

def gql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ayank-profile-contribution-sync",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]

account = gql(USER_QUERY, {"login": LOGIN})
created_at = account.get("createdAt")
if not created_at:
    raise RuntimeError("GitHub did not return the account creation date.")

start_year = datetime.fromisoformat(created_at.replace("Z", "+00:00")).year
today = date.today()

all_days = []
for year in range(start_year, today.year + 1):
    user = gql(
        CALENDAR_QUERY,
        {
            "login": LOGIN,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year + 1}-01-01T00:00:00Z",
        },
    )
    calendar = user["contributionsCollection"]["contributionCalendar"]
    all_days.extend(
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    )

by_date = {
    d["date"]: int(d["contributionCount"])
    for d in all_days
    if d["date"] <= today.isoformat()
}
if not by_date:
    raise RuntimeError("GitHub returned no contribution days.")

positive = sorted(v for v in by_date.values() if v > 0)

def quantile(values, p):
    if not values:
        return 0
    return values[min(len(values)-1, max(0, math.ceil(len(values)*p)-1))]

q1, q2, q3 = quantile(positive, .25), quantile(positive, .50), quantile(positive, .75)
palette = ["#16181D", "#3B1017", "#65121D", "#A61B2B", "#FF3B30"]

def color(n):
    if n <= 0: return palette[0]
    if n <= q1: return palette[1]
    if n <= q2: return palette[2]
    if n <= q3: return palette[3]
    return palette[4]

years = list(range(start_year, today.year + 1))
cell, gap = 13, 4
week_step = cell + gap
left = 38
right = 18
top = 35
row_gap = 34
panel_height = 7 * week_step + 30
width = left + 53 * week_step + right
height = top + len(years) * panel_height + (len(years)-1)*row_gap + 36

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
    f'<title>{LOGIN} GitHub contribution history</title>',
    '<style>'
    '.title{font:600 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#f2f4f7}'
    '.label{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707a84}'
    '.sub{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9aa4ad}'
    '</style>',
    '<rect width="100%" height="100%" rx="14" fill="#0B0D10"/>',
]

weekday = {1:"Mon", 3:"Wed", 5:"Fri"}

for idx, year in enumerate(years):
    y0 = top + idx * (panel_height + row_gap)
    jan1 = date(year, 1, 1)
    start = jan1 - timedelta(days=(jan1.weekday()+1)%7)
    year_total = sum(n for d,n in by_date.items() if d.startswith(str(year)))

    parts.append(f'<text x="{left}" y="{y0-12}" class="title">{year}</text>')
    parts.append(f'<text x="{width-right-140}" y="{y0-12}" class="sub">{year_total} contribution{"s" if year_total != 1 else ""}</text>')

    # Month labels based on their first visible week.
    last_month = None
    for week in range(53):
        d = start + timedelta(days=week*7)
        if d.year != year:
            continue
        month = d.strftime("%b")
        if month != last_month:
            x = left + week*week_step
            parts.append(f'<text x="{x}" y="{y0+2}" class="label">{month}</text>')
            last_month = month

    for rowday, label in weekday.items():
        y = y0 + 18 + rowday*week_step + 9
        parts.append(f'<text x="0" y="{y}" class="label">{label}</text>')

    for week in range(53):
        for rowday in range(7):
            d = start + timedelta(days=week*7 + rowday)
            if d.year != year or d > today:
                continue
            n = by_date.get(d.isoformat(), 0)
            x = left + week*week_step
            y = y0 + 18 + rowday*week_step
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color(n)}">'
                f'<title>{d.isoformat()}: {n} contribution{"s" if n != 1 else ""}</title></rect>'
            )

parts.append(f'<text x="{left}" y="{height-12}" class="label">Less</text>')
for i, c in enumerate(palette):
    parts.append(f'<rect x="{left+31+i*19}" y="{height-22}" width="13" height="13" rx="3" fill="{c}"/>')
parts.append(f'<text x="{left+31+len(palette)*19+3}" y="{height-12}" class="label">More</text>')
parts.append('</svg>')

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {sum(by_date.values())} contributions from {start_year} through {today.year}.")
