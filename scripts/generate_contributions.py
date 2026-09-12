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

def gql(variables):
    payload = json.dumps({
        "query": QUERY,
        "variables": variables,
    }).encode()

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ayank-profile-recent-contributions",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)

    if data.get("errors"):
        raise RuntimeError(data["errors"])

    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


today = date.today()
start = today - timedelta(days=29)
calendar = gql({
    "login": LOGIN,
    "from": f"{start.isoformat()}T00:00:00Z",
    "to": f"{(today + timedelta(days=1)).isoformat()}T00:00:00Z",
})

days = {
    d["date"]: int(d["contributionCount"])
    for week in calendar["weeks"]
    for d in week["contributionDays"]
    if start.isoformat() <= d["date"] <= today.isoformat()
}

values = sorted(v for v in days.values() if v > 0)

def quantile(values, p):
    if not values:
        return 0
    index = max(0, min(len(values) - 1, math.ceil(len(values) * p) - 1))
    return values[index]

q1 = quantile(values, 0.25)
q2 = quantile(values, 0.50)
q3 = quantile(values, 0.75)

palette = ["#16181D", "#3B1017", "#65121D", "#A61B2B", "#FF3B30"]

def color(count):
    if count <= 0:
        return palette[0]
    if count <= q1:
        return palette[1]
    if count <= q2:
        return palette[2]
    if count <= q3:
        return palette[3]
    return palette[4]

# 30 cells: 6 columns x 5 rows, large enough to read in a README.
cell = 24
gap = 7
cols = 6
rows = 5
left = 98
top = 54
right = 30
bottom = 36
width = left + cols * (cell + gap) + right
height = top + rows * (cell + gap) + bottom

total = sum(days.values())

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — recent GitHub activity</title>',
    f'<desc>{total} contributions in the last 30 days, from {start.isoformat()} to {today.isoformat()}.</desc>',
    '<style>'
    '.title{font:700 17px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#F2F4F7}'
    '.sub{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9AA4AD}'
    '.day{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707A84}'
    '</style>',
    '<rect width="100%" height="100%" rx="14" fill="#0B0D10"/>',
    f'<text x="{left}" y="23" class="title">Last 30 days</text>',
    f'<text x="{left}" y="40" class="sub">{start.strftime("%b %d, %Y")} — {today.strftime("%b %d, %Y")}  •  {total} contributions</text>',
]

# Arrange days chronologically in rows of six.
for index in range(30):
    d = start + timedelta(days=index)
    n = days.get(d.isoformat(), 0)
    col = index % cols
    row = index // cols
    x = left + col * (cell + gap)
    y = top + row * (cell + gap)

    parts.append(
        f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="6" fill="{color(n)}">'
        f'<title>{d.strftime("%A, %B %d, %Y")}: {n} contribution{"s" if n != 1 else ""}</title>'
        '</rect>'
    )

    parts.append(
        f'<text x="{x + cell/2}" y="{y + cell + 14}" text-anchor="middle" class="day">'
        f'{d.day}</text>'
    )

# Legend.
legend_y = height - 18
parts.append(f'<text x="{left}" y="{legend_y}" class="day">Less</text>')
for i, fill in enumerate(palette):
    parts.append(
        f'<rect x="{left + 31 + i*21}" y="{legend_y-11}" width="13" height="13" rx="4" fill="{fill}"/>'
    )
parts.append(f'<text x="{left + 31 + len(palette)*21 + 4}" y="{legend_y}" class="day">More</text>')

parts.append("</svg>")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {total} contributions in the last 30 days.")
