import json
import math
import os
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USER", "Ayank-ssh")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("dist/contributions.svg")

QUERY = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
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

def gql():
    body = json.dumps({
        "query": QUERY,
        "variables": {"login": LOGIN},
    }).encode("utf-8")

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

calendar = gql()
weeks = calendar["weeks"]
total = int(calendar["totalContributions"])

counts = {
    day["date"]: int(day["contributionCount"])
    for week in weeks
    for day in week["contributionDays"]
}

positive = sorted(v for v in counts.values() if v > 0)

def quantile(values, p):
    if not values:
        return 0
    idx = min(len(values) - 1, max(0, math.ceil(len(values) * p) - 1))
    return values[idx]

q1 = quantile(positive, 0.25)
q2 = quantile(positive, 0.50)
q3 = quantile(positive, 0.75)

# Same profile palette, but GitHub-native intensity progression.
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

# Native-like sizing: compact cells, 7 weekday rows, ~53 week columns.
cell = 11
gap = 3
step = cell + gap
left = 32
right = 20
top = 34
bottom = 30
week_count = len(weeks)

width = left + week_count * step + right
height = top + 7 * step + bottom

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
    f'<title>{LOGIN} GitHub contributions</title>',
    f'<desc>{total} contributions in the last year.</desc>',
    '<style>'
    '.summary{font:600 11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#F2F4F7}'
    '.label{font:9px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707A84}'
    '</style>',
    f'<text x="{left}" y="12" class="summary">{total} contributions in the last year</text>',
]

# Month labels. Use the first week of each month, matching GitHub's layout.
seen_months = set()
for wi, week in enumerate(weeks):
    for day in week["contributionDays"]:
        if day["date"][:7] in seen_months:
            continue
        month_key = day["date"][:7]
        # Don't show a label too far into a week; first appearance is enough.
        parts.append(
            f'<text x="{left + wi * step}" y="27" class="label">{day["date"][5:7]}</text>'
        )
        seen_months.add(month_key)
        break

# Weekday labels.
for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
    y = top + row * step + 9
    parts.append(f'<text x="0" y="{y}" class="label">{label}</text>')

for wi, week in enumerate(weeks):
    for row, day in enumerate(week["contributionDays"]):
        if row > 6:
            continue
        x = left + wi * step
        y = top + row * step
        n = int(day["contributionCount"])
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color(n)}">'
            f'<title>{day["date"]}: {n} contribution{"s" if n != 1 else ""}</title>'
            '</rect>'
        )

# GitHub-style legend.
legend_y = height - 14
legend_x = width - 74
parts.append(f'<text x="{legend_x - 21}" y="{legend_y}" class="label">Less</text>')
for i, fill in enumerate(palette):
    parts.append(
        f'<rect x="{legend_x + i*14}" y="{legend_y-10}" width="10" height="10" rx="2.5" fill="{fill}"/>'
    )
parts.append(f'<text x="{legend_x + len(palette)*14 + 3}" y="{legend_y}" class="label">More</text>')

parts.append('</svg>')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Generated {OUT}: {total} contributions.")
