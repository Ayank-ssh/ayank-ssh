import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USER", "Ayank-ssh")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/contributions.svg")

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        contributionDays {
          contributionCount
          date
        }
      }
    }
  }
}
"""

def gql(variables):
    payload = json.dumps({"query": QUERY, "variables": variables}).encode()
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
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["contributionDays"]

today = date.today()
start = today - timedelta(days=29)

days = gql({
    "login": LOGIN,
    "from": f"{start.isoformat()}T00:00:00Z",
    "to": f"{(today + timedelta(days=1)).isoformat()}T00:00:00Z",
})

counts = {
    d["date"]: int(d["contributionCount"])
    for d in days
    if start.isoformat() <= d["date"] <= today.isoformat()
}

positive = sorted(v for v in counts.values() if v > 0)

def quantile(values, p):
    if not values:
        return 0
    return values[min(len(values)-1, max(0, math.ceil(len(values) * p) - 1))]

q1 = quantile(positive, .25)
q2 = quantile(positive, .50)
q3 = quantile(positive, .75)

# Match the README's crimson/red system.
palette = ["#16181D", "#3B1017", "#65121D", "#A61B2B", "#FF3B30"]

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

# Calendar layout:
# columns = weeks, rows = weekdays, like GitHub's contribution graph.
calendar_start = start - timedelta(days=(start.weekday() + 1) % 7)
calendar_end = today + timedelta(days=(5 - today.weekday()) % 7)
weeks = []
cursor = calendar_start
while cursor <= calendar_end:
    weeks.append([cursor + timedelta(days=i) for i in range(7)])
    cursor += timedelta(days=7)

cell = 18
gap = 5
label_w = 34
left = 26
right = 26
top = 46
bottom = 40
week_step = cell + gap
width = left + label_w + len(weeks) * week_step + right
height = top + 7 * week_step + bottom
total = sum(counts.values())

month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — recent GitHub contribution activity</title>',
    f'<desc>{total} contributions from {start.strftime("%b %d")} to {today.strftime("%b %d, %Y")}.</desc>',
    '<style>'
    '.title{font:700 15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#F2F4F7}'
    '.sub{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9AA4AD}'
    '.label{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707A84}'
    '</style>',
    '<rect width="100%" height="100%" rx="14" fill="#0B0D10"/>',
    f'<text x="{left}" y="21" class="title">Last 30 days</text>',
    f'<text x="{left}" y="38" class="sub">{total} contributions • {start.strftime("%b %d")} — {today.strftime("%b %d, %Y")}</text>',
]

# Weekday labels.
for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
    y = top + row * week_step + 12
    parts.append(f'<text x="{left}" y="{y}" class="label">{label}</text>')

# Month labels and day cells.
seen_months = set()
for wi, week in enumerate(weeks):
    # Add month label above the first in-range day in that week.
    for d in week:
        if d < start or d > today:
            continue
        key = (d.year, d.month)
        if key not in seen_months:
            x = left + label_w + wi * week_step
            parts.append(
                f'<text x="{x}" y="{top-9}" class="label">{month_names[d.month-1]}</text>'
            )
            seen_months.add(key)
        break

    for row, d in enumerate(week):
        if d < start or d > today:
            continue
        n = counts.get(d.isoformat(), 0)
        x = left + label_w + wi * week_step
        y = top + row * week_step
        fill = color(n)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{fill}">'
            f'<title>{d.strftime("%A, %B %d, %Y")}: {n} contribution{"s" if n != 1 else ""}</title>'
            f'</rect>'
        )

# Footer legend.
legend_y = height - 17
parts.append(f'<text x="{left}" y="{legend_y}" class="label">Less</text>')
for i, fill in enumerate(palette):
    parts.append(
        f'<rect x="{left + 30 + i*20}" y="{legend_y-11}" width="12" height="12" rx="4" fill="{fill}"/>'
    )
parts.append(
    f'<text x="{left + 30 + len(palette)*20 + 4}" y="{legend_y}" class="label">More</text>'
)

parts.append("</svg>")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {total} contributions over 30 days.")
