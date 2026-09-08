import requests

def fetch_good_first_issues(repo="keycloak/keycloak", limit=10):
    url = f"https://api.github.com/search/issues"
    params = {
        "q": f"repo:{repo} is:issue is:open label:\"good first issue\"",
        "sort": "created",
        "order": "desc",
        "per_page": limit,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return [
        {"number": i["number"], "title": i["title"], "url": i["html_url"], "comments": i["comments"]}
        for i in resp.json()["items"]
    ]

for issue in fetch_good_first_issues():
    print(issue)

