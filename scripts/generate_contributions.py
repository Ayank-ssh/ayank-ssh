import json
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USER", "Ayank-ssh")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/contributions.svg")

QUERY = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        colors
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

payload = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=payload,
    headers={
        "Authorization": f"bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "ayank-profile-contributions",
        "Accept": "application/vnd.github+json",
    },
)
with urllib.request.urlopen(req, timeout=30) as response:
    data = json.load(response)

if data.get("errors"):
    raise RuntimeError(data["errors"])

calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
weeks = calendar["weeks"]
total = calendar["totalContributions"]

# Palette matched to the README: near-black -> deep crimson -> bright red.
levels = ["#16181d", "#3b1017", "#65121d", "#a61b2b", "#ff3b30"]

counts = [
    d["contributionCount"]
    for w in weeks
    for d in w["contributionDays"]
]
positive = sorted(c for c in counts if c > 0)

def level(count: int) -> str:
    if count <= 0:
        return levels[0]
    if not positive:
        return levels[1]
    # Four intensity bands based on the user's own contribution distribution.
    import math
    q = [positive[max(0, math.ceil(len(positive)*p)-1)] for p in (0.25, 0.50, 0.75)]
    if count <= q[0]:
        return levels[1]
    if count <= q[1]:
        return levels[2]
    if count <= q[2]:
        return levels[3]
    return levels[4]

cell = 13
gap = 4
left = 44
top = 34
week_step = cell + gap
height = top + 7 * week_step + 26
width = left + len(weeks) * week_step + 8

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
    '<title id="title">GitHub contribution activity</title>',
    f'<desc id="desc">{esc(LOGIN)} made {total} contributions in the last year.</desc>',
    '<rect width="100%" height="100%" rx="12" fill="#0b0d10"/>',
    '<style>.label{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#9aa4ad}.day{font:10px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#707a84}</style>',
    f'<text x="{left}" y="18" class="day">{total} contributions in the last year</text>',
]

# Month labels.
last_month = None
for wi, w in enumerate(weeks):
    first = w["contributionDays"][0]["date"]
    d = datetime.strptime(first, "%Y-%m-%d").date()
    month = d.strftime("%b")
    if month != last_month and wi > 0:
        parts.append(
            f'<text x="{left + wi * week_step}" y="31" class="day">{month}</text>'
        )
        last_month = month

# Weekday labels.
for label, row in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
    y = top + row * week_step + 9
    parts.append(f'<text x="0" y="{y}" class="day">{label}</text>')

for wi, w in enumerate(weeks):
    for day in w["contributionDays"]:
        d = datetime.strptime(day["date"], "%Y-%m-%d").date()
        x = left + wi * week_step
        y = top + d.weekday() * week_step
        c = level(day["contributionCount"])
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{c}">'
            f'<title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>'
        )

parts += [
    f'<text x="{left}" y="{height - 8}" class="day">Less</text>',
]
for i, c in enumerate(levels):
    parts.append(
        f'<rect x="{left + 34 + i*18}" y="{height - 18}" width="13" height="13" rx="3" fill="{c}"/>'
    )
parts += [
    f'<text x="{left + 34 + 5*18 + 4}" y="{height - 8}" class="day">More</text>',
    "</svg>",
]

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Wrote {OUT}")
