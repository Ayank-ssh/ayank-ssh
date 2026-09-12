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
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]

today = date.today()
end = today + timedelta(days=(6 - today.weekday()) % 7)
start = end - timedelta(days=363)

calendar = gql({
    "login": LOGIN,
    "from": start.isoformat() + "T00:00:00Z",
    "to": (end + timedelta(days=1)).isoformat() + "T00:00:00Z",
})

counts = {
    d["date"]: int(d["contributionCount"])
    for week in calendar["weeks"]
    for d in week["contributionDays"]
    if d["date"] <= today.isoformat()
}

positive = sorted(v for v in counts.values() if v > 0)

def quantile(values, p):
    if not values:
        return 0
    return values[min(len(values) - 1, max(0, math.ceil(len(values) * p) - 1))]

q1 = quantile(positive, .25)
q2 = quantile(positive, .50)
q3 = quantile(positive, .75)

# Red/crimson palette matching the profile.
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

cell = 12
gap = 3
step = cell + gap
label_w = 30
left = 12
right = 16
top = 40
bottom = 34

weeks = []
cursor = start - timedelta(days=(start.weekday() + 1) % 7)
last = end
while cursor <= last:
    weeks.append([cursor + timedelta(days=i) for i in range(7)])
    cursor += timedelta(days=7)

width = left + label_w + len(weeks) * step + right
height = top + 7 * step + bottom
total = sum(counts.values())

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} — GitHub contribution activity</title>',
    f'<desc>{total} contributions in the last year.</desc>',
    '<style>'
    '.title{font:600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#F2F4F7}'
    '.sub{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9AA4AD}'
    '.label{font:9px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707A84}'
    '</style>',
    '<rect width="100%" height="100%" rx="12" fill="#0B0D10"/>',
    f'<text x="{left}" y="17" class="title">{total} contributions in the last year</text>',
    f'<text x="{width-right-78}" y="17" class="sub">Less</text>',
]

# Month labels like GitHub.
last_month = None
for wi, week in enumerate(weeks):
    first_real = next((d for d in week if d <= today), None)
    if not first_real:
        continue
    key = (first_real.year, first_real.month)
    if key != last_month:
        x = left + label_w + wi * step
        parts.append(f'<text x="{x}" y="31" class="label">{first_real.strftime("%b")}</text>')
        last_month = key

# Weekday labels.
for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
    y = top + row * step + 9
    parts.append(f'<text x="{left}" y="{y}" class="label">{label}</text>')

for wi, week in enumerate(weeks):
    for row, day in enumerate(week):
        if day > today or day < start:
            continue
        n = counts.get(day.isoformat(), 0)
        x = left + label_w + wi * step
        y = top + row * step
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color(n)}">'
            f'<title>{day.strftime("%A, %B %d, %Y")}: {n} contribution{"s" if n != 1 else ""}</title>'
            '</rect>'
        )

# Legend, compact like GitHub.
legend_x = width - 61
for i, fill in enumerate(palette):
    parts.append(
        f'<rect x="{legend_x + i*14}" y="8" width="10" height="10" rx="2.5" fill="{fill}"/>'
    )
parts.append(f'<text x="{legend_x + len(palette)*14 + 5}" y="17" class="sub">More</text>')

parts.append("</svg>")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {total} contributions in the last year.")
