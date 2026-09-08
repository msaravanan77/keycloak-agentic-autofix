from pydantic import BaseModel


class Issue(BaseModel):
    number: int
    title: str
    url: str
    labels: list[str]
    comments: int = 0


class BugScanResult(BaseModel):
    qualifying_issues: list[Issue]
    excluded_count: int
    notes: str | None = None