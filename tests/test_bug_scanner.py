from agents.bug_scanner_agent import extract_bug_scan_result
from tools.github_issues import fetch_good_first_issues


def test_fetch_returns_list_of_issues():
    issues = fetch_good_first_issues(limit=3)
    assert isinstance(issues, list)
    assert len(issues) <= 3
    for issue in issues:
        assert {"number", "title", "url", "comments", "labels"} <= issue.keys()


def test_extract_handles_nested_braces_and_trailing_prose():
    text = (
        "Here is the summary.\n\n"
        "```json\n"
        '{"qualifying_issues": [{"number": 1, "title": "x", "url": "u", '
        '"labels": ["kind/bug"], "comments": 3}], "excluded_count": 2, "notes": null}\n'
        "```\n\n"
        "Trailing note that should be ignored."
    )
    result = extract_bug_scan_result(text)
    assert result.excluded_count == 2
    assert result.qualifying_issues[0].number == 1
    assert result.qualifying_issues[0].comments == 3
