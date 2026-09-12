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

def gql(query: str, variables: dict) -> dict:
    payload = json.dumps({
        "query": query,
        "variables": variables,
    }).encode("utf-8")

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


# Get the account creation year first.
account = gql(USER_QUERY, {"login": LOGIN})
created_at = account.get("createdAt")
if not created_at:
    raise RuntimeError("GitHub did not return the account creation date.")

start_year = datetime.fromisoformat(
    created_at.replace("Z", "+00:00")
).year
today = date.today()

# GitHub's contribution calendar supports a bounded date range.
# Fetch one calendar year at a time so the full available history is preserved.
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

# Deduplicate and keep only dates through today.
by_date = {
    day["date"]: int(day["contributionCount"])
    for day in all_days
    if day["date"] <= today.isoformat()
}

if not by_date:
    raise RuntimeError("GitHub returned no contribution days.")

positive = sorted(count for count in by_date.values() if count > 0)


def quartile(values, p):
    if not values:
        return 0
    index = max(0, min(len(values) - 1, math.ceil(len(values) * p) - 1))
    return values[index]


q1 = quartile(positive, 0.25)
q2 = quartile(positive, 0.50)
q3 = quartile(positive, 0.75)

# Red/crimson palette matched to the README.
palette = [
    "#16181D",  # none
    "#3B1017",
    "#65121D",
    "#A61B2B",
    "#FF3B30",
]


def cell_color(count):
    if count <= 0:
        return palette[0]
    if count <= q1:
        return palette[1]
    if count <= q2:
        return palette[2]
    if count <= q3:
        return palette[3]
    return palette[4]


# SVG layout: two years per row, each with 53 weeks × 7 days.
cell = 11
gap = 3
year_gap = 34
left = 42
top = 34
panel_width = 53 * (cell + gap)
panel_height = 7 * (cell + gap) + 28

years = list(range(start_year, today.year + 1))
cols = 2
rows = math.ceil(len(years) / cols)

width = left + cols * panel_width + 16
height = 18 + rows * (panel_height + year_gap)

total = sum(by_date.values())

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — full GitHub contribution history</title>',
    f'<desc>{total} contributions from {start_year} through {today.year}.</desc>',
    '<rect width="100%" height="100%" rx="14" fill="#0B0D10"/>',
]

weekday_labels = {1: "M", 3: "W", 5: "F"}

for idx, year in enumerate(years):
    col = idx % cols
    row = idx // cols
    x0 = 18 + col * panel_width
    y0 = 12 + row * (panel_height + year_gap)

    parts.append(
        f'<text x="{x0}" y="{y0 + 13}" '
        'fill="#F2F4F7" font-size="12" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-weight="600">{year}</text>'
    )

    jan1 = date(year, 1, 1)
    calendar_start = jan1 - timedelta(days=(jan1.weekday() + 1) % 7)

    for week in range(53):
        for rowday in range(7):
            current = calendar_start + timedelta(days=week * 7 + rowday)

            if current.year != year or current > today:
                continue

            count = by_date.get(current.isoformat(), 0)
            x = x0 + 19 + week * (cell + gap)
            y = y0 + 22 + rowday * (cell + gap)
            fill = cell_color(count)

            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="2.5" fill="{fill}">'
                f'<title>{current.isoformat()}: {count} '
                f'contribution{"s" if count != 1 else ""}</title>'
                '</rect>'
            )

    for rowday, label in weekday_labels.items():
        y = y0 + 22 + rowday * (cell + gap) + 9
        parts.append(
            f'<text x="{x0}" y="{y}" fill="#707A84" font-size="9" '
            'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
            f'{label}</text>'
        )

parts.append(
    f'<text x="{left}" y="{height - 10}" fill="#9AA4AD" font-size="10" '
    'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
    f'{total} total contributions</text>'
)

for i, fill in enumerate(palette):
    parts.append(
        f'<rect x="{width - 135 + i * 17}" y="{height - 18}" '
        f'width="11" height="11" rx="2" fill="{fill}"/>'
    )

parts.append(
    f'<text x="{width - 151}" y="{height - 9}" fill="#707A84" font-size="9" '
    'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">Less</text>'
)
parts.append(
    f'<text x="{width - 40}" y="{height - 9}" fill="#707A84" font-size="9" '
    'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">More</text>'
)

parts.append("</svg>")

OUT.write_text("\n".join(parts), encoding="utf-8")
print(
    f"Generated {OUT} for {LOGIN}: "
    f"{total} contributions from {start_year} through {today.year}."
)
