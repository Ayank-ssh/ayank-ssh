import json
import math
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USER", "Ayank-ssh")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("dist/contributions.svg")

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
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
    body = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ayank-profile-contribution-graph",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

today = date.today()
end = today + timedelta(days=(6 - today.weekday()) % 7)
start = end - timedelta(days=83)

weeks_data = gql({
    "login": LOGIN,
    "from": start.isoformat() + "T00:00:00Z",
    "to": (end + timedelta(days=1)).isoformat() + "T00:00:00Z",
})

days = [day for week in weeks_data for day in week["contributionDays"]]
counts = {
    d["date"]: int(d["contributionCount"])
    for d in days
    if start.isoformat() <= d["date"] <= today.isoformat()
}

positive = sorted(v for v in counts.values() if v > 0)

def q(values, p):
    if not values:
        return 0
    return values[min(len(values) - 1, max(0, math.ceil(len(values) * p) - 1))]

q1, q2, q3 = q(positive, .25), q(positive, .50), q(positive, .75)
palette = ["#16181D", "#3B1017", "#65121D", "#A61B2B", "#FF3B30"]

def color(n):
    if n <= 0: return palette[0]
    if n <= q1: return palette[1]
    if n <= q2: return palette[2]
    if n <= q3: return palette[3]
    return palette[4]

weeks = []
cursor = start
while cursor <= end:
    weeks.append([cursor + timedelta(days=i) for i in range(7)])
    cursor += timedelta(days=7)

cell, gap = 20, 6
step = cell + gap
label_w, left, right = 34, 16, 18
top, bottom = 50, 42
width = left + label_w + len(weeks) * step + right
height = top + 7 * step + bottom
total = sum(counts.get((today - timedelta(days=i)).isoformat(), 0) for i in range(84))

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — GitHub activity</title>',
    f'<desc>{total} contributions across the latest 12 weeks ending {today.isoformat()}.</desc>',
    '<style>.title{font:700 16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#F2F4F7}.sub{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9AA4AD}.label{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707A84}</style>',
    '<rect width="100%" height="100%" rx="14" fill="#0B0D10"/>',
    f'<text x="{left}" y="22" class="title">GitHub Activity</text>',
    f'<text x="{left}" y="39" class="sub">{total} contributions • last 12 weeks</text>',
]

for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
    parts.append(f'<text x="{left}" y="{top + row * step + 13}" class="label">{label}</text>')

last_month = None
for wi, week in enumerate(weeks):
    first = next((d for d in week if d <= today), None)
    if first:
        key = (first.year, first.month)
        if key != last_month:
            parts.append(f'<text x="{left + label_w + wi * step}" y="{top - 11}" class="label">{first.strftime("%b")}</text>')
            last_month = key
    for row, d in enumerate(week):
        if d > today or d < start:
            continue
        n = counts.get(d.isoformat(), 0)
        x, y = left + label_w + wi * step, top + row * step
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{color(n)}"><title>{d.strftime("%A, %B %d, %Y")}: {n} contribution{"s" if n != 1 else ""}</title></rect>')

legend_y = height - 18
parts.append(f'<text x="{left}" y="{legend_y}" class="label">Less</text>')
for i, fill in enumerate(palette):
    parts.append(f'<rect x="{left + 30 + i * 21}" y="{legend_y - 11}" width="13" height="13" rx="4" fill="{fill}"/>')
parts.append(f'<text x="{left + 30 + len(palette) * 21 + 4}" y="{legend_y}" class="label">More</text>')
parts.append('</svg>')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {total} contributions in the latest 12 weeks.")
