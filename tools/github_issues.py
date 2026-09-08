import os

import requests
from strands import tool

from config.settings import DEFAULT_ISSUE_LIMIT, REPO_NAME


def _headers() -> dict:
    """Send the GitHub token when one is set — raises the rate limit and is
    required once the pipeline starts pushing branches."""
    token = os.getenv("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


@tool
def fetch_good_first_issues(repo: str = REPO_NAME, limit: int = DEFAULT_ISSUE_LIMIT) -> list[dict]:
    """Fetch open 'good first issue' tickets from a GitHub repo."""
    url = "https://api.github.com/search/issues"
    params = {
        "q": f'repo:{repo} is:issue is:open label:"good first issue"',
        "sort": "created",
        "order": "desc",
        "per_page": limit,
    }
    resp = requests.get(url, params=params, headers=_headers())
    resp.raise_for_status()
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "url": i["html_url"],
            "comments": i["comments"],
            "labels": [l["name"] for l in i["labels"]],
        }
        for i in resp.json()["items"]
    ]
