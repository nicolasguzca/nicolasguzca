"""Fetch profile stats and the contribution calendar from the GitHub GraphQL API.

Writes cache/stats.json (numbers for the card) and cache/calendar.json (the
last year of days for the swarm board). Standard library only.

Needs a token in GITHUB_TOKEN. In Actions the built-in token is enough: the
calendar already includes private contribution counts when "Private
contributions" is switched on in the profile settings.

    GITHUB_TOKEN=$(gh auth token) python tools/fetch_stats.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
USER = os.environ.get("GH_USER", "nicolasguzca")
API = "https://api.github.com/graphql"


def gql(query: str, **variables) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-refresh",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


MAIN = """
query($login: String!, $after: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
    contributionsCollection {
      contributionYears
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def main() -> None:
    data = gql(MAIN, login=USER)["user"]
    repos = data["repositories"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    after = repos["pageInfo"]["endCursor"] if repos["pageInfo"]["hasNextPage"] else None
    while after:
        page = gql(MAIN, login=USER, after=after)["user"]["repositories"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        after = page["pageInfo"]["endCursor"] if page["pageInfo"]["hasNextPage"] else None

    coll = data["contributionsCollection"]
    years = sorted(coll["contributionYears"])

    # All-time total: one aliased contributionsCollection per calendar year.
    parts = [
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z")'
        " { contributionCalendar { totalContributions } }"
        for y in years
    ]
    per_year = gql("query($login: String!) { user(login: $login) { %s } }" % " ".join(parts), login=USER)["user"]
    all_time = sum(v["contributionCalendar"]["totalContributions"] for v in per_year.values())

    cal = coll["contributionCalendar"]
    days = [
        {
            "date": d["date"],
            "weekday": d["weekday"],
            "count": d["contributionCount"],
            "level": LEVELS.get(d["contributionLevel"], 0),
        }
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]

    CACHE.mkdir(exist_ok=True)
    stats = {
        "created": data["createdAt"],
        "repos": repos["totalCount"],
        "stars": stars,
        "contributed_to": data["repositoriesContributedTo"]["totalCount"],
        "followers": data["followers"]["totalCount"],
        "contributions_year": cal["totalContributions"],
        "contributions_all_time": all_time,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }
    (CACHE / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    (CACHE / "calendar.json").write_text(json.dumps(days, indent=1) + "\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
